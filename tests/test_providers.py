"""Tests for data providers."""

import unittest
from unittest.mock import patch, MagicMock

import pandas as pd

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

    @patch("sp500.data.providers.wiki.pd.read_html")
    def test_fetch_constituents(self, mock_read_html):
        """Test Wikipedia scraping with mocked pandas.read_html."""
        mock_df = pd.DataFrame({
            "Symbol": ["AAPL", "BRK.B", "MSFT"],
            "Security": ["Apple", "Berkshire Hathaway", "Microsoft"],
            "GICS Sector": ["Technology", "Financials", "Technology"],
        })
        mock_read_html.return_value = [mock_df]

        result = self.provider.fetch_constituents()

        self.assertEqual(len(result), 3)
        # Verify dot-to-dash normalisation
        self.assertIn("BRK-B", result["Symbol"].values)
        self.assertNotIn("BRK.B", result["Symbol"].values)

    @patch("sp500.data.providers.wiki.pd.read_html")
    def test_fetch_returns_constituents(self, mock_read_html):
        """Test that fetch() returns constituents under sentinel key."""
        mock_df = pd.DataFrame({
            "Symbol": ["AAPL"],
            "Security": ["Apple"],
            "GICS Sector": ["Technology"],
        })
        mock_read_html.return_value = [mock_df]

        result = self.provider.fetch(["AAPL"], {DataField.CONSTITUENTS})
        self.assertIn("__constituents__", result)
        self.assertIn(DataField.CONSTITUENTS, result["__constituents__"])


class TestYFinanceProvider(unittest.TestCase):
    def setUp(self):
        self.provider = YFinanceProvider(config={
            "rate_limits": {"yfinance": {"delay_seconds": 0, "batch_size": 50, "batch_delay": 0}}
        })

    def test_name(self):
        self.assertEqual(self.provider.name, "yfinance")

    def test_provides_expected_fields(self):
        provided = self.provider.provides()
        self.assertIn(DataField.INFO, provided)
        self.assertIn(DataField.CASH_FLOW, provided)
        self.assertIn(DataField.BALANCE_SHEET, provided)
        self.assertIn(DataField.PRICE_HISTORY, provided)

    @patch("sp500.data.providers.yfinance_.yfinance.Ticker")
    def test_fetch_single_ticker(self, mock_ticker_cls):
        """Test fetching INFO for a single ticker with mocked yfinance."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"trailingEps": 6.5, "currentPrice": 180.0}
        mock_ticker_cls.return_value = mock_ticker

        result = self.provider.fetch(["AAPL"], {DataField.INFO})

        self.assertIn("AAPL", result)
        self.assertIn(DataField.INFO, result["AAPL"])
        self.assertEqual(result["AAPL"][DataField.INFO]["trailingEps"], 6.5)


if __name__ == "__main__":
    unittest.main()
