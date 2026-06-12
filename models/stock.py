from dataclasses import dataclass


@dataclass
class Stock:
    ticker: str
    name: str
    sector: str
    market_cap: int