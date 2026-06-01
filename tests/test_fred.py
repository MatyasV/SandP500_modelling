"""Tests for FREDProvider and DataManager macro field injection."""

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from sp500.data.fields import DataField
from sp500.data.providers.fred import FREDProvider


class TestFREDProvider(unittest.TestCase):
    def setUp(self):
        self.provider = FREDProvider()

    def test_name(self):
        self.assertEqual(self.provider.name, "FRED")

    def test_provides_risk_free_rate(self):
        self.assertIn(DataField.RISK_FREE_RATE, self.provider.provides())

    @patch("sp500.data.providers.fred.yfinance.Ticker")
    def test_fetch_returns_macro_key(self, mock_ticker_cls):
        """fetch() should return {"__macro__": {RISK_FREE_RATE: rate}}."""
        mock_ticker = MagicMock()
        mock_hist = pd.DataFrame({"Close": [4.5]})  # 4.5% Treasury yield
        mock_ticker.history.return_value = mock_hist
        mock_ticker_cls.return_value = mock_ticker

        result = self.provider.fetch(["__macro__"], {DataField.RISK_FREE_RATE})
        self.assertIn("__macro__", result)
        self.assertIn(DataField.RISK_FREE_RATE, result["__macro__"])
        # 4.5% / 100 = 0.045
        self.assertAlmostEqual(result["__macro__"][DataField.RISK_FREE_RATE], 0.045, places=4)

    @patch("sp500.data.providers.fred.yfinance.Ticker")
    def test_fetch_falls_back_on_error(self, mock_ticker_cls):
        """If yfinance fails, should return fallback rate."""
        mock_ticker_cls.side_effect = Exception("Network error")
        result = self.provider.fetch(["__macro__"], {DataField.RISK_FREE_RATE})
        self.assertIn("__macro__", result)
        rate = result["__macro__"][DataField.RISK_FREE_RATE]
        self.assertGreater(rate, 0)
        self.assertLess(rate, 0.20)  # sanity check

    @patch("sp500.data.providers.fred.yfinance.Ticker")
    def test_fetch_empty_history_uses_fallback(self, mock_ticker_cls):
        """Empty price history should use fallback rate."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_cls.return_value = mock_ticker

        result = self.provider.fetch(["__macro__"], {DataField.RISK_FREE_RATE})
        rate = result["__macro__"][DataField.RISK_FREE_RATE]
        self.assertAlmostEqual(rate, 0.045, places=3)  # default fallback

    def test_fetch_wrong_field_returns_empty(self):
        """Requesting a field FREDProvider doesn't supply should return {}."""
        result = self.provider.fetch(["__macro__"], {DataField.INFO})
        self.assertEqual(result, {})


class TestDataManagerMacroInjection(unittest.TestCase):
    """Test that DataManager injects RISK_FREE_RATE into all ticker data dicts."""

    def test_macro_fields_constant_defined(self):
        """_MACRO_FIELDS should contain RISK_FREE_RATE."""
        from sp500.data.manager import _MACRO_FIELDS
        self.assertIn(DataField.RISK_FREE_RATE, _MACRO_FIELDS)

    def test_macro_data_injected(self):
        """
        When RISK_FREE_RATE is in requested fields, DataManager should inject it
        into every ticker's data dict.
        """
        from sp500.data.manager import DataManager
        from sp500.data.cache import SQLiteCache
        import tempfile, os

        # Set up a real (temp) cache and mock providers
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            cache = SQLiteCache(tmp.name, ttl_hours=0)  # TTL=0 means always fresh

            # Mock yfinance provider
            mock_yf = MagicMock()
            mock_yf.provides.return_value = {DataField.INFO}
            mock_yf.fetch.return_value = {
                "AAPL": {DataField.INFO: {"currentPrice": 150.0}},
            }
            mock_yf.name = "yfinance"

            # Mock FRED provider
            mock_fred = MagicMock()
            mock_fred.provides.return_value = {DataField.RISK_FREE_RATE}
            mock_fred.fetch.return_value = {
                "__macro__": {DataField.RISK_FREE_RATE: 0.042},
            }
            mock_fred.name = "FRED"

            dm = DataManager([mock_yf, mock_fred], cache, {})
            result = dm.fetch(["AAPL"], {DataField.INFO, DataField.RISK_FREE_RATE})

            self.assertIn("AAPL", result)
            self.assertIn(DataField.RISK_FREE_RATE, result["AAPL"])
            self.assertAlmostEqual(result["AAPL"][DataField.RISK_FREE_RATE], 0.042, places=4)
        finally:
            cache.conn.close()
            os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()
