"""Tests for SQLite cache."""

import os
import tempfile
import unittest

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

    def test_put_and_get(self):
        # TODO: Test round-trip storage and retrieval
        pass

    def test_ttl_expiration(self):
        # TODO: Test that stale entries are reported as missing
        pass

    def test_invalidate(self):
        # TODO: Test selective cache clearing
        pass

    def test_constituents_round_trip(self):
        # TODO: Test constituents caching
        pass


if __name__ == "__main__":
    unittest.main()
