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
            path = Path(temp_dir) / "stocks.json"

            snapshot = StockRepository(str(path)).save([record])
            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(snapshot["count"], 1)
        self.assertEqual(saved["stocks"], [record])

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
