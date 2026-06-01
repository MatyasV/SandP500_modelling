"""Tests for PortfolioOptimizer."""

import unittest
import numpy as np
import pandas as pd

from sp500.data.fields import DataField
from sp500.strategies.portfolio.optimizer import PortfolioOptimizer


def _make_price_history(prices, start="2020-01-01"):
    n = len(prices)
    dates = pd.date_range(start=start, periods=n, freq="B")
    return pd.DataFrame({
        "Open": prices, "High": np.array(prices)*1.01,
        "Low": np.array(prices)*0.99, "Close": prices,
        "Volume": np.full(n, 1e6),
    }, index=dates)


class TestPortfolioOptimizer(unittest.TestCase):
    def setUp(self):
        self.optimizer = PortfolioOptimizer()

    def test_required_fields(self):
        self.assertEqual(self.optimizer.required_fields, {DataField.PRICE_HISTORY})

    def _make_all_data(self, n_tickers=3, n_days=300, seed=42):
        np.random.seed(seed)
        all_data = {}
        tickers = [chr(65 + i) for i in range(n_tickers)]  # A, B, C, ...
        for ticker in tickers:
            prices = 100 * np.exp(np.cumsum(np.random.randn(n_days) * 0.01))
            all_data[ticker] = {DataField.PRICE_HISTORY: _make_price_history(prices)}
        return all_data

    def test_equal_weight_divides_evenly(self):
        """equal_weight should give each ticker 1/N weight."""
        all_data = self._make_all_data(n_tickers=4)
        result = self.optimizer.equal_weight(all_data)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.weights), 4)
        for w in result.weights.values():
            self.assertAlmostEqual(w, 0.25, places=3)
        self.assertAlmostEqual(sum(result.weights.values()), 1.0, places=3)
        self.assertEqual(result.method, "equal_weight")

    def test_max_sharpe_weights_sum_to_one(self):
        """Optimised weights should sum to approximately 1.0."""
        all_data = self._make_all_data(n_tickers=3)
        result = self.optimizer.optimize_max_sharpe(all_data, risk_free_rate=0.045)
        self.assertIsNotNone(result)
        total = sum(result.weights.values())
        self.assertAlmostEqual(total, 1.0, places=3)

    def test_max_sharpe_all_weights_non_negative(self):
        """Long-only constraint: all weights should be >= 0."""
        all_data = self._make_all_data(n_tickers=4)
        result = self.optimizer.optimize_max_sharpe(all_data, risk_free_rate=0.045)
        self.assertIsNotNone(result)
        for w in result.weights.values():
            self.assertGreaterEqual(w, -1e-6)  # allow tiny numerical noise

    def test_max_sharpe_returns_allocation_result(self):
        """optimize_max_sharpe should return a valid AllocationResult."""
        from sp500.core.models import AllocationResult
        all_data = self._make_all_data(n_tickers=3)
        result = self.optimizer.optimize_max_sharpe(all_data, risk_free_rate=0.045)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, AllocationResult)
        self.assertGreater(result.expected_volatility, 0)
        self.assertEqual(result.method, "max_sharpe")

    def test_too_few_tickers_returns_none(self):
        """Fewer than min_tickers should return None."""
        optimizer = PortfolioOptimizer(config={"portfolio": {"min_tickers": 3}})
        all_data = self._make_all_data(n_tickers=2)
        result = optimizer.optimize_max_sharpe(all_data)
        self.assertIsNone(result)

    def test_empty_data_returns_none(self):
        """Empty all_data should return None."""
        result = self.optimizer.equal_weight({})
        self.assertIsNone(result)
        result2 = self.optimizer.optimize_max_sharpe({})
        self.assertIsNone(result2)

    def test_efficient_frontier_returns_list(self):
        """compute_efficient_frontier should return a list of dicts."""
        all_data = self._make_all_data(n_tickers=3)
        frontier = self.optimizer.compute_efficient_frontier(all_data, n_portfolios=50)
        self.assertIsInstance(frontier, list)
        self.assertEqual(len(frontier), 50)
        for point in frontier:
            self.assertIn("vol", point)
            self.assertIn("return", point)
            self.assertIn("sharpe", point)

    def test_short_history_still_works(self):
        """Tickers with 60-100 days of history should still produce a result."""
        all_data = self._make_all_data(n_tickers=3, n_days=70)
        result = self.optimizer.equal_weight(all_data)
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
