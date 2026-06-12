import yfinance as yf

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def fetch_stock(ticker: str):

    info = yf.Ticker(ticker).info

    return {
        "ticker": ticker,
        "name": info.get("longName"),
        "sector": info.get("sector"),
        "market_cap": info.get("marketCap")
    }