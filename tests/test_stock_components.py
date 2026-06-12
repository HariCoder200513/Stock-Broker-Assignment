import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from persistence.repository import StockRepository
from routes.stocks import process_stock
from validator.stock_validator import (
    validate_stock,
    validation_errors
)


class StockComponentTests(unittest.TestCase):
    def test_validator_accepts_complete_stock(self):
        record = {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "sector": "Technology",
            "market_cap": 100
        }

        self.assertTrue(validate_stock(record))
        self.assertEqual(validation_errors(record), [])

    def test_validator_rejects_partial_stock(self):
        errors = validation_errors({
            "ticker": "AAPL",
            "market_cap": 0
        })

        self.assertIn("name is required.", errors)
        self.assertIn("sector is required.", errors)
        self.assertIn("market_cap must be positive.", errors)

    def test_repository_persists_snapshot(self):
        record = {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "sector": "Technology",
            "market_cap": 100
        }

        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_stocks.db"
            repo = StockRepository(str(db_path))
            
            snapshot = repo.save([record], expected_tickers=["AAPL"])
            
            # Verify snapshot response
            self.assertEqual(snapshot["valid_count"], 1)
            self.assertEqual(len(snapshot["stocks"]), 1)
            self.assertEqual(snapshot["stocks"][0]["ticker"], "AAPL")
            
            # Verify database state directly
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM market_data WHERE ticker = 'AAPL'").fetchone()
            conn.close()
            
            self.assertIsNotNone(row)
            self.assertEqual(row["name"], "Apple Inc.")
            self.assertEqual(row["market_cap"], 100)
            self.assertEqual(row["is_stale"], 0)

    def test_repository_handles_duplicates_in_batch(self):
        records = [
            {"ticker": "AAPL", "name": "Apple", "sector": "Tech", "market_cap": 100},
            {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology", "market_cap": 110},
        ]

        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_stocks.db"
            repo = StockRepository(str(db_path))
            
            snapshot = repo.save(records, expected_tickers=["AAPL"])
            
            self.assertEqual(snapshot["valid_count"], 1)
            self.assertEqual(snapshot["duplicate_count"], 1)
            self.assertEqual(snapshot["stocks"][0]["name"], "Apple Inc.") # Last one wins

    def test_repository_marks_stale_data(self):
        record1 = {"ticker": "AAPL", "name": "Apple", "sector": "Tech", "market_cap": 100}
        record2 = {"ticker": "MSFT", "name": "Microsoft", "sector": "Tech", "market_cap": 200}

        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_stocks.db"
            repo = StockRepository(str(db_path))
            
            # First run: both AAPL and MSFT
            repo.save([record1, record2], expected_tickers=["AAPL", "MSFT"])
            
            # Second run: only AAPL expected, MSFT should be marked stale
            snapshot = repo.save([record1], expected_tickers=["AAPL"])
            
            self.assertEqual(snapshot["stale_count"], 1)
            
            # Verify database state
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            msft = conn.execute("SELECT * FROM market_data WHERE ticker = 'MSFT'").fetchone()
            conn.close()
            
            self.assertEqual(msft["is_stale"], 1)
            self.assertIsNotNone(msft["stale_since"])

    def test_repository_idempotent_upsert(self):
        record = {"ticker": "AAPL", "name": "Apple", "sector": "Tech", "market_cap": 100}

        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_stocks.db"
            repo = StockRepository(str(db_path))
            
            # First run
            repo.save([record], expected_tickers=["AAPL"])
            
            # Second run with same data
            snapshot = repo.save([record], expected_tickers=["AAPL"])
            self.assertEqual(snapshot["upserted_count"], 1)
            
            # Third run with updated data
            updated_record = record.copy()
            updated_record["market_cap"] = 110
            repo.save([updated_record], expected_tickers=["AAPL"])
            
            # Verify database state
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM market_data WHERE ticker = 'AAPL'").fetchall()
            conn.close()
            
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["market_cap"], 110)

    @patch("routes.stocks.fetch_stock")
    def test_process_stock_drops_invalid_fetch_result(self, fetch_stock):
        fetch_stock.return_value = {
            "ticker": "AAPL",
            "name": None,
            "sector": "Technology",
            "market_cap": 100
        }

        self.assertIsNone(process_stock("AAPL"))


if __name__ == "__main__":
    unittest.main()
