from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)

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

import time


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


def run_pipeline():

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

    print(
        f"""
Requested : {len(TICKERS)}
Valid     : {len(valid_records)}
Time      : {elapsed}s
"""
    )


if __name__ == "__main__":

    run_pipeline()