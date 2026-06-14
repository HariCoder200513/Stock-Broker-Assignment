"""
Ingestion pipeline orchestrator.

This module coordinates the three stages of the ingestion pipeline:
  1. **Fetch** — pull raw market data from Yahoo Finance (concurrent).
  2. **Validate** — filter out records with missing or invalid fields.
  3. **Persist** — upsert clean records into SQLite and mark stale rows.

Separating the orchestrator from the Flask route has two benefits:
  • The pipeline can be tested end-to-end without spinning up a web server.
  • It can be invoked from a CLI, a cron job, or a Celery task — not just
    an HTTP request.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from config import MAX_WORKERS, TICKERS, SKIP_TICKERS
from constants import STATUS_SUCCESS, STATUS_VALIDATION_FAILED, STATUS_FETCH_FAILED, STATUS_SKIPPED
from fetcher.yahoo_fetcher import fetch_stock
from persistence.repository import StockRepository
from validator.stock_validator import validation_errors

logger = logging.getLogger(__name__)


def _process_single_ticker(ticker: str) -> dict[str, Any]:
    """
    Fetch and validate a single ticker.

    Returns a dict that always contains ``ticker`` and ``status``.
    On success the dict also contains ``name``, ``sector``, ``market_cap``.
    On failure it contains ``message`` with the error description.
    """
    stats = {"retries": 0}

    try:
        record = fetch_stock(ticker, stats)
        errors = validation_errors(record)

        if errors:
            return {
                "ticker": ticker,
                "status": STATUS_VALIDATION_FAILED,
                "message": "; ".join(errors),
                "retries": stats["retries"],
            }

        record["retries"] = stats["retries"]
        record["status"] = STATUS_SUCCESS
        return record

    except Exception as exc:
        return {
            "ticker": ticker,
            "status": STATUS_FETCH_FAILED,
            "message": str(exc),
            "retries": stats["retries"],
        }


def run_ingestion(
    tickers: list[str] = None,
    max_workers: int = None,
) -> dict[str, Any]:
    """
    Execute one full ingestion run.

    Args:
        tickers:     List of ticker symbols to fetch.  Defaults to the
                     configured watchlist in ``config.TICKERS``.
        max_workers: Thread-pool size.  Defaults to ``config.MAX_WORKERS``.

    Returns:
        A dict containing:
          - ``requested``, ``returned``, ``failed``, ``skipped``, ``stale_count``, ``total_retries``,
            ``time_taken_seconds`` — top-level summary stats.
          - ``persisted_at`` — ISO-8601 timestamp of the DB snapshot.
          - ``stocks`` — the full list of per-ticker results (including
            failures, so the UI can show status badges).
    """
    tickers = tickers or TICKERS
    max_workers = max_workers or MAX_WORKERS

    start_time = time.time()
    results: list[dict] = []
    
    # ── Filter out skipped tickers (known problematic ones) ────────────────
    active_tickers = [t for t in tickers if t.upper() not in SKIP_TICKERS]
    skipped_tickers = [t for t in tickers if t.upper() in SKIP_TICKERS]

    # ── Step 1: Concurrent fetch + validate ─────────────────────────────────
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_single_ticker, t): t
            for t in active_tickers
        }
        for future in as_completed(futures):
            results.append(future.result())

    # ── Step 2: Add skipped tickers to results with skip status ────────────
    for ticker in skipped_tickers:
        results.append({
            "ticker": ticker,
            "status": STATUS_SKIPPED,
            "message": f"Ticker {ticker} is in the skip list (known issue with upstream)",
            "retries": 0,
        })

    # ── Step 3: Separate successes from failures ────────────────────────────
    valid_records = [r for r in results if r["status"] == STATUS_SUCCESS]

    # ── Step 4: Persist to SQLite ───────────────────────────────────────────
    repository = StockRepository()
    snapshot = repository.save(valid_records, expected_tickers=active_tickers)

    elapsed = round(time.time() - start_time, 2)
    total_retries = sum(r.get("retries", 0) for r in results)
    failed_count = len([r for r in results if r["status"] in (STATUS_FETCH_FAILED, STATUS_VALIDATION_FAILED)])

    summary = {
        "requested": len(tickers),
        "skipped": len(skipped_tickers),
        "active": len(active_tickers),
        "returned": len(valid_records),
        "failed": failed_count,
        "stale_count": snapshot["stale_count"],
        "total_retries": total_retries,
        "time_taken_seconds": elapsed,
    }

    logger.info(
        "Ingestion run completed",
        extra={"extra_fields": summary},
    )

    return {
        **summary,
        "persisted_at": snapshot["completed_at"],
        "stocks": results,
    }
