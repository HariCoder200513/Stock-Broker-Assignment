# US Stocks Dashboard — Market Data Ingestion Pipeline

A production-minded ingestion service that fetches real-time market data for 50+ US-listed equities, validates every record, and persists clean data to SQLite with strong integrity guarantees.

## 🚀 Quick Start

### Option 1: Docker (Recommended)
```bash
docker compose up --build
```
Access the dashboard at: [http://127.0.0.1:5000](http://127.0.0.1:5000)

### Option 2: Local
```bash
pip install -r requirements.txt
python main.py
```

### Run Tests
```bash
python -m pytest tests/ -v
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Flask Route (/stocks)                    │
│                  (thin HTTP adapter only)                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                 Orchestrator (pipeline.py)                    │
│         Coordinates: Fetch → Validate → Persist              │
│         Runnable from HTTP, CLI, or cron                     │
└───────┬──────────────────┬──────────────────┬───────────────┘
        │                  │                  │
┌───────▼───────┐  ┌───────▼───────┐  ┌──────▼────────┐
│    Fetcher    │  │   Validator   │  │  Repository   │
│ yahoo_fetcher │  │stock_validator│  │  repository   │
│               │  │               │  │               │
│ • Timeout     │  │ • Required    │  │ • Upsert      │
│ • Retry w/    │  │   fields      │  │ • Dedup       │
│   backoff     │  │ • Ticker fmt  │  │ • Stale       │
│ • Rate-limit  │  │ • Type checks │  │   detection   │
│   detection   │  │ • Range       │  │ • Audit log   │
└───────────────┘  │   validation  │  │ • Transactions│
                   └───────────────┘  └───────────────┘
```

Each layer is **independently testable** — 43 unit tests verify all three in isolation.

---

## 📁 Project Structure

```
├── config.py                  # Tuneable constants (env-var overridable)
├── main.py                    # Flask app entry point
├── logger_config.py           # Structured JSON logging
├── fetcher/
│   └── yahoo_fetcher.py       # yfinance adapter with retry/timeout
├── validator/
│   └── stock_validator.py     # Data-quality checks (pure functions)
├── persistence/
│   ├── schema.py              # DDL + constraint definitions
│   └── repository.py          # SQLite upsert, dedup, stale detection
├── orchestrator/
│   └── pipeline.py            # Fetch→Validate→Persist coordination
├── models/
│   └── stock.py               # Frozen dataclass for type safety
├── routes/
│   └── stocks.py              # Thin Flask blueprint
├── tests/
│   ├── test_fetcher.py        # 9 tests — mocked API, error classification
│   ├── test_validator.py      # 22 tests — every validation rule
│   └── test_repository.py     # 12 tests — upsert, dedup, stale, audit
├── index.html / script.js / style.css   # Dashboard frontend
├── Dockerfile / docker-compose.yml      # Container deployment
└── requirements.txt           # Minimal, curated dependencies
```

---

## 🧠 Key Design Decisions

### 1. Error Classification (Transient vs. Permanent)
Not all failures deserve a retry. The fetcher distinguishes:
- **Transient** (retried): timeouts, rate limits, network blips, partial responses
- **Permanent** (fail immediately): empty ticker, invalid input

This avoids wasting retry budget on errors that will never succeed.

### 2. Exponential Back-off
Retries use `1s → 2s → 4s` delays (capped at 8s) to avoid hammering a rate-limited API. Implemented via `tenacity` with structured logging on each retry attempt.

### 3. Defence in Depth
Validation runs **twice**: once in the orchestrator (to avoid persisting garbage) and again inside the repository (the DB layer doesn't trust upstream callers). The SQLite schema adds a third layer with `NOT NULL` and `CHECK` constraints.

### 4. Idempotent Upserts
The `ON CONFLICT(ticker) DO UPDATE` pattern means the service can run repeatedly without creating duplicates. The `first_seen_at` timestamp is preserved; `last_seen_at` is refreshed.

### 5. Soft Deletion (Stale Tracking)
Tickers removed from the watchlist are flagged `is_stale = 1` rather than deleted. This preserves historical data while keeping the dashboard clean.

### 6. Orchestrator Separation
The pipeline logic lives in `orchestrator/pipeline.py`, not in the Flask route. This means the same ingestion logic can be triggered from a CLI script, a cron job, or a Celery task — not just an HTTP request.

---

## 🗄️ Database Schema

```sql
CREATE TABLE IF NOT EXISTS market_data (
    ticker       TEXT    PRIMARY KEY,
    name         TEXT    NOT NULL,
    sector       TEXT    NOT NULL,
    market_cap   INTEGER NOT NULL CHECK (market_cap > 0),
    first_seen_at TEXT   NOT NULL,
    last_seen_at  TEXT   NOT NULL,
    is_stale     INTEGER NOT NULL DEFAULT 0,
    stale_since  TEXT
);

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
);
```

**Why these constraints?**
- `PRIMARY KEY (ticker)` — one row per stock, enforced at the DB level
- `NOT NULL` + `CHECK` — final safety net after application-level validation
- `ingestion_runs` — audit trail for pipeline health monitoring
- `is_stale` / `stale_since` — soft-delete preserves history

---

## ⚙️ Configuration

All constants are overridable via environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `MAX_WORKERS` | 25 | Thread pool size for concurrent fetches |
| `FETCH_TIMEOUT_SECONDS` | 10 | Per-ticker API call timeout |
| `FETCH_RETRY_ATTEMPTS` | 3 | Max retries before marking a ticker as failed |
| `DATABASE_PATH` | `data/market_data.sqlite3` | SQLite file location |
| `STALE_DATA_THRESHOLD_DAYS` | 7 | Days after which a stock is marked stale if not refreshed |
| `SKIP_TICKERS` | SQ | Comma-separated list of tickers to skip (known problematic ones) |

---

## 🔧 Recent Improvements

### 1. **Fallback Data Fetching**
The fetcher now uses a two-tier approach:
- Primary: Standard `info` endpoint from yfinance
- Fallback: `fast_info` endpoint if primary returns incomplete data
- This handles partial responses from Yahoo Finance during high load or for certain delisted tickers

### 2. **Graceful Handling of Problematic Tickers**
Some tickers (e.g., **SQ** after the Block acquisition) may become unavailable or delisted. These are now:
- **Skipped** during ingestion to avoid wasting retry budget
- **Tracked** in the skip list with a clear status badge
- **Configurable** via the `SKIP_TICKERS` environment variable

### 3. **Stale Data Management**
The repository now marks data as "stale" based on:
- **Timeout threshold**: Stocks not refreshed for `STALE_DATA_THRESHOLD_DAYS` (default: 7 days) are marked stale
- **Removal from watchlist**: Stocks no longer in the active ticker list are marked stale
- **Soft deletion**: Stale records are preserved (not deleted) with `is_stale=1` and `stale_since` timestamp
- **Active-only queries**: The dashboard only shows non-stale records

### How Stale Detection Works

```
On each ingestion run:
1. Records successfully fetched are upserted (is_stale cleared)
2. After upsert, the repository checks for tickers that:
   - Are NOT in the current watchlist, OR
   - Have NOT been refreshed within the threshold
3. These tickers get marked: is_stale=1, stale_since=<first time marked>
4. Subsequent queries filter out stale records (WHERE is_stale=0)
```

---

## 📊 Sample Output

After running the pipeline with SQ skipped and stale data handling:

```json
{
  "requested": 51,
  "skipped": 1,
  "active": 50,
  "returned": 50,
  "failed": 0,
  "total_retries": 2,
  "time_taken_seconds": 18.43,
  "persisted_at": "2026-06-13T11:22:46.123456+00:00",
  "stocks": [
    {
      "ticker": "AAPL",
      "status": "success",
      "name": "Apple Inc.",
      "sector": "Technology",
      "market_cap": 2850000000000,
      "retries": 0
    },
    ...
    {
      "ticker": "SQ",
      "status": "skipped",
      "message": "Ticker SQ is in the skip list (known issue with upstream)",
      "retries": 0
    }
  ]
}
```

The database contains:
- **50 active stocks** (is_stale = 0) — actively trading and recently fetched
- **Historical records** for any previously removed tickers marked as stale (is_stale = 1)

---

## 🧪 Testing the Pipeline

### Run Ingestion Manually
```bash
python3 -c "from orchestrator.pipeline import run_ingestion; import json; print(json.dumps(run_ingestion(), indent=2))"
```

### Skip a Different Ticker
```bash
SKIP_TICKERS="TSLA,PLTR" python main.py
```

### Adjust Stale Data Threshold
```bash
STALE_DATA_THRESHOLD_DAYS=30 python main.py
```

### Check Database State
```bash
sqlite3 data/market_data.sqlite3
> SELECT ticker, is_stale, stale_since FROM market_data ORDER BY ticker;
> SELECT * FROM ingestion_runs ORDER BY started_at DESC LIMIT 1;
```

---

## 📝 Error Handling Philosophy

This pipeline treats errors with **production-grade rigor**:

| Error Type | Action |
|---|---|
| **Transient** (timeout, rate limit, partial response) | Retry with exponential backoff (1s → 2s → 4s) |
| **Permanent** (empty ticker, invalid format) | Fail immediately, don't retry |
| **Problematic upstream** (delisted ticker like SQ) | Skip gracefully, track in skip list |
| **Database constraint violation** | Transaction rolls back; pipeline logs error |
| **Network blip** | Recorded in retry count; observable via audit logs |

All failures are logged with full context for debugging:
```
fetch_failed: "TransientMarketDataError: Timed out fetching TSLA after 10s"
validation_failed: "missing name, sector"
skipped: "Ticker SQ is in the skip list"
```

---

## 🚀 Production Deployment

### Docker
```bash
docker compose up --build
```

### Environment-driven Configuration
```bash
export MAX_WORKERS=50
export FETCH_TIMEOUT_SECONDS=15
export STALE_DATA_THRESHOLD_DAYS=14
export SKIP_TICKERS="SQ,DELISTED_TICKER"
export DATABASE_PATH="/data/market_data.db"
python main.py
```

---

## 📜 License

MIT
