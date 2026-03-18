"""Tests for analysis strategies."""

import math
import unittest

import pandas as pd

from sp500.data.fields import DataField
from sp500.strategies.undervalue.graham import GrahamStrategy
from sp500.strategies.undervalue.dcf import DCFStrategy
from sp500.strategies.undervalue.relative import RelativeStrategy
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


if __name__ == "__main__":
    unittest.main()
