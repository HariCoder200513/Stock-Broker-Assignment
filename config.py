TICKERS = [
    # Top 50
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM", "BAC", "WMT",
    "V", "MA", "NFLX", "ADBE", "CRM", "ORCL", "INTC", "AMD", "CSCO", "IBM",
    "PEP", "KO", "DIS", "MCD", "NKE", "XOM", "CVX", "PFE", "MRK", "ABT",
    "T", "VZ", "COST", "HD", "LOW", "CAT", "GE", "UPS", "FDX", "GS",
    "MS", "BLK", "UBER", "LYFT", "SQ", "SHOP", "PLTR", "SNOW", "PANW", "CRWD",
    
    # 51-100
    "AVGO", "COST", "TMUS", "TXN", "QCOM", "AMAT", "INTU", "ISRG", "AMGN", "HON",
    "LRCX", "PGR", "UNH", "LLY", "VRTX", "BKNG", "SBUX", "MDLZ", "REGN", "ADP",
    "ADI", "MU", "GILD", "PANW", "MELI", "SNPS", "CDNS", "PYPL", "MAR", "KLAC",
    "ORLY", "CTAS", "MNST", "LULU", "ROP", "CDW", "IDXX", "ADSK", "PCAR", "DXCM",
    "CPRT", "MCHP", "ROST", "PAYX", "FAST", "ODFL", "KDP", "AZN", "EXC", "KLA",

    # 101-150
    "AEP", "BKR", "BIIB", "CHTR", "CMCSA", "CPRT", "CSX", "CTSH", "DDOG", "DLTR",
    "EA", "EBAY", "ENPH", "EXPE", "FANG", "FTNT", "GEHC", "IDXX", "ILMN", "KHC",
    "LCID", "MCHP", "MRNA", "MRVL", "ODFL", "ON", "ORLY", "PANW", "PAYX", "PYPL",
    "QCOM", "ROST", "SBUX", "SGEN", "SIRI", "SNPS", "TEAM", "TMUS", "TXN", "VRSK",
    "VRTX", "WBA", "WBD", "WDAY", "XEL", "ZS", "ABNB", "CEG", "GFS", "PDD",

    # 151-200
    "ANSS", "ASML", "AXON", "CDNS", "DASH", "FI", "KLAC", "LRCX", "MDB", "MELI",
    "MNST", "ROP", "SNOW", "SPLK", "TTD", "WDAY", "A", "AA", "AAL", "AAON",
    "AAP", "AAWW", "ABBV", "ABC", "ABG", "ABM", "ABMD", "ABT", "ACAD", "ACC",
    "ACGL", "ACHC", "ACI", "ACIW", "ACLS", "ACM", "ACN", "ACRE", "ACRS", "ACRX",
    "ACTG", "ACU", "ACVA", "ADAP", "ADBE", "ADC", "ADCT", "ADI", "ADM", "ADMA"
]

# Ensure uniqueness and count
TICKERS = list(dict.fromkeys(TICKERS))

if len(TICKERS) < 50:
    raise ValueError("At least 50 stock tickers are required.")

MAX_WORKERS = 25  # Increased slightly for 200 tickers
FETCH_TIMEOUT_SECONDS = 8
FETCH_RETRY_ATTEMPTS = 3
DATABASE_PATH = "data/market_data.sqlite3"
PERSISTENCE_PATH = DATABASE_PATH
