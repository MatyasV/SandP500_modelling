"""Tests for growth trend strategies."""

import unittest
import numpy as np
import pandas as pd

from sp500.data.fields import DataField
from sp500.strategies.growth.earnings import EarningsTrendStrategy
from sp500.strategies.growth.revenue import RevenueTrendStrategy
from sp500.strategies.growth.margins import MarginAnalysisStrategy
from sp500.strategies.growth.composite import GrowthCompositeStrategy


def _make_income_stmt(rows: dict, n_quarters: int = 8) -> pd.DataFrame:
    """Build a quarterly income statement DataFrame."""
    dates = pd.date_range(end="2024-01-01", periods=n_quarters, freq="QE")
    return pd.DataFrame(rows, index=pd.Index(dates.strftime("%Y-%m-%d"), name=""))


class TestEarningsTrendStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = EarningsTrendStrategy()

    def test_name(self):
        self.assertEqual(self.strategy.name, "earnings")

    def test_required_fields(self):
        self.assertEqual(self.strategy.required_fields,
                         {DataField.INCOME_STMT_Q, DataField.INFO})

    def test_analyze_healthy_growth(self):
        """8 quarters of strongly growing Net Income → score > 60."""
        quarters = pd.date_range(end="2024-01-01", periods=8, freq="QE")
        net_income = np.linspace(1e9, 3e9, 8)  # strong growth
        df = pd.DataFrame(
            {"Net Income": net_income},
            index=pd.Index(quarters.strftime("%Y-%m-%d"))
        ).T
        # df columns = dates, index = row names — this is how yfinance returns it
        data = {
            DataField.INCOME_STMT_Q: df,
            DataField.INFO: {"sharesOutstanding": 1e9},
        }
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertGreater(result.score, 60)

    def test_analyze_declining_earnings(self):
        """8 quarters of declining Net Income → score < 40."""
        quarters = pd.date_range(end="2024-01-01", periods=8, freq="QE")
        net_income = np.linspace(3e9, 1e9, 8)  # declining
        df = pd.DataFrame(
            {"Net Income": net_income},
            index=pd.Index(quarters.strftime("%Y-%m-%d"))
        ).T
        data = {
            DataField.INCOME_STMT_Q: df,
            DataField.INFO: {"sharesOutstanding": 1e9},
        }
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertLess(result.score, 40)

    def test_analyze_insufficient_quarters(self):
        """Fewer than 4 quarters → None."""
        quarters = pd.date_range(end="2024-01-01", periods=3, freq="QE")
        net_income = np.linspace(1e9, 2e9, 3)
        df = pd.DataFrame(
            {"Net Income": net_income},
            index=pd.Index(quarters.strftime("%Y-%m-%d"))
        ).T
        data = {
            DataField.INCOME_STMT_Q: df,
            DataField.INFO: {"sharesOutstanding": 1e9},
        }
        result = self.strategy.analyze("TEST", data)
        self.assertIsNone(result)


class TestRevenueTrendStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = RevenueTrendStrategy()

    def test_name(self):
        self.assertEqual(self.strategy.name, "revenue")

    def test_required_fields(self):
        self.assertEqual(self.strategy.required_fields, {DataField.INCOME_STMT_Q})

    def test_analyze_growing_revenue(self):
        """Steady revenue uptrend → score > 60."""
        quarters = pd.date_range(end="2024-01-01", periods=8, freq="QE")
        revenue = np.linspace(5e9, 10e9, 8)
        df = pd.DataFrame(
            {"Total Revenue": revenue},
            index=pd.Index(quarters.strftime("%Y-%m-%d"))
        ).T
        data = {DataField.INCOME_STMT_Q: df}
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertGreater(result.score, 60)

    def test_analyze_declining_revenue(self):
        """Declining revenue → score < 40."""
        quarters = pd.date_range(end="2024-01-01", periods=8, freq="QE")
        revenue = np.linspace(10e9, 5e9, 8)
        df = pd.DataFrame(
            {"Total Revenue": revenue},
            index=pd.Index(quarters.strftime("%Y-%m-%d"))
        ).T
        data = {DataField.INCOME_STMT_Q: df}
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertLess(result.score, 40)


class TestMarginAnalysisStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = MarginAnalysisStrategy()

    def test_name(self):
        self.assertEqual(self.strategy.name, "margins")

    def test_required_fields(self):
        self.assertEqual(self.strategy.required_fields, {DataField.INCOME_STMT_Q})

    def test_analyze_high_margins(self):
        """Company with ~40% net margins should score > 60."""
        quarters = pd.date_range(end="2024-01-01", periods=8, freq="QE")
        revenue = np.full(8, 10e9)
        net_income = np.full(8, 4e9)    # 40% net margin
        gross_profit = np.full(8, 7e9)  # 70% gross margin
        ebit = np.full(8, 5e9)          # 50% operating margin

        df = pd.DataFrame({
            "Total Revenue": revenue,
            "Gross Profit": gross_profit,
            "EBIT": ebit,
            "Net Income": net_income,
        }, index=pd.Index(quarters.strftime("%Y-%m-%d"))).T
        data = {DataField.INCOME_STMT_Q: df}
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertGreater(result.score, 60)

    def test_analyze_includes_financials(self):
        """Financials typically lack Gross Profit — should still return a result."""
        quarters = pd.date_range(end="2024-01-01", periods=8, freq="QE")
        revenue = np.full(8, 20e9)
        net_income = np.full(8, 4e9)  # 20% net margin
        ebit = np.full(8, 6e9)        # 30% operating margin

        # No Gross Profit row — simulating a financial company
        df = pd.DataFrame({
            "Total Revenue": revenue,
            "EBIT": ebit,
            "Net Income": net_income,
        }, index=pd.Index(quarters.strftime("%Y-%m-%d"))).T
        data = {DataField.INCOME_STMT_Q: df}
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)  # Must not return None just because Gross Profit is missing
        self.assertNotIn("gross_margin_pct", result.details)  # Should not include it


class TestGrowthCompositeStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = GrowthCompositeStrategy(
            strategies=[EarningsTrendStrategy(), RevenueTrendStrategy(), MarginAnalysisStrategy()]
        )

    def test_name(self):
        self.assertEqual(self.strategy.name, "growth_composite")

    def test_required_fields_is_union(self):
        expected = {DataField.INCOME_STMT_Q, DataField.INFO}
        self.assertEqual(self.strategy.required_fields, expected)

    def test_default_equal_weights(self):
        self.assertEqual(self.strategy.weights, {
            "earnings": 1.0, "revenue": 1.0, "margins": 1.0
        })


if __name__ == "__main__":
    unittest.main()
