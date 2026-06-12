"""
Repository — the only module that talks to SQLite.

Responsibilities:
  1. Accept a batch of raw stock dicts from the ingestion pipeline.
  2. Run each record through the validator (defence in depth — the
     orchestrator has already validated, but the repository does not
     trust upstream layers).
  3. Deduplicate within the batch (last-write-wins for same ticker).
  4. Upsert into ``market_data`` inside a single transaction.
  5. Mark rows that were NOT refreshed in this run as "stale."
  6. Log an ``ingestion_runs`` audit row with counts.

Transaction safety:
  • The entire batch is wrapped in a single SQLite transaction (the
    ``with connection`` context manager commits on success, rolls back
    on exception).
  • WAL journal mode is enabled so concurrent readers (the Flask route)
    are never blocked by a write.

Why OrderedDict for dedup?
  • Preserves insertion order (for deterministic test output).
  • O(1) membership check.
  • Last-write-wins: if the same ticker appears twice in the batch,
    the later record overwrites the earlier one.
"""

import logging
import sqlite3
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

from config import DATABASE_PATH
from persistence.schema import initialize_schema
from validator.stock_validator import validation_errors

logger = logging.getLogger(__name__)


class StockRepository:
    """
    Manages the SQLite lifecycle for market-data persistence.

    Usage::

        repo = StockRepository()
        result = repo.save(raw_records, expected_tickers=TICKERS)
        #  result["stocks"]         → list of active stock dicts
        #  result["upserted_count"] → how many rows were written
    """

    def __init__(self, path: str = DATABASE_PATH):
        self.path = Path(path)

    # ── Public API ──────────────────────────────────────────────────────

    def save(self, records: list[dict], expected_tickers: list[str] = None) -> dict:
        """
        Persist a batch of market-data records.

        This method is *idempotent* — calling it twice with the same data
        produces the same database state (upsert semantics).

        Args:
            records:          Raw stock dicts from the fetcher.
            expected_tickers: The full watchlist.  Tickers in the DB but
                              *not* in this list are marked stale.

        Returns:
            A summary dict with counts and the list of active stocks.
        """
        started_at = self._utc_now()

        # ── Step 1: Validate and deduplicate in memory ──────────────────
        clean_records, rejected_count, duplicate_count = self._sanitize(records)
        expected = self._normalize_tickers(expected_tickers)

        # ── Step 2: Ensure the data directory exists ────────────────────
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # ── Step 3: Single-transaction write ────────────────────────────
        with self._connect() as connection:
            initialize_schema(connection)

            upserted_count = self._upsert_batch(
                connection, clean_records, started_at
            )
            stale_count = self._mark_stale_rows(
                connection, expected, started_at
            )

            completed_at = self._utc_now()

            # ── Step 4: Audit log ───────────────────────────────────────
            connection.execute(
                """
                INSERT INTO ingestion_runs (
                    started_at, completed_at,
                    requested_count, valid_count, duplicate_count,
                    upserted_count, stale_count, skipped_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    started_at, completed_at,
                    len(records), len(clean_records), duplicate_count,
                    upserted_count, stale_count, rejected_count,
                ),
            )

            # ── Step 5: Read back active rows for the API response ──────
            active_rows = self._fetch_active_rows(connection)

        logger.info(
            "Batch persisted",
            extra={
                "extra_fields": {
                    "upserted": upserted_count,
                    "rejected": rejected_count,
                    "duplicates": duplicate_count,
                    "stale": stale_count,
                }
            },
        )

        return {
            "started_at": started_at,
            "completed_at": completed_at,
            "requested_count": len(records),
            "valid_count": len(clean_records),
            "duplicate_count": duplicate_count,
            "skipped_count": rejected_count,
            "upserted_count": upserted_count,
            "stale_count": stale_count,
            "stocks": active_rows,
        }

    # ── Connection factory ──────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        """
        Open a connection with production-safe pragmas.

        • ``row_factory = Row`` — rows behave like dicts.
        • ``foreign_keys = ON`` — enforce referential integrity.
        • ``journal_mode = WAL`` — concurrent reads during writes.
        • ``synchronous = NORMAL`` — good durability without the
          performance penalty of FULL.
        """
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    # ── Sanitization ────────────────────────────────────────────────────

    def _sanitize(self, records: list[dict]) -> tuple[list[dict], int, int]:
        """
        Validate every record and collapse duplicates within the batch.

        Returns:
            (clean_records, rejected_count, duplicate_count)
        """
        rejected_count = 0
        duplicate_count = 0
        seen: OrderedDict[str, dict] = OrderedDict()

        for record in records:
            errors = validation_errors(record)
            if errors:
                logger.debug(
                    "Record rejected: %s — %s",
                    record.get("ticker", "?"),
                    "; ".join(errors),
                )
                rejected_count += 1
                continue

            ticker = record["ticker"].strip().upper()
            normalized = {
                "ticker": ticker,
                "name": record["name"].strip(),
                "sector": record["sector"].strip(),
                "market_cap": int(record["market_cap"]),
            }

            if ticker in seen:
                duplicate_count += 1

            seen[ticker] = normalized

        return list(seen.values()), rejected_count, duplicate_count

    # ── Upsert ──────────────────────────────────────────────────────────

    def _upsert_batch(
        self,
        connection: sqlite3.Connection,
        records: list[dict],
        timestamp: str,
    ) -> int:
        """
        Insert-or-update each record.

        On conflict (same ticker already exists):
          • Update name, sector, market_cap to the latest values.
          • Refresh ``last_seen_at``.
          • Clear the stale flag so the ticker is active again.
        """
        upserted_count = 0

        for record in records:
            connection.execute(
                """
                INSERT INTO market_data (
                    ticker, name, sector, market_cap,
                    first_seen_at, last_seen_at,
                    is_stale, stale_since
                ) VALUES (?, ?, ?, ?, ?, ?, 0, NULL)
                ON CONFLICT(ticker) DO UPDATE SET
                    name         = excluded.name,
                    sector       = excluded.sector,
                    market_cap   = excluded.market_cap,
                    last_seen_at = excluded.last_seen_at,
                    is_stale     = 0,
                    stale_since  = NULL
                """,
                (
                    record["ticker"],
                    record["name"],
                    record["sector"],
                    record["market_cap"],
                    timestamp,
                    timestamp,
                ),
            )
            upserted_count += 1

        return upserted_count

    # ── Stale detection ─────────────────────────────────────────────────

    def _mark_stale_rows(
        self,
        connection: sqlite3.Connection,
        expected_tickers: list[str],
        timestamp: str,
    ) -> int:
        """
        Mark any ticker NOT in ``expected_tickers`` as stale.

        This handles the case where a ticker is removed from the watchlist
        or the upstream returned no data for it.  Rather than deleting the
        row (losing historical data), we soft-flag it.

        ``stale_since`` uses COALESCE so the first time a row goes stale we
        record the timestamp, but subsequent runs don't overwrite it.
        """
        if not expected_tickers:
            return 0

        placeholders = ", ".join(["?"] * len(expected_tickers))

        cursor = connection.execute(
            f"""
            UPDATE market_data
            SET is_stale    = 1,
                stale_since = COALESCE(stale_since, ?)
            WHERE ticker NOT IN ({placeholders})
              AND last_seen_at < ?
            """,
            [timestamp, *expected_tickers, timestamp],
        )

        return cursor.rowcount if cursor.rowcount != -1 else 0

    # ── Query ───────────────────────────────────────────────────────────

    def _fetch_active_rows(self, connection: sqlite3.Connection) -> list[dict]:
        """Return all non-stale stocks, sorted alphabetically by ticker."""
        cursor = connection.execute(
            """
            SELECT ticker, name, sector, market_cap,
                   first_seen_at, last_seen_at
            FROM   market_data
            WHERE  is_stale = 0
            ORDER  BY ticker
            """
        )
        return [dict(row) for row in cursor.fetchall()]

    # ── Utilities ───────────────────────────────────────────────────────

    def _normalize_tickers(self, tickers: list[str] | None) -> list[str]:
        """Deduplicate and uppercase a list of ticker strings."""
        if not tickers:
            return []

        seen: set[str] = set()
        normalized: list[str] = []

        for ticker in tickers:
            if not ticker:
                continue
            value = ticker.strip().upper()
            if value not in seen:
                seen.add(value)
                normalized.append(value)

        return normalized

    @staticmethod
    def _utc_now() -> str:
        """ISO-8601 UTC timestamp for audit columns."""
        return datetime.now(timezone.utc).isoformat()
