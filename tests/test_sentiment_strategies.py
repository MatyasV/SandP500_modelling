"""Tests for sentiment analysis strategies."""

import unittest

import pandas as pd

from sp500.core.models import StrategyResult
from sp500.data.fields import DataField
from sp500.strategies.sentiment.analyst import AnalystConsensusStrategy
from sp500.strategies.sentiment.recommendations import RecommendationTrendsStrategy
from sp500.strategies.sentiment.composite import SentimentCompositeStrategy


class TestAnalystConsensusStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = AnalystConsensusStrategy()

    def test_name(self):
        self.assertEqual(self.strategy.name, "analyst")

    def test_required_fields(self):
        self.assertEqual(self.strategy.required_fields,
                         {DataField.INFO, DataField.ANALYST_TARGETS})

    def test_does_not_exclude_financials(self):
        constituents = pd.DataFrame({
            "Symbol": ["AAPL", "JPM"],
            "GICS Sector": ["Information Technology", "Financials"],
        })
        filtered = self.strategy.filter_universe(constituents)
        self.assertEqual(len(filtered), 2)

    def test_analyze_scoring(self):
        """50% upside to mean target should score 50."""
        targets = pd.DataFrame({
            "current": [100.0],
            "low": [80.0],
            "median": [140.0],
            "mean": [150.0],
            "high": [200.0],
            "numberOfAnalystOpinions": [15],
        })
        data = {
            DataField.INFO: {"currentPrice": 100.0},
            DataField.ANALYST_TARGETS: targets,
        }
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.score, 50.0, delta=1.0)
        self.assertEqual(result.details["num_analysts"], 15)
        self.assertAlmostEqual(result.details["upside_pct"], 50.0, delta=0.1)

    def test_analyze_overvalued(self):
        """Stock above mean target scores 0."""
        targets = pd.DataFrame({
            "current": [200.0],
            "low": [80.0],
            "median": [140.0],
            "mean": [150.0],
            "high": [160.0],
            "numberOfAnalystOpinions": [10],
        })
        data = {
            DataField.INFO: {"currentPrice": 200.0},
            DataField.ANALYST_TARGETS: targets,
        }
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertEqual(result.score, 0.0)

    def test_too_few_analysts_returns_none(self):
        """Fewer than min_analysts should return None."""
        targets = pd.DataFrame({
            "current": [100.0],
            "low": [80.0],
            "median": [140.0],
            "mean": [150.0],
            "high": [200.0],
            "numberOfAnalystOpinions": [2],
        })
        data = {
            DataField.INFO: {"currentPrice": 100.0},
            DataField.ANALYST_TARGETS: targets,
        }
        result = self.strategy.analyze("TEST", data)
        self.assertIsNone(result)

    def test_missing_info_returns_none(self):
        """Missing INFO data should return None."""
        targets = pd.DataFrame({
            "mean": [150.0],
            "numberOfAnalystOpinions": [10],
        })
        data = {
            DataField.ANALYST_TARGETS: targets,
        }
        result = self.strategy.analyze("TEST", data)
        self.assertIsNone(result)

    def test_missing_targets_returns_none(self):
        """Missing ANALYST_TARGETS data should return None."""
        data = {
            DataField.INFO: {"currentPrice": 100.0},
        }
        result = self.strategy.analyze("TEST", data)
        self.assertIsNone(result)

    def test_confidence_scales_with_analyst_count(self):
        """Confidence should increase with more analysts, capped at 1.0."""
        targets_few = pd.DataFrame({
            "current": [100.0], "low": [80.0], "median": [140.0],
            "mean": [150.0], "high": [200.0],
            "numberOfAnalystOpinions": [5],
        })
        targets_many = pd.DataFrame({
            "current": [100.0], "low": [80.0], "median": [140.0],
            "mean": [150.0], "high": [200.0],
            "numberOfAnalystOpinions": [25],
        })
        data_few = {
            DataField.INFO: {"currentPrice": 100.0},
            DataField.ANALYST_TARGETS: targets_few,
        }
        data_many = {
            DataField.INFO: {"currentPrice": 100.0},
            DataField.ANALYST_TARGETS: targets_many,
        }
        result_few = self.strategy.analyze("TEST", data_few)
        result_many = self.strategy.analyze("TEST", data_many)
        self.assertLess(result_few.confidence, result_many.confidence)
        self.assertEqual(result_many.confidence, 1.0)

    def test_series_input(self):
        """Should handle Series (not just DataFrame) for analyst targets."""
        targets = pd.Series({
            "current": 100.0, "low": 80.0, "median": 140.0,
            "mean": 150.0, "high": 200.0,
            "numberOfAnalystOpinions": 15,
        })
        data = {
            DataField.INFO: {"currentPrice": 100.0},
            DataField.ANALYST_TARGETS: targets,
        }
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.score, 50.0, delta=1.0)


class TestRecommendationTrendsStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = RecommendationTrendsStrategy()

    def test_name(self):
        self.assertEqual(self.strategy.name, "recommendations")

    def test_required_fields(self):
        self.assertEqual(self.strategy.required_fields,
                         {DataField.RECOMMENDATIONS})

    def test_analyze_bullish(self):
        """Mostly buy ratings should score high."""
        recs = pd.DataFrame({
            "strongBuy": [10],
            "buy": [15],
            "hold": [5],
            "sell": [1],
            "strongSell": [0],
        })
        data = {DataField.RECOMMENDATIONS: recs}
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertGreater(result.score, 70)

    def test_analyze_bearish(self):
        """Mostly sell ratings should score low."""
        recs = pd.DataFrame({
            "strongBuy": [0],
            "buy": [1],
            "hold": [5],
            "sell": [15],
            "strongSell": [10],
        })
        data = {DataField.RECOMMENDATIONS: recs}
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertLess(result.score, 30)

    def test_too_few_ratings_returns_none(self):
        """Fewer than 5 total ratings should return None."""
        recs = pd.DataFrame({
            "strongBuy": [1],
            "buy": [1],
            "hold": [1],
            "sell": [0],
            "strongSell": [0],
        })
        data = {DataField.RECOMMENDATIONS: recs}
        result = self.strategy.analyze("TEST", data)
        self.assertIsNone(result)

    def test_missing_data_returns_none(self):
        """Missing RECOMMENDATIONS data should return None."""
        data = {}
        result = self.strategy.analyze("TEST", data)
        self.assertIsNone(result)

    def test_trend_improving(self):
        """Shift from bearish to bullish should add trend bonus."""
        recs = pd.DataFrame({
            "strongBuy": [10, 2],
            "buy": [15, 5],
            "hold": [5, 5],
            "sell": [1, 10],
            "strongSell": [0, 8],
        })
        data = {DataField.RECOMMENDATIONS: recs}
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertEqual(result.details["trend_direction"], "improving")

    def test_all_hold_scores_neutral(self):
        """All hold ratings should score around 50."""
        recs = pd.DataFrame({
            "strongBuy": [0],
            "buy": [0],
            "hold": [20],
            "sell": [0],
            "strongSell": [0],
        })
        data = {DataField.RECOMMENDATIONS: recs}
        result = self.strategy.analyze("TEST", data)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.score, 50.0, delta=1.0)


class TestSentimentCompositeStrategy(unittest.TestCase):
    def setUp(self):
        self.analyst = AnalystConsensusStrategy()
        self.recommendations = RecommendationTrendsStrategy()
        self.strategy = SentimentCompositeStrategy(
            strategies=[self.analyst, self.recommendations]
        )

    def test_name(self):
        self.assertEqual(self.strategy.name, "sentiment_composite")

    def test_required_fields_is_union(self):
        expected = {DataField.INFO, DataField.ANALYST_TARGETS,
                    DataField.RECOMMENDATIONS}
        self.assertEqual(self.strategy.required_fields, expected)

    def test_default_equal_weights(self):
        self.assertEqual(self.strategy.weights, {
            "analyst": 1.0,
            "recommendations": 1.0,
        })

    def test_blending(self):
        """Composite should blend available sub-strategy scores."""
        targets = pd.DataFrame({
            "current": [100.0], "low": [80.0], "median": [140.0],
            "mean": [150.0], "high": [200.0],
            "numberOfAnalystOpinions": [20],
        })
        recs = pd.DataFrame({
            "strongBuy": [10], "buy": [15], "hold": [5],
            "sell": [1], "strongSell": [0],
        })
        all_data = {
            "TEST": {
                DataField.INFO: {"currentPrice": 100.0},
                DataField.ANALYST_TARGETS: targets,
                DataField.RECOMMENDATIONS: recs,
            }
        }
        results = self.strategy.analyze_all(all_data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].ticker, "TEST")
        # Score should be between the two sub-strategy scores
        self.assertGreater(results[0].score, 0)
        self.assertLessEqual(results[0].score, 100)


if __name__ == "__main__":
    unittest.main()
