"""Tests for SQLite cache."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta

import pandas as pd

from sp500.data.cache import SQLiteCache
from sp500.data.fields import DataField


class TestSQLiteCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.cache = SQLiteCache(self.tmp.name, ttl_hours=24)

    def tearDown(self):
        self.cache.conn.close()
        os.unlink(self.tmp.name)

    def test_tables_created(self):
        """Verify cache and constituents tables exist after init."""
        cursor = self.cache.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        self.assertIn("cache", tables)
        self.assertIn("constituents", tables)

    def test_put_and_get_dict(self):
        """Test round-trip for dict data (e.g. INFO)."""
        info = {"trailingEps": 5.0, "bookValue": 20.0, "currentPrice": 100.0}
        self.cache.put("AAPL", {DataField.INFO: info})

        result = self.cache.get("AAPL", {DataField.INFO})
        self.assertEqual(result.missing, set())
        self.assertIn(DataField.INFO, result.found)
        self.assertEqual(result.found[DataField.INFO]["trailingEps"], 5.0)

    def test_put_and_get_dataframe(self):
        """Test round-trip for DataFrame data (e.g. CASH_FLOW)."""
        df = pd.DataFrame({"2023": [100, -20], "2022": [90, -18]},
                          index=["Operating Cash Flow", "Capital Expenditure"])
        self.cache.put("AAPL", {DataField.CASH_FLOW: df})

        result = self.cache.get("AAPL", {DataField.CASH_FLOW})
        self.assertEqual(result.missing, set())
        self.assertIn(DataField.CASH_FLOW, result.found)
        retrieved = result.found[DataField.CASH_FLOW]
        self.assertIsInstance(retrieved, pd.DataFrame)

    def test_ttl_expiration(self):
        """Test that stale entries are reported as missing."""
        self.cache.put("AAPL", {DataField.INFO: {"price": 100}})

        # Manually backdate the entry
        old_time = (datetime.utcnow() - timedelta(hours=25)).isoformat()
        self.cache.conn.execute(
            "UPDATE cache SET fetched_at = ? WHERE ticker = ? AND field = ?",
            (old_time, "AAPL", "INFO"),
        )
        self.cache.conn.commit()

        result = self.cache.get("AAPL", {DataField.INFO})
        self.assertIn(DataField.INFO, result.missing)
        self.assertNotIn(DataField.INFO, result.found)

    def test_invalidate(self):
        """Test selective cache clearing."""
        self.cache.put("AAPL", {DataField.INFO: {"price": 100}})
        self.cache.put("MSFT", {DataField.INFO: {"price": 200}})

        deleted = self.cache.invalidate(ticker="AAPL")
        self.assertEqual(deleted, 1)

        result = self.cache.get("AAPL", {DataField.INFO})
        self.assertIn(DataField.INFO, result.missing)

        result = self.cache.get("MSFT", {DataField.INFO})
        self.assertIn(DataField.INFO, result.found)

    def test_invalidate_all(self):
        """Test clearing entire cache."""
        self.cache.put("AAPL", {DataField.INFO: {"price": 100}})
        self.cache.put("MSFT", {DataField.INFO: {"price": 200}})

        deleted = self.cache.invalidate()
        self.assertEqual(deleted, 2)

    def test_constituents_round_trip(self):
        """Test constituents caching."""
        df = pd.DataFrame({
            "Symbol": ["AAPL", "MSFT", "GOOG"],
            "Security": ["Apple", "Microsoft", "Alphabet"],
            "GICS Sector": ["Technology", "Technology", "Communication Services"],
        })
        self.cache.put_constituents(df)

        retrieved = self.cache.get_constituents()
        self.assertIsNotNone(retrieved)
        self.assertEqual(len(retrieved), 3)
        self.assertListEqual(list(retrieved["Symbol"]), ["AAPL", "MSFT", "GOOG"])


if __name__ == "__main__":
    unittest.main()
