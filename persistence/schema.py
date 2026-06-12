STOCKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS market_data (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT NOT NULL,
    market_cap INTEGER NOT NULL CHECK (market_cap > 0),
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    is_stale INTEGER NOT NULL DEFAULT 0,
    stale_since TEXT
)
"""

INGESTION_RUNS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    requested_count INTEGER NOT NULL,
    valid_count INTEGER NOT NULL,
    duplicate_count INTEGER NOT NULL,
    upserted_count INTEGER NOT NULL,
    stale_count INTEGER NOT NULL,
    skipped_count INTEGER NOT NULL
)
"""

STOCKS_BY_STATUS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_market_data_status
ON market_data (is_stale, last_seen_at)
"""


def initialize_schema(connection) -> None:
    connection.execute(STOCKS_TABLE_SQL)
    connection.execute(INGESTION_RUNS_TABLE_SQL)
    connection.execute(STOCKS_BY_STATUS_INDEX_SQL)
