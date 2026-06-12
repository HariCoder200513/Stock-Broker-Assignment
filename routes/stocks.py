from flask import Blueprint
from flask import jsonify

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)

import time
import logging

from config import (
    TICKERS,
    MAX_WORKERS
)

from fetcher.yahoo_fetcher import (
    fetch_stock
)

from validator.stock_validator import (
    validation_errors
)

from persistence.repository import (
    StockRepository
)

stocks_bp = Blueprint(
    "stocks",
    __name__
)

logger = logging.getLogger(__name__)


def process_stock(ticker):
    stats = {"retries": 0}
    try:
        record = fetch_stock(ticker, stats)
        errors = validation_errors(record)

        if errors:
            return {
                "ticker": ticker,
                "status": "validation_failed",
                "message": "; ".join(errors),
                "retries": stats["retries"]
            }

        record["retries"] = stats["retries"]
        record["status"] = "success"
        return record

    except Exception as e:
        return {
            "ticker": ticker,
            "status": "fetch_failed",
            "message": str(e),
            "retries": stats["retries"]
        }


@stocks_bp.route("/stocks")
def get_stocks():
    start_time = time.time()
    results = []

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:
        futures = {
            executor.submit(process_stock, ticker): ticker
            for ticker in TICKERS
        }

        for future in as_completed(futures):
            results.append(future.result())

    valid_records = [r for r in results if r["status"] == "success"]
    
    repository = StockRepository()
    snapshot = repository.save(
        valid_records,
        expected_tickers=TICKERS
    )

    elapsed = round(time.time() - start_time, 2)
    
    total_retries = sum(r.get("retries", 0) for r in results)

    return jsonify({
        "requested": len(TICKERS),
        "returned": len(valid_records),
        "failed": len(TICKERS) - len(valid_records),
        "total_retries": total_retries,
        "persisted_at": snapshot["completed_at"],
        "time_taken_seconds": elapsed,
        "stocks": results # Send all results to show failures/retries
    })
