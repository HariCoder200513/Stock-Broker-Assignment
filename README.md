# US Stocks Dashboard - Market Data Ingestion Pipeline

A robust, modular ingestion pipeline that fetches real-time market data for a watchlist of 200 US stocks, persists it in a clean SQLite database, and serves it via a performant web dashboard.

## 🚀 Quick Start

### Option 1: Using Docker (Recommended)
Ensure you have Docker and Docker Compose installed.
```bash
# Build and start the container
docker-compose up --build
```
Access the dashboard at: [http://127.0.0.1:5000](http://127.0.0.1:5000)

### Option 2: Local Setup
1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Run the Application**:
   ```bash
   python main.py
   ```
3. **Access the Dashboard**: [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## 🏗️ Architecture

The project follows a clean, modular architecture with strict separation of concerns:

- **Frontend (Vanilla HTML/CSS/JS)**: A responsive SPA (Single Page Application) that polls the backend, implements client-side pagination (50 per page), and provides real-time filtering/sorting.
- **API Layer (Flask)**: Serves both the static frontend and the RESTful `/stocks` endpoint.
- **Ingestion Engine**:
    - **Fetcher**: Concurrent fetchers using `ThreadPoolExecutor` and `yfinance`.
    - **Validator**: Enforces data quality and type safety.
    - **Repository**: Manages the SQLite lifecycle, deduplication, and idempotent upserts.
- **Storage (SQLite)**: A persistent file-based relational database.

---

## 🧠 Key Design Decisions & Trade-offs

### 1. SQLite vs. JSON
- **Decision**: Transitioned from simple JSON files to a structured SQLite database.
- **Rationale**: SQL provides native support for data integrity (constraints), atomic transactions, and efficient "upserts." This satisfies the requirement for keeping the database "clean" across repeated runs.

### 2. Client-Side Pagination
- **Decision**: Implemented pagination on the frontend rather than the backend.
- **Trade-off**: For 200 records, the network payload is negligible (~20KB). Fetching all data at once allows for **instant** client-side searching and sorting without additional server round-trips, providing a superior UX.

### 3. Concurrency vs. Rate Limiting
- **Decision**: Used 10 threads (`MAX_WORKERS`) for fetching.
- **Trade-off**: Higher concurrency would speed up the backend, but significantly increases the risk of being blocked by Yahoo Finance (429 Rate Limits). 10 workers provide a sensible balance between speed and reliability.

### 4. Structured JSON Logging
- **Decision**: Replaced standard string logging with structured JSON logs.
- **Rationale**: Allows for machine-readable telemetry (important for ingestion pipelines) and makes it easier to track failure patterns and retry efficiency.

---

## 🗄️ Database Schema & Rationale

The schema is defined in `persistence/schema.py`.

### DDL (Data Definition Language)
```sql
CREATE TABLE IF NOT EXISTS market_data (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT NOT NULL,
    market_cap INTEGER NOT NULL CHECK (market_cap > 0),
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    is_stale INTEGER NOT NULL DEFAULT 0,
    stale_since TEXT
);

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
);
```

### Rationale
- **Primary Key (`ticker`)**: Ensures absolute deduplication. Each stock has exactly one "source of truth" record.
- **Constraints**: `NOT NULL` and `CHECK` constraints act as a final layer of defense for data integrity.
- **Audit Logging (`ingestion_runs`)**: Tracks the health of the pipeline over time. It allows us to monitor how many stocks are failing vs. succeeding in each 30-second window.
- **Stale Tracking**: Instead of deleting data, we use `is_stale`. This preserves historical knowledge of a stock while allowing the UI to only show currently active tickers.

---


