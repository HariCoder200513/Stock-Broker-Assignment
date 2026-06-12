from flask import Flask, jsonify
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor
import yfinance as yf
import time

app = Flask(__name__)
CORS(app)

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

def fetch_stock(symbol):
    try:
        info = yf.Ticker(symbol).info

        return {
            "ticker": symbol,
            "name": info.get("longName"),
            "sector": info.get("sector"),
            "market_cap": info.get("marketCap")
        }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

@app.route("/stocks")
def get_stocks():
    start = time.time()

    with ThreadPoolExecutor(max_workers=100) as executor:
        results = list(executor.map(fetch_stock, TICKERS))

    results = [r for r in results if r is not None]

    elapsed = round(time.time() - start, 2)

    return jsonify({
        "count": len(results),
        "time_taken_seconds": elapsed,
        "stocks": results
    })

if __name__ == "__main__":
    app.run(debug=True)