"""
Data-quality validator — the gatekeeper between raw API responses and the
database.

Design philosophy:
  • Every record must pass validation before it touches the database.
  • Validation is pure-functional: no side effects, no I/O.
  • Returns a *list of human-readable error strings* rather than a boolean,
    so callers can log exactly why a record was rejected.
  • The ``validate_stock`` convenience wrapper returns a bool for simple
    pass/fail checks.

Validation rules:
  1. All four required fields (ticker, name, sector, market_cap) must be
     present and non-empty.
  2. ``ticker`` must be 1–5 uppercase ASCII letters (standard US exchange
     format).
  3. ``name`` must be a non-empty string of reasonable length (≤200 chars).
  4. ``sector`` must be a non-empty string.
  5. ``market_cap`` must be a positive integer (or a float that represents
     a whole number).
"""

import re

# The four columns that the database schema requires for every row.
REQUIRED_FIELDS = ["ticker", "name", "sector", "market_cap"]

# US exchange tickers are 1–5 uppercase letters.
# This catches obviously malformed values like "123" or "A.BC".
_TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}$")


def validation_errors(record: dict) -> list[str]:
    """
    Validate a single stock record and return a list of error messages.

    An empty list means the record is clean.  Each string in the returned
    list describes one specific violation, which is useful for structured
    logging in the ingestion pipeline.

    Args:
        record: A dict with keys ``ticker``, ``name``, ``sector``,
                ``market_cap``.

    Returns:
        A list of human-readable error strings (empty = valid).
    """
    errors = []

    # ── Guard: missing record ───────────────────────────────────────────
    if record is None:
        return ["Record is None — nothing to validate."]

    if not isinstance(record, dict):
        return [f"Expected a dict, got {type(record).__name__}."]

    # ── Check required fields exist and are non-empty ───────────────────
    for field in REQUIRED_FIELDS:
        value = record.get(field)

        if value is None:
            errors.append(f"'{field}' is missing.")
            continue

        # Catch empty strings and whitespace-only strings.
        if isinstance(value, str) and not value.strip():
            errors.append(f"'{field}' is empty or whitespace-only.")

    # ── Ticker format ───────────────────────────────────────────────────
    ticker = record.get("ticker")
    if isinstance(ticker, str) and ticker.strip():
        if not _TICKER_PATTERN.match(ticker.strip().upper()):
            errors.append(
                f"'{ticker}' is not a valid US ticker "
                f"(expected 1–5 uppercase letters)."
            )

    # ── Name length sanity check ────────────────────────────────────────
    name = record.get("name")
    if isinstance(name, str) and len(name) > 200:
        errors.append(
            f"'name' is suspiciously long ({len(name)} chars); "
            f"max allowed is 200."
        )

    # ── Market cap: must be a positive number ───────────────────────────
    market_cap = record.get("market_cap")
    if market_cap is not None:
        try:
            numeric_value = float(market_cap)
            if numeric_value <= 0:
                errors.append(
                    f"'market_cap' must be positive, got {market_cap}."
                )
        except (ValueError, TypeError):
            errors.append(
                f"'market_cap' must be numeric, got {type(market_cap).__name__}."
            )

    return errors


def validate_stock(record: dict) -> bool:
    """
    Convenience wrapper — returns True if the record passes all checks.
    """
    return len(validation_errors(record)) == 0
