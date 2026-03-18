"""Tests for data providers."""

import unittest

from sp500.data.fields import DataField
from sp500.data.providers.wiki import WikipediaProvider
from sp500.data.providers.yfinance_ import YFinanceProvider


class TestWikipediaProvider(unittest.TestCase):
    def setUp(self):
        self.provider = WikipediaProvider()

    def test_name(self):
        self.assertEqual(self.provider.name, "Wikipedia")

    def test_provides_constituents(self):
        self.assertIn(DataField.CONSTITUENTS, self.provider.provides())

    def test_fetch_constituents(self):
        # TODO: Test actual fetching (may need mocking)
        pass


class TestYFinanceProvider(unittest.TestCase):
    def setUp(self):
        self.provider = YFinanceProvider()

    def test_name(self):
        self.assertEqual(self.provider.name, "yfinance")

    def test_provides_expected_fields(self):
        provided = self.provider.provides()
        self.assertIn(DataField.INFO, provided)
        self.assertIn(DataField.CASH_FLOW, provided)
        self.assertIn(DataField.BALANCE_SHEET, provided)
        self.assertIn(DataField.PRICE_HISTORY, provided)

    def test_fetch_single_ticker(self):
        # TODO: Test fetching for a single ticker (may need mocking)
        pass


if __name__ == "__main__":
    unittest.main()
