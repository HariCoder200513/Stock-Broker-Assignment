"""
Domain model for a single stock record.

Using a dataclass instead of raw dicts gives us:
  • Type safety — callers know exactly what fields exist
  • Immutability (frozen=True) — prevents accidental mutation after validation
  • A canonical conversion point between API responses and DB rows
"""

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Stock:
    """
    Represents one validated market-data snapshot for a US-listed equity.

    Attributes:
        ticker:     The exchange symbol, always uppercase (e.g. "AAPL").
        name:       The full legal / trading name of the company.
        sector:     GICS sector classification (e.g. "Technology").
        market_cap: Total market capitalisation in USD, must be > 0.
    """
    ticker: str
    name: str
    sector: str
    market_cap: int

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON responses or DB insertion."""
        return asdict(self)