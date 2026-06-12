import unittest
from validator.stock_validator import validate_stock, validation_errors

class TestStockValidation(unittest.TestCase):
    def test_valid_record(self):
        record = {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "sector": "Technology",
            "market_cap": 2500000000000
        }
        self.assertTrue(validate_stock(record))
        self.assertEqual(len(validation_errors(record)), 0)

    def test_missing_fields(self):
        record = {
            "ticker": "AAPL",
            "name": "Apple Inc."
        }
        self.assertFalse(validate_stock(record))
        errors = validation_errors(record)
        self.assertIn("sector is required.", errors)
        self.assertIn("market_cap is required.", errors)

    def test_invalid_market_cap(self):
        # Negative
        record = {"ticker": "A", "name": "B", "sector": "C", "market_cap": -100}
        self.assertIn("market_cap must be positive.", validation_errors(record))
        
        # Zero
        record["market_cap"] = 0
        self.assertIn("market_cap must be positive.", validation_errors(record))
        
        # Non-numeric
        record["market_cap"] = "large"
        self.assertIn("market_cap must be a numeric value.", validation_errors(record))

    def test_empty_strings(self):
        record = {
            "ticker": "  ",
            "name": "Apple",
            "sector": "Tech",
            "market_cap": 100
        }
        self.assertIn("ticker is required.", validation_errors(record))

if __name__ == "__main__":
    unittest.main()
