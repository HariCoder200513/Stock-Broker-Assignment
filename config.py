TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    "TSLA", "NVDA", "JPM", "BAC", "WMT",
    "V", "MA", "NFLX", "ADBE", "CRM",
    "ORCL", "INTC", "AMD", "CSCO", "IBM",
    "PEP", "KO", "DIS", "MCD", "NKE",
    "XOM", "CVX", "PFE", "MRK", "ABT",
    "T", "VZ", "COST", "HD", "LOW",
    "CAT", "GE", "UPS", "FDX", "GS",
    "MS", "BLK", "UBER", "LYFT", "SQ",
    "SHOP", "PLTR", "SNOW", "PANW", "CRWD"
]

if len(TICKERS) < 50:
    raise ValueError("At least 50 stock tickers are required.")

MAX_WORKERS = 5
FETCH_TIMEOUT_SECONDS = 8
FETCH_RETRY_ATTEMPTS = 3
DATABASE_PATH = "data/market_data.sqlite3"
PERSISTENCE_PATH = DATABASE_PATH
