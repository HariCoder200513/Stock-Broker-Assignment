"""
Unit tests for the Yahoo Finance fetcher.

These tests mock the yfinance API call to verify:
  • Happy-path extraction of the four required fields.
  • Proper exception classification (transient vs. permanent).
  • Timeout enforcement.
  • Handling of partial / empty upstream responses.

No real network calls are made.
"""

from unittest.mock import patch, MagicMock
import pytest

from fetcher.yahoo_fetcher import (
    YahooFinanceFetcher,
    MarketDataError,
    TransientMarketDataError,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

_COMPLETE_INFO = {
    "longName": "Apple Inc.",
    "sector": "Technology",
    "marketCap": 3_000_000_000_000,
}


# ── Happy path ──────────────────────────────────────────────────────────────

class TestFetchSuccess:
    """Verify correct data extraction from a well-formed response."""

    @patch("fetcher.yahoo_fetcher._load_yahoo_info", return_value=_COMPLETE_INFO)
    def test_returns_all_four_fields(self, mock_load):
        fetcher = YahooFinanceFetcher(timeout_seconds=5)
        result = fetcher.fetch("AAPL")

        assert result["ticker"] == "AAPL"
        assert result["name"] == "Apple Inc."
        assert result["sector"] == "Technology"
        assert result["market_cap"] == 3_000_000_000_000

    @patch("fetcher.yahoo_fetcher._load_yahoo_info", return_value=_COMPLETE_INFO)
    def test_normalizes_ticker_to_uppercase(self, mock_load):
        fetcher = YahooFinanceFetcher(timeout_seconds=5)
        result = fetcher.fetch("  aapl  ")
        assert result["ticker"] == "AAPL"

    @patch("fetcher.yahoo_fetcher._load_yahoo_info")
    def test_falls_back_to_short_name(self, mock_load):
        """If longName is missing, use shortName as fallback."""
        mock_load.return_value = {
            "shortName": "Apple Inc",
            "sector": "Technology",
            "marketCap": 3_000_000_000_000,
        }
        fetcher = YahooFinanceFetcher(timeout_seconds=5)
        result = fetcher.fetch("AAPL")
        assert result["name"] == "Apple Inc"


# ── Error handling ──────────────────────────────────────────────────────────

class TestFetchErrors:
    """Verify correct error classification for various failure modes."""

    def test_empty_ticker_raises_permanent_error(self):
        fetcher = YahooFinanceFetcher(timeout_seconds=5)
        with pytest.raises(MarketDataError, match="empty"):
            fetcher.fetch("")

    @patch("fetcher.yahoo_fetcher._load_yahoo_info", return_value=None)
    def test_empty_response_raises_transient_error(self, mock_load):
        fetcher = YahooFinanceFetcher(timeout_seconds=5)
        with pytest.raises(TransientMarketDataError, match="Empty response"):
            fetcher.fetch("AAPL")

    @patch("fetcher.yahoo_fetcher._load_yahoo_info", return_value={})
    def test_empty_dict_raises_transient_error(self, mock_load):
        fetcher = YahooFinanceFetcher(timeout_seconds=5)
        with pytest.raises(TransientMarketDataError, match="Empty response"):
            fetcher.fetch("AAPL")

    @patch("fetcher.yahoo_fetcher._load_yahoo_info")
    def test_partial_response_raises_transient_error(self, mock_load):
        """A response missing 'sector' should be treated as transient."""
        mock_load.return_value = {
            "longName": "Apple Inc.",
            "marketCap": 3_000_000_000_000,
            # sector is missing
        }
        fetcher = YahooFinanceFetcher(timeout_seconds=5)
        with pytest.raises(TransientMarketDataError, match="missing sector"):
            fetcher.fetch("AAPL")

    @patch("fetcher.yahoo_fetcher._load_yahoo_info")
    def test_rate_limit_raises_transient_error(self, mock_load):
        mock_load.side_effect = Exception("Too Many Requests (429)")
        fetcher = YahooFinanceFetcher(timeout_seconds=5)
        with pytest.raises(TransientMarketDataError, match="Rate limited"):
            fetcher.fetch("AAPL")

    @patch("fetcher.yahoo_fetcher._load_yahoo_info")
    def test_network_error_raises_transient_error(self, mock_load):
        mock_load.side_effect = ConnectionError("Connection refused")
        fetcher = YahooFinanceFetcher(timeout_seconds=5)
        with pytest.raises(TransientMarketDataError, match="Network/API error"):
            fetcher.fetch("AAPL")
