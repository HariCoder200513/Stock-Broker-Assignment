import unittest
from persistence.repository import StockRepository

class TestDeduplication(unittest.TestCase):
    def setUp(self):
        self.repo = StockRepository(":memory:")

    def test_sanitize_collapses_duplicates(self):
        records = [
            {"ticker": "AAPL", "name": "Apple", "sector": "Tech", "market_cap": 100},
            {"ticker": "MSFT", "name": "Microsoft", "sector": "Tech", "market_cap": 200},
            {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology", "market_cap": 150},
        ]
        
        clean, rejected, duplicates = self.repo._sanitize(records)
        
        self.assertEqual(len(clean), 2)
        self.assertEqual(duplicates, 1)
        
        # Check that the last one wins
        aapl = next(r for r in clean if r["ticker"] == "AAPL")
        self.assertEqual(aapl["name"], "Apple Inc.")
        self.assertEqual(aapl["market_cap"], 150)

    def test_normalize_tickers_removes_duplicates(self):
        tickers = ["AAPL", "msft", "AAPL", "GOOGL", "msft"]
        normalized = self.repo._normalize_tickers(tickers)
        
        self.assertEqual(len(normalized), 3)
        self.assertEqual(normalized, ["AAPL", "MSFT", "GOOGL"])

    def test_sanitize_handles_case_insensitivity(self):
        records = [
            {"ticker": "aapl", "name": "Apple", "sector": "Tech", "market_cap": 100},
            {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology", "market_cap": 150},
        ]
        clean, rejected, duplicates = self.repo._sanitize(records)
        self.assertEqual(len(clean), 1)
        self.assertEqual(duplicates, 1)
        self.assertEqual(clean[0]["ticker"], "AAPL")

if __name__ == "__main__":
    unittest.main()
