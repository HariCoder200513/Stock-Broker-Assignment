"""
Unit tests for the data-quality validator.

These tests verify that the validator correctly accepts clean records
and rejects records with missing fields, invalid types, bad ticker
formats, and edge-case market cap values.

No I/O, no mocks — the validator is a pure function.
"""

import pytest
from validator.stock_validator import validate_stock, validation_errors


# ── Fixtures ────────────────────────────────────────────────────────────────

def _valid_record() -> dict:
    """A known-good record that should always pass validation."""
    return {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology",
        "market_cap": 3_000_000_000_000,
    }


# ── Happy path ──────────────────────────────────────────────────────────────

class TestValidRecords:
    """Records that should pass all validation checks."""

    def test_complete_record_is_valid(self):
        assert validate_stock(_valid_record()) is True

    def test_errors_list_is_empty_for_valid_record(self):
        assert validation_errors(_valid_record()) == []

    def test_float_whole_number_market_cap_is_accepted(self):
        """Market cap from yfinance sometimes arrives as 3.0e12."""
        record = _valid_record()
        record["market_cap"] = 3_000_000_000_000.0
        assert validate_stock(record) is True


# ── Missing fields ──────────────────────────────────────────────────────────

class TestMissingFields:
    """Each required field must be present and non-empty."""

    @pytest.mark.parametrize("field", ["ticker", "name", "sector", "market_cap"])
    def test_none_field_is_rejected(self, field):
        record = _valid_record()
        record[field] = None
        assert validate_stock(record) is False

    @pytest.mark.parametrize("field", ["ticker", "name", "sector"])
    def test_empty_string_field_is_rejected(self, field):
        record = _valid_record()
        record[field] = ""
        assert validate_stock(record) is False

    @pytest.mark.parametrize("field", ["ticker", "name", "sector"])
    def test_whitespace_only_field_is_rejected(self, field):
        record = _valid_record()
        record[field] = "   "
        assert validate_stock(record) is False

    def test_missing_key_entirely_is_rejected(self):
        record = _valid_record()
        del record["sector"]
        assert validate_stock(record) is False

    def test_none_record_is_rejected(self):
        errors = validation_errors(None)
        assert len(errors) > 0

    def test_non_dict_record_is_rejected(self):
        errors = validation_errors("not a dict")
        assert len(errors) > 0


# ── Ticker format ───────────────────────────────────────────────────────────

class TestTickerFormat:
    """Ticker must be 1-5 uppercase ASCII letters."""

    def test_numeric_ticker_is_rejected(self):
        record = _valid_record()
        record["ticker"] = "12345"
        assert validate_stock(record) is False

    def test_ticker_with_special_chars_is_rejected(self):
        record = _valid_record()
        record["ticker"] = "A.BC"
        assert validate_stock(record) is False

    def test_ticker_too_long_is_rejected(self):
        record = _valid_record()
        record["ticker"] = "ABCDEF"
        assert validate_stock(record) is False


# ── Market cap validation ───────────────────────────────────────────────────

class TestMarketCap:
    """Market cap must be a positive number."""

    def test_zero_market_cap_is_rejected(self):
        record = _valid_record()
        record["market_cap"] = 0
        assert validate_stock(record) is False

    def test_negative_market_cap_is_rejected(self):
        record = _valid_record()
        record["market_cap"] = -1_000_000
        assert validate_stock(record) is False

    def test_string_market_cap_is_rejected(self):
        record = _valid_record()
        record["market_cap"] = "not a number"
        assert validate_stock(record) is False

    def test_positive_integer_market_cap_is_valid(self):
        record = _valid_record()
        record["market_cap"] = 1
        assert validate_stock(record) is True


# ── Name validation ─────────────────────────────────────────────────────────

class TestNameValidation:
    """Name must be a reasonable-length, non-empty string."""

    def test_excessively_long_name_is_rejected(self):
        record = _valid_record()
        record["name"] = "A" * 201
        assert validate_stock(record) is False

    def test_max_length_name_is_accepted(self):
        record = _valid_record()
        record["name"] = "A" * 200
        assert validate_stock(record) is True
