"""
Central configuration for the market-data ingestion service.

All tuneable constants live here so they can be reviewed (or overridden via
environment variables in production) without touching business logic.
"""

import os

# ── Ticker Universe ─────────────────────────────────────────────────────────
# A curated watchlist of 50+ US-listed equities spanning mega-cap tech,
# financials, healthcare, consumer, energy, and industrials.
# Duplicates are stripped automatically at import time.
TICKERS = [
    # ── Mega-cap Technology ──
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",

    # ── Enterprise Software / Cloud ──
    "ADBE", "CRM", "ORCL", "NFLX", "INTC", "AMD", "CSCO", "IBM",

    # ── Financials ──
    "JPM", "BAC", "GS", "MS", "BLK", "V", "MA",

    # ── Consumer / Retail ──
    "WMT", "COST", "HD", "LOW", "MCD", "NKE", "DIS", "PEP", "KO",

    # ── Energy ──
    "XOM", "CVX",

    # ── Healthcare / Pharma ──
    "PFE", "MRK", "ABT", "UNH", "LLY",

    # ── Telecom ──
    "T", "VZ",

    # ── Industrials / Logistics ──
    "CAT", "GE", "UPS", "FDX",

    # ── High-Growth / Recent IPOs ──
    "UBER", "LYFT", "SQ", "SHOP", "PLTR", "SNOW", "PANW", "CRWD",
]

# Remove accidental duplicates while preserving order.
TICKERS = list(dict.fromkeys(TICKERS))

# Guard: the assignment requires a minimum of 50 tickers.
if len(TICKERS) < 50:
    raise ValueError(
        f"Watchlist has only {len(TICKERS)} tickers; at least 50 are required."
    )


# ── Concurrency ─────────────────────────────────────────────────────────────
# Controls how many tickers we fetch in parallel.  Higher values speed up the
# run but risk Yahoo Finance rate-limiting (HTTP 429).  25 workers is a safe
# middle ground for ~50 tickers.
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "25"))

# ── Fetcher Resilience ──────────────────────────────────────────────────────
# Per-ticker timeout for the Yahoo Finance API call.
FETCH_TIMEOUT_SECONDS = int(os.getenv("FETCH_TIMEOUT_SECONDS", "10"))

# Maximum retry attempts per ticker before marking it as failed.
# Uses exponential back-off (1 s → 2 s → 4 s → …) between retries.
FETCH_RETRY_ATTEMPTS = int(os.getenv("FETCH_RETRY_ATTEMPTS", "3"))

# ── Storage ─────────────────────────────────────────────────────────────────
# Path to the SQLite database file.  The directory is created automatically
# by the repository if it doesn't exist.
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/market_data.sqlite3")

# ── Stale Data Handling ──────────────────────────────────────────────────────
# Number of days after which a stock is considered "stale" if not refreshed.
# When a stock is removed from the watchlist or fails to fetch for this many
# days, it is soft-flagged as stale rather than deleted.
STALE_DATA_THRESHOLD_DAYS = int(os.getenv("STALE_DATA_THRESHOLD_DAYS", "7"))

# ── Problematic Ticker Handling ──────────────────────────────────────────────
# List of tickers known to have issues with Yahoo Finance (delisted, incomplete
# data, etc.). These tickers are skipped during ingestion to avoid repeated
# failures that consume retries and slow down the pipeline.
SKIP_TICKERS = set(
    os.getenv("SKIP_TICKERS", "").split(",") if os.getenv("SKIP_TICKERS") else []
)
# SQ (Square) was delisted from NYSE in 2024 after Block acquisition
if not SKIP_TICKERS:
    SKIP_TICKERS = {"SQ"}
