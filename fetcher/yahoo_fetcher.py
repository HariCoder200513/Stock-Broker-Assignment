import yfinance as yf
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError
)
import logging

from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from config import (
    FETCH_RETRY_ATTEMPTS,
    FETCH_TIMEOUT_SECONDS
)


logger = logging.getLogger(__name__)


class MarketDataError(Exception):
    """Base error for failures while reading market data."""


class TransientMarketDataError(MarketDataError):
    """Raised for retryable failures such as timeouts and rate limits."""


def _load_yahoo_info(ticker: str) -> dict:
    return yf.Ticker(ticker).info


def _is_rate_limit_error(error: Exception) -> bool:
    message = str(error).lower()

    return any(
        phrase in message
        for phrase in (
            "rate limit",
            "too many requests",
            "429"
        )
    )


class YahooFinanceFetcher:
    def __init__(
        self,
        timeout_seconds: int = FETCH_TIMEOUT_SECONDS
    ):
        self.timeout_seconds = timeout_seconds

    def fetch(self, ticker: str) -> dict:
        normalized_ticker = ticker.strip().upper()

        if not normalized_ticker:
            raise MarketDataError("Ticker cannot be empty.")

        try:
            info = self._fetch_info_with_timeout(
                normalized_ticker
            )
        except TimeoutError as error:
            raise TransientMarketDataError(
                f"Timed out fetching {normalized_ticker}"
            ) from error
        except Exception as error:
            # yfinance wraps several HTTP/network cases in generic exceptions.
            # Treat them as transient so short network fluctuations and 429s
            # get retried before the route reports a skipped ticker.
            if _is_rate_limit_error(error):
                raise TransientMarketDataError(
                    f"Rate limited fetching {normalized_ticker}"
                ) from error

            raise TransientMarketDataError(
                f"Network/API error fetching {normalized_ticker}: {error}"
            ) from error

        if not info:
            raise TransientMarketDataError(
                f"Empty response for {normalized_ticker}"
            )

        record = {
            "ticker": normalized_ticker,
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "market_cap": info.get("marketCap")
        }

        missing_fields = [
            key
            for key, value in record.items()
            if value in (None, "")
        ]

        if missing_fields:
            raise TransientMarketDataError(
                f"Partial response for {normalized_ticker}; "
                f"missing {', '.join(missing_fields)}"
            )

        return record

    def _fetch_info_with_timeout(self, ticker: str) -> dict:
        executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix=f"yahoo-{ticker}"
        )
        future = executor.submit(
            _load_yahoo_info,
            ticker
        )

        try:
            return future.result(
                timeout=self.timeout_seconds
            )
        except TimeoutError:
            future.cancel()
            raise
        finally:
            executor.shutdown(
                wait=False,
                cancel_futures=True
            )


_default_fetcher = YahooFinanceFetcher()


@retry(
    stop=stop_after_attempt(FETCH_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(TransientMarketDataError),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def fetch_stock(ticker: str) -> dict:
    return _default_fetcher.fetch(ticker)
