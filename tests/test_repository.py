"""
Unit tests for the persistence layer (StockRepository).

These tests use a temporary in-memory SQLite database so they:
  • Run fast (no disk I/O).
  • Are fully isolated (each test gets a fresh DB).
  • Don't pollute the production database.

Scenarios covered:
  • Clean batch insertion.
  • Upsert semantics (same ticker, updated data).
  • Rejection of invalid records at the repository level.
  • Deduplication within a single batch.
  • Stale-row detection.
  • Audit logging in ingestion_runs.
"""

import sqlite3
import pytest
from persistence.repository import StockRepository


# ── Fixtures ────────────────────────────────────────────────────────────────

def _make_repo(tmp_path) -> StockRepository:
    """Create a StockRepository pointing at a temporary SQLite file."""
    db_path = str(tmp_path / "test.sqlite3")
    return StockRepository(path=db_path)


def _valid_records() -> list[dict]:
    """A batch of 3 known-good records."""
    return [
        {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology", "market_cap": 3_000_000_000_000},
        {"ticker": "MSFT", "name": "Microsoft Corp.", "sector": "Technology", "market_cap": 2_800_000_000_000},
        {"ticker": "JPM", "name": "JPMorgan Chase", "sector": "Financial Services", "market_cap": 500_000_000_000},
    ]


# ── Basic insertion ─────────────────────────────────────────────────────────

class TestBasicInsertion:
    """Verify that clean records are persisted correctly."""

    def test_saves_all_valid_records(self, tmp_path):
        repo = _make_repo(tmp_path)
        result = repo.save(_valid_records())

        assert result["valid_count"] == 3
        assert result["upserted_count"] == 3
        assert result["skipped_count"] == 0
        assert len(result["stocks"]) == 3

    def test_stock_data_is_correct(self, tmp_path):
        repo = _make_repo(tmp_path)
        result = repo.save(_valid_records())

        stocks_by_ticker = {s["ticker"]: s for s in result["stocks"]}
        aapl = stocks_by_ticker["AAPL"]

        assert aapl["name"] == "Apple Inc."
        assert aapl["sector"] == "Technology"
        assert aapl["market_cap"] == 3_000_000_000_000


# ── Upsert semantics ───────────────────────────────────────────────────────

class TestUpsert:
    """Verify that re-saving the same ticker updates rather than duplicates."""

    def test_upsert_updates_existing_row(self, tmp_path):
        repo = _make_repo(tmp_path)
        repo.save(_valid_records())

        # Update Apple's market cap
        updated = [{"ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology", "market_cap": 3_500_000_000_000}]
        result = repo.save(updated)

        stocks_by_ticker = {s["ticker"]: s for s in result["stocks"]}
        assert stocks_by_ticker["AAPL"]["market_cap"] == 3_500_000_000_000

    def test_upsert_does_not_create_duplicates(self, tmp_path):
        repo = _make_repo(tmp_path)
        repo.save(_valid_records())
        repo.save(_valid_records())

        # Should still be exactly 3 rows, not 6
        result = repo.save(_valid_records())
        assert len(result["stocks"]) == 3


# ── Validation at repository level ──────────────────────────────────────────

class TestRepositoryValidation:
    """The repository re-validates as defence in depth."""

    def test_rejects_records_with_missing_fields(self, tmp_path):
        repo = _make_repo(tmp_path)
        bad_records = [
            {"ticker": "BAD", "name": None, "sector": "Tech", "market_cap": 100},
        ]
        result = repo.save(bad_records)

        assert result["valid_count"] == 0
        assert result["skipped_count"] == 1

    def test_rejects_records_with_negative_market_cap(self, tmp_path):
        repo = _make_repo(tmp_path)
        bad_records = [
            {"ticker": "BAD", "name": "Bad Corp", "sector": "Tech", "market_cap": -100},
        ]
        result = repo.save(bad_records)

        assert result["valid_count"] == 0
        assert result["skipped_count"] == 1


# ── Deduplication ───────────────────────────────────────────────────────────

class TestDeduplication:
    """Duplicate tickers within a single batch are collapsed."""

    def test_duplicate_tickers_in_batch_are_collapsed(self, tmp_path):
        repo = _make_repo(tmp_path)
        records = [
            {"ticker": "AAPL", "name": "Apple v1", "sector": "Technology", "market_cap": 1_000},
            {"ticker": "AAPL", "name": "Apple v2", "sector": "Technology", "market_cap": 2_000},
        ]
        result = repo.save(records)

        assert result["duplicate_count"] == 1
        assert result["valid_count"] == 1  # collapsed to one
        # Last-write-wins
        assert result["stocks"][0]["market_cap"] == 2_000


# ── Stale detection ─────────────────────────────────────────────────────────

class TestStaleDetection:
    """Tickers not refreshed should be marked as stale."""

    def test_missing_ticker_is_marked_stale(self, tmp_path):
        repo = _make_repo(tmp_path)

        # First run: insert AAPL and MSFT
        repo.save(
            _valid_records()[:2],
            expected_tickers=["AAPL", "MSFT"],
        )

        # Second run: only AAPL is in the watchlist
        result = repo.save(
            [_valid_records()[0]],
            expected_tickers=["AAPL"],
        )

        # MSFT should be stale — only AAPL should appear in active stocks
        active_tickers = [s["ticker"] for s in result["stocks"]]
        assert "AAPL" in active_tickers
        assert "MSFT" not in active_tickers


# ── Audit logging ───────────────────────────────────────────────────────────

class TestAuditLogging:
    """Each save() call creates an ingestion_runs audit row."""

    def test_ingestion_run_is_logged(self, tmp_path):
        repo = _make_repo(tmp_path)
        repo.save(_valid_records())

        # Directly query the audit table
        conn = sqlite3.connect(str(tmp_path / "test.sqlite3"))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM ingestion_runs").fetchall()
        conn.close()

        assert len(rows) == 1
        assert dict(rows[0])["valid_count"] == 3
        assert dict(rows[0])["requested_count"] == 3
