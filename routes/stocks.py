from flask import Blueprint
from flask import jsonify

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)

import time

from config import (
    TICKERS,
    MAX_WORKERS
)

from fetcher.yahoo_fetcher import (
    fetch_stock
)

from validator.stock_validator import (
    validate_stock
)

from persistence.repository import (
    StockRepository
)

stocks_bp = Blueprint(
    "stocks",
    __name__
)


def process_stock(ticker):

    try:

        record = fetch_stock(ticker)

        if not validate_stock(record):

            print(
                f"Validation failed: {ticker}"
            )

            return None

        return record

    except Exception as e:

        print(
            f"Failed {ticker}: {e}"
        )

        return None


@stocks_bp.route("/stocks")
def get_stocks():

    start_time = time.time()

    valid_records = []

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {
            executor.submit(
                process_stock,
                ticker
            ): ticker
            for ticker in TICKERS
        }

        for future in as_completed(
            futures
        ):

            result = future.result()

            if result:
                valid_records.append(
                    result
                )

    repository = StockRepository()

    repository.save(
        valid_records
    )

    elapsed = round(
        time.time() - start_time,
        2
    )

    return jsonify({
        "requested": len(TICKERS),
        "returned": len(valid_records),
        "time_taken_seconds": elapsed,
        "stocks": valid_records
    })