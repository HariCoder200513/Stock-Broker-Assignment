import sqlite3
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

from config import DATABASE_PATH
from persistence.schema import initialize_schema
from validator.stock_validator import validation_errors


class StockRepository:
    def __init__(
        self,
        path: str = DATABASE_PATH
    ):
        self.path = Path(path)

    def save(self, records, expected_tickers=None):
        """
        Persist a cleaned market-data batch.

        The database keeps one row per ticker. Repeated runs are idempotent:
        - duplicate tickers in the incoming batch are collapsed in memory
        - the ticker primary key prevents duplicate rows
        - existing rows are updated in place with the latest values
        - tickers not refreshed in the current run are marked stale
        """
        started_at = self._utc_now()
        clean_records, rejected_count, duplicate_count = self._sanitize(records)
        expected = self._normalize_tickers(expected_tickers)

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with self._connect() as connection:
            initialize_schema(connection)
            upserted_count = self._upsert_batch(
                connection,
                clean_records,
                started_at
            )
            stale_count = self._mark_stale_rows(
                connection,
                expected,
                started_at
            )
            completed_at = self._utc_now()

            connection.execute(
                """
                INSERT INTO ingestion_runs (
                    started_at,
                    completed_at,
                    requested_count,
                    valid_count,
                    duplicate_count,
                    upserted_count,
                    stale_count,
                    skipped_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    started_at,
                    completed_at,
                    len(records),
                    len(clean_records),
                    duplicate_count,
                    upserted_count,
                    stale_count,
                    rejected_count
                )
            )

            active_rows = self._fetch_active_rows(connection)

        return {
            "started_at": started_at,
            "completed_at": completed_at,
            "requested_count": len(records),
            "valid_count": len(clean_records),
            "duplicate_count": duplicate_count,
            "skipped_count": rejected_count,
            "upserted_count": upserted_count,
            "stale_count": stale_count,
            "stocks": active_rows
        }

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def _sanitize(self, records):
        clean_records = []
        rejected_count = 0
        duplicate_count = 0
        seen = OrderedDict()

        for record in records:
            errors = validation_errors(record)

            if errors:
                rejected_count += 1
                continue

            ticker = record["ticker"].strip().upper()
            normalized = {
                "ticker": ticker,
                "name": record["name"].strip(),
                "sector": record["sector"].strip(),
                "market_cap": int(record["market_cap"])
            }

            if ticker in seen:
                duplicate_count += 1

            seen[ticker] = normalized

        clean_records = list(seen.values())
        return clean_records, rejected_count, duplicate_count

    def _upsert_batch(self, connection, records, timestamp):
        upserted_count = 0

        for record in records:
            connection.execute(
                """
                INSERT INTO market_data (
                    ticker,
                    name,
                    sector,
                    market_cap,
                    first_seen_at,
                    last_seen_at,
                    is_stale,
                    stale_since
                ) VALUES (?, ?, ?, ?, ?, ?, 0, NULL)
                ON CONFLICT(ticker) DO UPDATE SET
                    name = excluded.name,
                    sector = excluded.sector,
                    market_cap = excluded.market_cap,
                    last_seen_at = excluded.last_seen_at,
                    is_stale = 0,
                    stale_since = NULL
                """,
                (
                    record["ticker"],
                    record["name"],
                    record["sector"],
                    record["market_cap"],
                    timestamp,
                    timestamp
                )
            )
            upserted_count += 1

        return upserted_count

    def _mark_stale_rows(self, connection, expected_tickers, timestamp):
        if not expected_tickers:
            return 0

        placeholders = ", ".join(["?"] * len(expected_tickers))

        cursor = connection.execute(
            f"""
            UPDATE market_data
            SET is_stale = 1,
                stale_since = COALESCE(stale_since, ?)
            WHERE ticker NOT IN ({placeholders})
              AND last_seen_at < ?
            """,
            [timestamp, *expected_tickers, timestamp]
        )

        return cursor.rowcount if cursor.rowcount != -1 else 0

    def _fetch_active_rows(self, connection):
        cursor = connection.execute(
            """
            SELECT ticker, name, sector, market_cap, first_seen_at, last_seen_at
            FROM market_data
            WHERE is_stale = 0
            ORDER BY ticker
            """
        )

        return [dict(row) for row in cursor.fetchall()]

    def _normalize_tickers(self, tickers):
        if not tickers:
            return []

        normalized = []
        seen = set()

        for ticker in tickers:
            if not ticker:
                continue

            value = ticker.strip().upper()
            if value in seen:
                continue

            seen.add(value)
            normalized.append(value)

        return normalized

    def _utc_now(self):
        return datetime.now(timezone.utc).isoformat()
