from flask import Flask, jsonify
from flask_cors import CORS
import yfinance as yf

app = Flask(__name__)
CORS(app)

TICKERS = [
    "AAPL","MSFT","GOOGL","AMZN","META",
    "TSLA","NVDA","JPM","BAC","WMT",
    "V","MA","NFLX","ADBE","CRM",
    "ORCL","INTC","AMD","CSCO","IBM",
    "PEP","KO","DIS","MCD","NKE",
    "XOM","CVX","PFE","MRK","ABT",
    "T","VZ","COST","HD","LOW",
    "CAT","GE","UPS","FDX","GS",
    "MS","BLK","UBER","LYFT","SQ",
    "SHOP","PLTR","SNOW","PANW","CRWD"
]

@app.route("/stocks")
def stocks():
    results = []

    for symbol in TICKERS:
        try:
            info = yf.Ticker(symbol).info

            results.append({
                "ticker": symbol,
                "name": info.get("longName"),
                "sector": info.get("sector"),
                "market_cap": info.get("marketCap")
            })

        except Exception as e:
            print(f"Error fetching {symbol}: {e}")

    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True)