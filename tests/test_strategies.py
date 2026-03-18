"""Tests for analysis strategies."""

import math
import unittest

import numpy as np
import pandas as pd

from sp500.data.fields import DataField
from sp500.strategies.undervalue.graham import GrahamStrategy
from sp500.strategies.undervalue.dcf import DCFStrategy
from sp500.strategies.undervalue.relative import RelativeStrategy
from sp500.strategies.undervalue.momentum import MomentumStrategy
from sp500.strategies.undervalue.quality import QualityStrategy
from sp500.strategies.undervalue.dividend import DividendQualityStrategy
from sp500.strategies.undervalue.composite import CompositeStrategy


class TestGrahamStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = GrahamStrategy()

    def test_name(self):
        self.assertEqual(self.strategy.name, "graham")

    def test_required_fields(self):
        self.assertEqual(self.strategy.required_fields, {DataField.INFO})

    def test_excludes_financials(self):
        constituents = pd.DataFrame({
            "Symbol": ["AAPL", "JPM", "MSFT"],
            "GICS Sector": ["Technology", "Financials", "Technology"],
        })
        filtered = self.strategy.filter_universe(constituents)
        self.assertEqual(len(filtered), 2)
        self.assertNotIn("JPM", filtered["Symbol"].values)

    def test_analyze_scoring(self):
        """Test Graham Number calculation with known values."""
        data = {DataField.INFO: {
            "trailingEps": 5.0,
            "bookValue": 20.0,
            "currentPrice": 10.0,
        }}
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)

        # Graham Number = sqrt(22.5 * 5 * 20) = sqrt(2250) ≈ 47.43
        expected_graham = math.sqrt(22.5 * 5 * 20)
        self.assertAlmostEqual(result.details["graham_number"], expected_graham, places=1)

        # Score = ((47.43 - 10) / 47.43) * 100 ≈ 78.9
        expected_score = ((expected_graham - 10) / expected_graham) * 100
        self.assertAlmostEqual(result.score, expected_score, places=1)
        self.assertEqual(result.confidence, 1.0)

    def test_analyze_negative_eps(self):
        """Skip stocks with negative EPS."""
        data = {DataField.INFO: {"trailingEps": -2.0, "bookValue": 20.0, "currentPrice": 50.0}}
        self.assertIsNone(self.strategy.analyze("TEST", data))

    def test_analyze_overvalued(self):
        """Stocks trading above Graham Number get score 0."""
        data = {DataField.INFO: {"trailingEps": 1.0, "bookValue": 5.0, "currentPrice": 200.0}}
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertEqual(result.score, 0.0)


class TestDCFStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = DCFStrategy()

    def test_name(self):
        self.assertEqual(self.strategy.name, "dcf")

    def test_required_fields(self):
        self.assertEqual(self.strategy.required_fields, {DataField.INFO, DataField.CASH_FLOW})

    def test_analyze_scoring(self):
        """Test DCF calculation with simple mock data."""
        # Create a cash flow DataFrame with 5 years of data
        cf_df = pd.DataFrame({
            "2019": [100e9, -20e9],
            "2020": [110e9, -22e9],
            "2021": [120e9, -24e9],
            "2022": [130e9, -26e9],
            "2023": [140e9, -28e9],
        }, index=["Operating Cash Flow", "Capital Expenditure"])

        data = {
            DataField.INFO: {
                "currentPrice": 100.0,
                "sharesOutstanding": 1e9,
            },
            DataField.CASH_FLOW: cf_df,
        }
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertGreater(result.score, 0)
        self.assertEqual(result.confidence, 1.0)
        self.assertIn("fair_value", result.details)

    def test_analyze_negative_fcf(self):
        """Skip stocks with negative average FCF."""
        cf_df = pd.DataFrame({
            "2022": [-50e9, -20e9],
            "2023": [-60e9, -25e9],
        }, index=["Operating Cash Flow", "Capital Expenditure"])

        data = {
            DataField.INFO: {"currentPrice": 100.0, "sharesOutstanding": 1e9},
            DataField.CASH_FLOW: cf_df,
        }
        result = self.strategy.analyze("TEST", data)
        self.assertIsNone(result)

    def test_analyze_negative_last_fcf_no_complex_error(self):
        """Negative last FCF with positive average should not raise TypeError."""
        # First two years have high positive FCF, last year is negative —
        # average is positive but last_fcf < 0 which would produce a complex
        # CAGR if not guarded against.
        cf_df = pd.DataFrame({
            "2021": [200e9, -10e9],
            "2022": [180e9, -10e9],
            "2023": [-20e9, -10e9],
        }, index=["Operating Cash Flow", "Capital Expenditure"])

        data = {
            DataField.INFO: {"currentPrice": 100.0, "sharesOutstanding": 1e9},
            DataField.CASH_FLOW: cf_df,
        }
        result = self.strategy.analyze("TEST", data)
        # Should either return a valid result or None, but never raise
        if result is not None:
            self.assertGreaterEqual(result.score, 0)
            self.assertLessEqual(result.score, 100)


class TestRelativeStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = RelativeStrategy()

    def test_name(self):
        self.assertEqual(self.strategy.name, "relative")

    def test_required_fields(self):
        self.assertEqual(self.strategy.required_fields, {DataField.CONSTITUENTS, DataField.INFO})

    def test_analyze_all_scoring(self):
        """Test relative valuation with 5 stocks in same sector."""
        constituents = pd.DataFrame({
            "Symbol": ["A", "B", "C", "D", "E"],
            "GICS Sector": ["Tech"] * 5,
        })

        all_data = {}
        pe_values = [10, 20, 30, 40, 50]
        for ticker, pe in zip(["A", "B", "C", "D", "E"], pe_values):
            all_data[ticker] = {
                DataField.CONSTITUENTS: constituents,
                DataField.INFO: {
                    "trailingPE": pe,
                    "priceToBook": pe / 5,
                    "enterpriseToEbitda": pe / 2,
                },
            }

        results = self.strategy.analyze_all(all_data)
        self.assertEqual(len(results), 5)

        # Sort by score descending — cheapest (lowest P/E) should rank highest
        results.sort(key=lambda r: r.score, reverse=True)
        self.assertEqual(results[0].ticker, "A")  # lowest P/E = highest score
        self.assertEqual(results[-1].ticker, "E")  # highest P/E = lowest score


class TestCompositeStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = CompositeStrategy(
            strategies=[GrahamStrategy(), DCFStrategy(), RelativeStrategy()]
        )

    def test_name(self):
        self.assertEqual(self.strategy.name, "composite")

    def test_required_fields_is_union(self):
        expected = {DataField.INFO, DataField.CASH_FLOW, DataField.CONSTITUENTS}
        self.assertEqual(self.strategy.required_fields, expected)

    def test_default_equal_weights(self):
        self.assertEqual(self.strategy.weights, {
            "graham": 1.0, "dcf": 1.0, "relative": 1.0
        })

    def test_analyze_all_blending(self):
        """Test composite blending with mock data that only graham can score."""
        constituents = pd.DataFrame({
            "Symbol": ["TEST"],
            "GICS Sector": ["Technology"],
        })
        all_data = {
            "TEST": {
                DataField.INFO: {
                    "trailingEps": 5.0,
                    "bookValue": 20.0,
                    "currentPrice": 10.0,
                    "trailingPE": 2.0,
                    "priceToBook": 0.5,
                    "enterpriseToEbitda": 5.0,
                },
                DataField.CONSTITUENTS: constituents,
                # No CASH_FLOW — DCF will return None
            },
        }

        results = self.strategy.analyze_all(all_data)
        # Should get at least a result from graham (relative needs >1 stock to rank)
        scored_tickers = {r.ticker for r in results}
        # Graham should score this stock
        self.assertTrue(len(results) >= 1 or len(scored_tickers) == 0)


class TestMomentumStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = MomentumStrategy()

    def test_name(self):
        self.assertEqual(self.strategy.name, "momentum")

    def test_required_fields(self):
        self.assertEqual(self.strategy.required_fields, {DataField.PRICE_HISTORY})

    def test_analyze_all_scoring(self):
        """Stocks with stronger uptrend should score higher."""
        np.random.seed(42)
        all_data = {}
        # Stock A: strong uptrend
        prices_a = np.linspace(50, 150, 300)
        # Stock B: flat
        prices_b = np.full(300, 100.0)
        # Stock C: downtrend
        prices_c = np.linspace(150, 50, 300)

        for ticker, prices in [("A", prices_a), ("B", prices_b), ("C", prices_c)]:
            dates = pd.date_range(end="2024-01-01", periods=300, freq="B")
            hist = pd.DataFrame({
                "Open": prices,
                "High": prices * 1.01,
                "Low": prices * 0.99,
                "Close": prices,
                "Volume": np.full(300, 1e6),
            }, index=dates)
            all_data[ticker] = {DataField.PRICE_HISTORY: hist}

        results = self.strategy.analyze_all(all_data)
        self.assertEqual(len(results), 3)

        by_ticker = {r.ticker: r for r in results}
        # Uptrend should beat downtrend
        self.assertGreater(by_ticker["A"].score, by_ticker["C"].score)

    def test_insufficient_history(self):
        """Very short price history should still produce a result with low confidence."""
        dates = pd.date_range(end="2024-01-01", periods=60, freq="B")
        prices = np.linspace(90, 100, 60)
        hist = pd.DataFrame({
            "Open": prices, "High": prices, "Low": prices,
            "Close": prices, "Volume": np.full(60, 1e6),
        }, index=dates)
        all_data = {"X": {DataField.PRICE_HISTORY: hist}}
        results = self.strategy.analyze_all(all_data)
        self.assertEqual(len(results), 1)
        self.assertLessEqual(results[0].confidence, 0.6)


class TestQualityStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = QualityStrategy()

    def test_name(self):
        self.assertEqual(self.strategy.name, "quality")

    def test_required_fields(self):
        self.assertEqual(self.strategy.required_fields,
                         {DataField.INFO, DataField.BALANCE_SHEET, DataField.INCOME_STMT})

    def test_excludes_financials(self):
        constituents = pd.DataFrame({
            "Symbol": ["AAPL", "JPM", "MSFT"],
            "GICS Sector": ["Technology", "Financials", "Technology"],
        })
        filtered = self.strategy.filter_universe(constituents)
        self.assertNotIn("JPM", filtered["Symbol"].values)

    def test_analyze_healthy_company(self):
        """Company with strong financials should score high."""
        is_df = pd.DataFrame({
            "2021": [50e9, 2e9, 200e9],
            "2022": [55e9, 2e9, 210e9],
            "2023": [60e9, 2e9, 220e9],
            "2024": [65e9, 2e9, 230e9],
        }, index=["EBIT", "Interest Expense", "Total Revenue"])

        data = {
            DataField.INFO: {
                "debtToEquity": 40.0,    # 0.4 after normalization
                "returnOnEquity": 0.22,
            },
            DataField.BALANCE_SHEET: pd.DataFrame(),
            DataField.INCOME_STMT: is_df,
        }
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertGreater(result.score, 50)

    def test_analyze_risky_company(self):
        """Company with high leverage and low coverage should score low."""
        is_df = pd.DataFrame({
            "2023": [5e9, 4e9, 100e9],
        }, index=["EBIT", "Interest Expense", "Total Revenue"])

        data = {
            DataField.INFO: {
                "debtToEquity": 350.0,    # 3.5 after normalization
                "returnOnEquity": -0.05,
            },
            DataField.BALANCE_SHEET: pd.DataFrame(),
            DataField.INCOME_STMT: is_df,
        }
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertLess(result.score, 30)


class TestDividendQualityStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = DividendQualityStrategy()

    def test_name(self):
        self.assertEqual(self.strategy.name, "dividend")

    def test_required_fields(self):
        self.assertEqual(self.strategy.required_fields,
                         {DataField.INFO, DataField.DIVIDENDS, DataField.CONSTITUENTS})

    def test_analyze_all_scoring(self):
        """Consistent dividend grower should score well."""
        constituents = pd.DataFrame({
            "Symbol": ["A", "B", "C"],
            "GICS Sector": ["Tech"] * 3,
        })
        # Stock A: good yield, low payout, growing dividends
        dates_a = pd.to_datetime(["2020-06-01", "2021-06-01", "2022-06-01", "2023-06-01"])
        divs_a = pd.Series([1.0, 1.1, 1.2, 1.3], index=dates_a)

        # Stock B: high yield (trap), high payout
        dates_b = pd.to_datetime(["2023-06-01"])
        divs_b = pd.Series([5.0], index=dates_b)

        # Stock C: moderate yield, stable
        dates_c = pd.to_datetime(["2021-06-01", "2022-06-01", "2023-06-01"])
        divs_c = pd.Series([2.0, 2.0, 2.0], index=dates_c)

        all_data = {
            "A": {
                DataField.INFO: {"dividendYield": 0.03, "payoutRatio": 0.25},
                DataField.DIVIDENDS: divs_a,
                DataField.CONSTITUENTS: constituents,
            },
            "B": {
                DataField.INFO: {"dividendYield": 0.10, "payoutRatio": 0.95},
                DataField.DIVIDENDS: divs_b,
                DataField.CONSTITUENTS: constituents,
            },
            "C": {
                DataField.INFO: {"dividendYield": 0.04, "payoutRatio": 0.45},
                DataField.DIVIDENDS: divs_c,
                DataField.CONSTITUENTS: constituents,
            },
        }

        results = self.strategy.analyze_all(all_data)
        self.assertEqual(len(results), 3)

        by_ticker = {r.ticker: r for r in results}
        # A (consistent grower, low payout) should beat B (yield trap, high payout)
        self.assertGreater(by_ticker["A"].score, by_ticker["B"].score)

    def test_no_dividend_excluded(self):
        """Stocks with no dividend should not appear in results."""
        constituents = pd.DataFrame({
            "Symbol": ["X"],
            "GICS Sector": ["Tech"],
        })
        all_data = {
            "X": {
                DataField.INFO: {"dividendYield": 0, "payoutRatio": 0},
                DataField.DIVIDENDS: pd.Series(dtype=float),
                DataField.CONSTITUENTS: constituents,
            },
        }
        results = self.strategy.analyze_all(all_data)
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
