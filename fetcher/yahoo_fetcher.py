"""
Yahoo Finance data fetcher with production-grade resilience.

Design goals:
  1. Isolate all upstream I/O behind a single class so the rest of the
     codebase never imports yfinance directly.
  2. Enforce per-request timeouts — yfinance can hang indefinitely on
     slow networks or unresponsive endpoints.
  3. Classify errors as transient (retryable) vs. permanent so the retry
     decorator only retries things that might succeed on a second attempt.
  4. Return raw dicts — validation is the next layer's responsibility.

Retry strategy (via tenacity):
  • Up to FETCH_RETRY_ATTEMPTS attempts per ticker.
  • Exponential back-off: 1 s → 2 s → 4 s (capped at 8 s).
  • Only TransientMarketDataError triggers a retry; permanent errors
    (empty ticker, delisted stock) fail immediately.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Optional

import yfinance as yf
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import FETCH_RETRY_ATTEMPTS, FETCH_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


# ── Custom Exceptions ───────────────────────────────────────────────────────

class MarketDataError(Exception):
    """Base error for all market-data fetch failures."""


class TransientMarketDataError(MarketDataError):
    """
    Raised for retryable failures: timeouts, rate limits, network blips.

    The retry decorator checks for this type specifically — any other
    exception propagates immediately without consuming retry budget.
    """


# ── Internal helpers ────────────────────────────────────────────────────────

def _load_yahoo_info(ticker: str) -> dict[str, Any]:
    """
    Call the yfinance API for a single ticker.

    This function runs inside a separate thread so that the main thread
    can enforce a wall-clock timeout via Future.result(timeout=…).
    
    Attempts multiple fallback strategies:
    1. Primary: info dict from standard endpoint
    2. Fallback: fast_info if primary returns empty
    """
    ticker_obj = yf.Ticker(ticker)
    info = ticker_obj.info
    
    # If we get an empty or stub response, try fast_info as a fallback
    # (useful for some delisted or partially indexed tickers like SQ)
    if not info or len(info) < 5:
        try:
            fast_info = ticker_obj.fast_info
            if fast_info and len(fast_info) > 0:
                # Merge fast_info into info, preferring fast_info values
                info = {**info, **fast_info}
        except Exception:
            # If fast_info fails, just stick with the original info
            pass
    
    return info


def _is_rate_limit_error(error: Exception) -> bool:
    """
    Heuristic check for HTTP 429 / rate-limit errors.

    yfinance does not expose structured HTTP status codes, so we
    inspect the stringified exception for known phrases.
    """
    message = str(error).lower()
    return any(
        phrase in message
        for phrase in ("rate limit", "too many requests", "429")
    )


# ── Fetcher Class ───────────────────────────────────────────────────────────

class YahooFinanceFetcher:
    """
    Fetches market data for a single ticker from Yahoo Finance.

    Each call spins up a short-lived ThreadPoolExecutor with one worker
    so we can enforce a hard timeout on the yfinance I/O.  This is
    intentional: yfinance uses requests internally and does not accept
    its own timeout parameter.
    """

    def __init__(self, timeout_seconds: int = FETCH_TIMEOUT_SECONDS):
        self.timeout_seconds = timeout_seconds

    def fetch(self, ticker: str) -> dict[str, Any]:
        """
        Fetch market data for *ticker* and return a raw dict.

        Returns:
            {"ticker": …, "name": …, "sector": …, "market_cap": …}

        Raises:
            MarketDataError: if the ticker is empty (permanent — no retry).
            TransientMarketDataError: on timeout, rate limit, network error,
                or incomplete upstream response (all retryable).
        """
        normalized_ticker = ticker.strip().upper()

        if not normalized_ticker:
            raise MarketDataError("Ticker cannot be empty.")

        # ── Step 1: Call the API with a hard timeout ────────────────────
        try:
            info = self._fetch_info_with_timeout(normalized_ticker)
        except TimeoutError as error:
            raise TransientMarketDataError(
                f"Timed out fetching {normalized_ticker} "
                f"after {self.timeout_seconds}s"
            ) from error
        except Exception as error:
            # yfinance wraps HTTP/network errors in generic exceptions.
            # Classify 429s explicitly; treat everything else as transient
            # too, since short network blips are the most common cause.
            if _is_rate_limit_error(error):
                raise TransientMarketDataError(
                    f"Rate limited fetching {normalized_ticker}"
                ) from error
            raise TransientMarketDataError(
                f"Network/API error fetching {normalized_ticker}: {error}"
            ) from error

        # ── Step 2: Guard against empty / stub responses ────────────────
        if not info:
            raise TransientMarketDataError(
                f"Empty response for {normalized_ticker}"
            )

        # ── Step 3: Extract the four required fields ────────────────────
        record = {
            "ticker": normalized_ticker,
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "market_cap": info.get("marketCap"),
        }

        # If any required field is missing the upstream gave us a partial
        # response — mark as transient so we retry (Yahoo occasionally
        # returns stubs for valid tickers during high load).
        missing_fields = [k for k, v in record.items() if v in (None, "")]
        if missing_fields:
            raise TransientMarketDataError(
                f"Partial response for {normalized_ticker}; "
                f"missing {', '.join(missing_fields)}"
            )

        return record

    # ── Private: timeout-wrapped I/O ────────────────────────────────────

    def _fetch_info_with_timeout(self, ticker: str) -> dict[str, Any]:
        """
        Run the yfinance call in a background thread and impose a hard
        wall-clock timeout.

        We create a fresh single-thread executor per call to avoid
        thread-safety issues with yfinance's internal state.  The
        overhead is negligible compared to the network round-trip.
        """
        executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix=f"yahoo-{ticker}",
        )
        future = executor.submit(_load_yahoo_info, ticker)

        try:
            return future.result(timeout=self.timeout_seconds)
        except TimeoutError:
            future.cancel()
            raise
        finally:
            executor.shutdown(wait=False, cancel_futures=True)


# ── Module-level singleton ──────────────────────────────────────────────────
# Re-used by fetch_stock() below so we don't re-create the fetcher object
# on every call.

_default_fetcher = YahooFinanceFetcher()


# ── Retry-decorated public API ──────────────────────────────────────────────

def _track_retry(retry_state):
    """
    Tenacity *after* callback — records how many retries were consumed
    in the caller-supplied ``stats`` dict for observability.
    """
    if retry_state.attempt_number > 1:
        stats = retry_state.args[1] if len(retry_state.args) > 1 else None
        if isinstance(stats, dict):
            stats["retries"] = retry_state.attempt_number - 1


@retry(
    stop=stop_after_attempt(FETCH_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(TransientMarketDataError),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=_track_retry,
    reraise=True,
)
def fetch_stock(ticker: str, stats: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """
    Public entry point — fetch one ticker with automatic retries.

    Args:
        ticker: US equity symbol (e.g. "AAPL").
        stats:  Optional mutable dict; if provided, a ``retries`` key
                is injected with the number of retry attempts consumed.

    Returns:
        A raw dict with keys: ticker, name, sector, market_cap.

    Raises:
        TransientMarketDataError: after all retry attempts are exhausted.
        MarketDataError: on permanent errors (e.g. empty ticker string).
    """
    return _default_fetcher.fetch(ticker)
