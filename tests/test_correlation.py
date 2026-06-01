"""Tests for CorrelationAnalyzer."""

import unittest
import numpy as np
import pandas as pd

from sp500.data.fields import DataField
from sp500.strategies.correlation.pairs import CorrelationAnalyzer


def _make_price_history(prices, start="2022-01-01"):
    n = len(prices)
    dates = pd.date_range(start=start, periods=n, freq="B")
    return pd.DataFrame({
        "Open": prices, "High": np.array(prices)*1.01,
        "Low": np.array(prices)*0.99, "Close": prices,
        "Volume": np.full(n, 1e6),
    }, index=dates)


class TestCorrelationAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = CorrelationAnalyzer()

    def test_required_fields(self):
        self.assertEqual(self.analyzer.required_fields, {DataField.PRICE_HISTORY})

    def test_compute_matrix_shape(self):
        """Correlation matrix should be N×N with tickers as labels."""
        np.random.seed(1)
        all_data = {}
        for ticker in ["A", "B", "C"]:
            prices = 100 + np.cumsum(np.random.randn(300))
            all_data[ticker] = {DataField.PRICE_HISTORY: _make_price_history(prices)}

        result = self.analyzer.compute_matrix(all_data)
        self.assertEqual(result.matrix.shape, (3, 3))
        self.assertEqual(len(result.tickers), 3)

    def test_diagonal_is_one(self):
        """Self-correlation should be 1.0."""
        np.random.seed(2)
        all_data = {}
        for ticker in ["X", "Y"]:
            prices = 100 + np.cumsum(np.random.randn(300))
            all_data[ticker] = {DataField.PRICE_HISTORY: _make_price_history(prices)}
        result = self.analyzer.compute_matrix(all_data)
        for t in result.tickers:
            self.assertAlmostEqual(result.matrix.loc[t, t], 1.0, places=5)

    def test_negatively_correlated_pair(self):
        """Prices built from opposite returns should have negative correlation."""
        np.random.seed(7)
        n = 300
        returns = np.random.randn(n) * 0.01
        prices_up = 100 * np.exp(np.cumsum(returns))
        prices_down = 100 * np.exp(np.cumsum(-returns))
        all_data = {
            "UP": {DataField.PRICE_HISTORY: _make_price_history(prices_up)},
            "DOWN": {DataField.PRICE_HISTORY: _make_price_history(prices_down)},
        }
        result = self.analyzer.compute_matrix(all_data)
        corr = result.matrix.loc["UP", "DOWN"]
        self.assertLess(corr, 0)

    def test_find_pairs_diversifying_sorted_ascending(self):
        """Diversifying pairs should be sorted by correlation ascending."""
        np.random.seed(3)
        all_data = {}
        for ticker in ["A", "B", "C", "D"]:
            prices = 100 + np.cumsum(np.random.randn(300))
            all_data[ticker] = {DataField.PRICE_HISTORY: _make_price_history(prices)}
        result = self.analyzer.compute_matrix(all_data)
        pairs = self.analyzer.find_pairs(result, top_n=3, mode="diversifying")
        self.assertEqual(len(pairs), 3)
        for i in range(len(pairs) - 1):
            self.assertLessEqual(pairs[i].correlation, pairs[i+1].correlation)

    def test_find_pairs_correlated_sorted_descending(self):
        """Correlated pairs should be sorted by correlation descending."""
        np.random.seed(4)
        all_data = {}
        for ticker in ["A", "B", "C"]:
            prices = 100 + np.cumsum(np.random.randn(300))
            all_data[ticker] = {DataField.PRICE_HISTORY: _make_price_history(prices)}
        result = self.analyzer.compute_matrix(all_data)
        pairs = self.analyzer.find_pairs(result, top_n=3, mode="correlated")
        for i in range(len(pairs) - 1):
            self.assertGreaterEqual(pairs[i].correlation, pairs[i+1].correlation)

    def test_sector_info_included_in_pairs(self):
        """Pairs should include sector information when sector_map is provided."""
        np.random.seed(5)
        all_data = {}
        for ticker in ["A", "B"]:
            prices = 100 + np.cumsum(np.random.randn(300))
            all_data[ticker] = {DataField.PRICE_HISTORY: _make_price_history(prices)}
        result = self.analyzer.compute_matrix(all_data)
        sector_map = {"A": "Technology", "B": "Financials"}
        pairs = self.analyzer.find_pairs(result, mode="diversifying", sector_map=sector_map)
        if pairs:
            self.assertIn(pairs[0].sector1, ["Technology", "Financials"])
            self.assertIn(pairs[0].sector2, ["Technology", "Financials"])

    def test_sector_matrix_shape(self):
        """Sector matrix should be num_sectors × num_sectors."""
        np.random.seed(6)
        all_data = {}
        tickers_and_sectors = [("A", "Tech"), ("B", "Tech"), ("C", "Finance"), ("D", "Energy")]
        for ticker, _ in tickers_and_sectors:
            prices = 100 + np.cumsum(np.random.randn(300))
            all_data[ticker] = {DataField.PRICE_HISTORY: _make_price_history(prices)}
        result = self.analyzer.compute_matrix(all_data)
        sector_map = {t: s for t, s in tickers_and_sectors}
        sect_matrix = self.analyzer.sector_matrix(result, sector_map)
        n_sectors = len(set(sector_map.values()))
        self.assertEqual(sect_matrix.shape, (n_sectors, n_sectors))

    def test_empty_data_returns_empty_result(self):
        """Empty all_data should return CorrelationResult with empty matrix."""
        result = self.analyzer.compute_matrix({})
        self.assertTrue(result.matrix.empty)
        self.assertEqual(result.tickers, [])


if __name__ == "__main__":
    unittest.main()
