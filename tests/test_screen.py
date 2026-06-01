"""Tests for cross-category screen (ScreenResult and run_screen)."""

import unittest
from unittest.mock import MagicMock, patch

from sp500.core.models import StrategyResult, ScreenResult
from sp500.strategies.base import BaseStrategy
from sp500.data.fields import DataField


class TestScreenResult(unittest.TestCase):
    def test_instantiation(self):
        sr = ScreenResult(
            ticker="AAPL",
            scores={"undervalue": 75.0, "risk": 30.0, "growth": 60.0},
            confidences={"undervalue": 0.9, "risk": 0.8, "growth": 0.7},
            details={"undervalue_graham_score": 80.0},
        )
        self.assertEqual(sr.ticker, "AAPL")
        self.assertEqual(sr.scores["undervalue"], 75.0)
        self.assertEqual(sr.confidences["risk"], 0.8)

    def test_empty_scores(self):
        sr = ScreenResult(ticker="X", scores={}, confidences={}, details={})
        self.assertEqual(sr.scores, {})


class _MockStrategy(BaseStrategy):
    """A minimal mock strategy for testing."""
    def __init__(self, name_, results):
        self._name = name_
        self._results = results  # list of StrategyResult

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return "mock"

    @property
    def required_fields(self):
        return {DataField.INFO}

    def filter_universe(self, constituents):
        return constituents

    def analyze(self, ticker, data):
        return None

    def analyze_all(self, all_data):
        return self._results


class TestRunScreen(unittest.TestCase):
    def _make_orchestrator(self):
        """Create an Orchestrator with a mocked DataManager."""
        import pandas as pd
        from sp500.core.orchestrator import Orchestrator

        mock_dm = MagicMock()
        # Fake constituents
        constituents = pd.DataFrame({
            "Symbol": ["AAPL", "MSFT", "GOOG"],
            "GICS Sector": ["Technology", "Technology", "Communication Services"],
        })
        mock_dm.fetch_constituents.return_value = constituents
        mock_dm.fetch.return_value = {
            "AAPL": {DataField.INFO: {}},
            "MSFT": {DataField.INFO: {}},
            "GOOG": {DataField.INFO: {}},
        }

        return Orchestrator(mock_dm)

    def test_run_screen_merges_categories(self):
        """run_screen should merge results from multiple strategies into ScreenResults."""
        orchestrator = self._make_orchestrator()

        uv_results = [
            StrategyResult("AAPL", 80.0, {"graham_score": 80}, 0.9),
            StrategyResult("MSFT", 60.0, {"graham_score": 60}, 0.8),
        ]
        risk_results = [
            StrategyResult("AAPL", 25.0, {"ann_vol_pct": 15.0}, 0.9),
            StrategyResult("MSFT", 70.0, {"ann_vol_pct": 40.0}, 0.8),
            StrategyResult("GOOG", 50.0, {"ann_vol_pct": 30.0}, 0.7),
        ]

        strategies = {
            "undervalue": _MockStrategy("composite", uv_results),
            "risk": _MockStrategy("risk_composite", risk_results),
        }

        results = orchestrator.run_screen(strategies, top_n=10)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIsInstance(r, ScreenResult)
            self.assertIn("ticker", r.__dataclass_fields__)

    def test_run_screen_filters_by_min_score(self):
        """Stocks below undervalue_min filter should be excluded."""
        orchestrator = self._make_orchestrator()

        uv_results = [
            StrategyResult("AAPL", 80.0, {}, 0.9),
            StrategyResult("MSFT", 30.0, {}, 0.8),  # below 50 threshold
        ]
        strategies = {"undervalue": _MockStrategy("composite", uv_results)}
        filters = {"undervalue": (50.0, None)}

        results = orchestrator.run_screen(strategies, top_n=10, filters=filters)
        tickers = [r.ticker for r in results]
        self.assertIn("AAPL", tickers)
        self.assertNotIn("MSFT", tickers)

    def test_run_screen_filters_by_max_score(self):
        """Stocks above risk_max should be excluded."""
        orchestrator = self._make_orchestrator()

        risk_results = [
            StrategyResult("AAPL", 20.0, {}, 0.9),   # safe
            StrategyResult("MSFT", 75.0, {}, 0.8),  # too risky
        ]
        strategies = {"risk": _MockStrategy("risk_composite", risk_results)}
        filters = {"risk": (None, 40.0)}

        results = orchestrator.run_screen(strategies, top_n=10, filters=filters)
        tickers = [r.ticker for r in results]
        self.assertIn("AAPL", tickers)
        self.assertNotIn("MSFT", tickers)

    def test_run_screen_no_filters(self):
        """No filters → all results returned (up to top_n)."""
        orchestrator = self._make_orchestrator()

        uv_results = [
            StrategyResult("AAPL", 80.0, {}, 0.9),
            StrategyResult("MSFT", 60.0, {}, 0.8),
            StrategyResult("GOOG", 40.0, {}, 0.7),
        ]
        strategies = {"undervalue": _MockStrategy("composite", uv_results)}

        results = orchestrator.run_screen(strategies, top_n=10)
        self.assertEqual(len(results), 3)


if __name__ == "__main__":
    unittest.main()
