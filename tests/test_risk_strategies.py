"""Tests for risk profiling strategies."""

import unittest
import numpy as np
import pandas as pd

from sp500.data.fields import DataField
from sp500.strategies.risk.volatility import VolatilityStrategy
from sp500.strategies.risk.risk_adjusted import RiskAdjustedReturnsStrategy
from sp500.strategies.risk.composite import RiskCompositeStrategy


def _make_price_history(prices, end="2024-01-01"):
    """Build a minimal OHLCV DataFrame from a price array."""
    n = len(prices)
    dates = pd.date_range(end=end, periods=n, freq="B")
    return pd.DataFrame({
        "Open": prices,
        "High": np.array(prices) * 1.01,
        "Low": np.array(prices) * 0.99,
        "Close": prices,
        "Volume": np.full(n, 1e6),
    }, index=dates)


class TestVolatilityStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = VolatilityStrategy()

    def test_name(self):
        self.assertEqual(self.strategy.name, "volatility")

    def test_required_fields(self):
        self.assertEqual(self.strategy.required_fields, {DataField.PRICE_HISTORY, DataField.INFO})

    def test_analyze_all_returns_results(self):
        """Basic smoke test — should return a result for each ticker."""
        np.random.seed(42)
        prices = np.cumsum(np.random.randn(300)) + 100
        hist = _make_price_history(prices)
        all_data = {
            "TEST": {
                DataField.PRICE_HISTORY: hist,
                DataField.INFO: {"beta": 1.0},
            }
        }
        results = self.strategy.analyze_all(all_data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].ticker, "TEST")
        self.assertGreaterEqual(results[0].score, 0)
        self.assertLessEqual(results[0].score, 100)

    def test_high_vol_scores_higher(self):
        """High-volatility stock should get a higher risk score than low-vol stock."""
        np.random.seed(0)
        # High-vol: large random daily jumps
        high_vol_prices = 100 + np.cumsum(np.random.randn(300) * 5)
        high_vol_prices = np.abs(high_vol_prices) + 10  # keep positive
        # Low-vol: gentle steady trend
        low_vol_prices = np.linspace(90, 110, 300)

        all_data = {
            "HIGH": {
                DataField.PRICE_HISTORY: _make_price_history(high_vol_prices),
                DataField.INFO: {"beta": 1.5},
            },
            "LOW": {
                DataField.PRICE_HISTORY: _make_price_history(low_vol_prices),
                DataField.INFO: {"beta": 0.5},
            },
        }
        results = self.strategy.analyze_all(all_data)
        by_ticker = {r.ticker: r for r in results}
        self.assertGreater(by_ticker["HIGH"].score, by_ticker["LOW"].score)

    def test_low_history_low_confidence(self):
        """Less than 126 trading days should yield confidence <= 0.3."""
        prices = np.linspace(90, 100, 60)
        hist = _make_price_history(prices)
        all_data = {"X": {DataField.PRICE_HISTORY: hist, DataField.INFO: {"beta": 1.0}}}
        results = self.strategy.analyze_all(all_data)
        self.assertEqual(len(results), 1)
        self.assertLessEqual(results[0].confidence, 0.3)

    def test_missing_info_uses_beta_fallback(self):
        """Missing INFO should not crash — beta defaults to 1.0."""
        prices = np.linspace(90, 110, 300)
        hist = _make_price_history(prices)
        all_data = {"Y": {DataField.PRICE_HISTORY: hist}}  # no INFO
        results = self.strategy.analyze_all(all_data)
        self.assertEqual(len(results), 1)  # should still produce a result


class TestRiskAdjustedReturnsStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = RiskAdjustedReturnsStrategy()

    def test_name(self):
        self.assertEqual(self.strategy.name, "risk_adjusted")

    def test_required_fields(self):
        self.assertEqual(self.strategy.required_fields, {DataField.PRICE_HISTORY})

    def test_analyze_all_returns_results(self):
        """Basic smoke test."""
        np.random.seed(1)
        prices = np.cumsum(np.random.randn(300)) + 100
        prices = np.abs(prices) + 50
        hist = _make_price_history(prices)
        all_data = {"TEST": {DataField.PRICE_HISTORY: hist}}
        results = self.strategy.analyze_all(all_data)
        self.assertEqual(len(results), 1)
        self.assertGreaterEqual(results[0].score, 0)
        self.assertLessEqual(results[0].score, 100)

    def test_poor_risk_adjusted_scores_higher(self):
        """Highly volatile flat stock (low Sharpe) should score higher risk than steady uptrend."""
        np.random.seed(5)
        # High-risk: volatile + flat overall → low Sharpe
        volatile_flat = 100 + np.cumsum(np.random.randn(300) * 3)
        volatile_flat = np.abs(volatile_flat) + 10
        # Low-risk: steady uptrend → high Sharpe
        steady_up = np.linspace(80, 160, 300)

        all_data = {
            "BAD": {DataField.PRICE_HISTORY: _make_price_history(volatile_flat)},
            "GOOD": {DataField.PRICE_HISTORY: _make_price_history(steady_up)},
        }
        results = self.strategy.analyze_all(all_data)
        by_ticker = {r.ticker: r for r in results}
        self.assertGreater(by_ticker["BAD"].score, by_ticker["GOOD"].score)

    def test_low_history_low_confidence(self):
        """Less than 126 trading days → confidence <= 0.3."""
        prices = np.linspace(90, 100, 60)
        hist = _make_price_history(prices)
        all_data = {"X": {DataField.PRICE_HISTORY: hist}}
        results = self.strategy.analyze_all(all_data)
        self.assertEqual(len(results), 1)
        self.assertLessEqual(results[0].confidence, 0.3)


class TestRiskCompositeStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = RiskCompositeStrategy(
            strategies=[VolatilityStrategy(), RiskAdjustedReturnsStrategy()]
        )

    def test_name(self):
        self.assertEqual(self.strategy.name, "risk_composite")

    def test_required_fields_is_union(self):
        expected = {DataField.PRICE_HISTORY, DataField.INFO}
        self.assertEqual(self.strategy.required_fields, expected)

    def test_default_equal_weights(self):
        self.assertEqual(self.strategy.weights, {
            "volatility": 1.0, "risk_adjusted": 1.0
        })

    def test_analyze_all_returns_results(self):
        """Composite should return results for any ticker both sub-strategies score."""
        np.random.seed(7)
        prices = np.cumsum(np.random.randn(300)) + 100
        prices = np.abs(prices) + 50
        hist = _make_price_history(prices)
        all_data = {
            "A": {DataField.PRICE_HISTORY: hist, DataField.INFO: {"beta": 1.2}},
        }
        results = self.strategy.analyze_all(all_data)
        self.assertGreaterEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
