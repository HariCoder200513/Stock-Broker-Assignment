"""
Database schema definitions for the market-data ingestion pipeline.

Two tables:
  1. ``market_data``    — one row per ticker, upserted on every run.
  2. ``ingestion_runs`` — one row per pipeline execution for audit/observability.

Design rationale:
  • PRIMARY KEY on ``ticker`` guarantees exactly one row per stock — no
    duplicates can ever reach the table, even under concurrent writes.
  • NOT NULL + CHECK constraints act as a *final safety net* after the
    application-level validator.  Defence in depth: even if a bug slips
    past the validator, the DB will reject the row.
  • ``is_stale`` + ``stale_since`` allow soft-deletion: tickers that stop
    appearing in the watchlist are flagged rather than removed, preserving
    historical data.
  • WAL journal mode (set at connection time) allows concurrent reads
    during writes — important for the Flask route that serves data while
    an ingestion run is in progress.
"""


# ── Main data table ─────────────────────────────────────────────────────────
STOCKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS market_data (
    ticker       TEXT    PRIMARY KEY,
    name         TEXT    NOT NULL,
    sector       TEXT    NOT NULL,
    market_cap   INTEGER NOT NULL CHECK (market_cap > 0),
    first_seen_at TEXT   NOT NULL,
    last_seen_at  TEXT   NOT NULL,
    is_stale     INTEGER NOT NULL DEFAULT 0,
    stale_since  TEXT
)
"""

# ── Audit / observability table ─────────────────────────────────────────────
INGESTION_RUNS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT    NOT NULL,
    completed_at    TEXT    NOT NULL,
    requested_count INTEGER NOT NULL,
    valid_count     INTEGER NOT NULL,
    duplicate_count INTEGER NOT NULL,
    upserted_count  INTEGER NOT NULL,
    stale_count     INTEGER NOT NULL,
    skipped_count   INTEGER NOT NULL
)
"""

# ── Index for the "show active stocks" query ────────────────────────────────
# The dashboard always filters on is_stale = 0, so an index on
# (is_stale, last_seen_at) avoids a full table scan.
STOCKS_BY_STATUS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_market_data_status
ON market_data (is_stale, last_seen_at)
"""


def initialize_schema(connection) -> None:
    """
    Idempotently create all tables and indexes.

    Safe to call on every connection — ``IF NOT EXISTS`` ensures no-ops
    on subsequent runs.
    """
    connection.execute(STOCKS_TABLE_SQL)
    connection.execute(INGESTION_RUNS_TABLE_SQL)
    connection.execute(STOCKS_BY_STATUS_INDEX_SQL)
