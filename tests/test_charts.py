"""Tests for matplotlib chart generation in sp500/output/charts.py."""

import os
import unittest
import tempfile
import numpy as np
import pandas as pd

# Patch matplotlib BEFORE importing charts to use non-interactive backend
import matplotlib
matplotlib.use("Agg")

from sp500.output.charts import (
    plot_score_distribution,
    plot_sector_allocation,
    plot_portfolio_weights,
    plot_efficient_frontier,
    plot_correlation_heatmap,
)


class _FakeResult:
    """Minimal stand-in for StrategyResult."""
    def __init__(self, ticker, score):
        self.ticker = ticker
        self.score = score


class _FakeAllocation:
    """Minimal stand-in for AllocationResult."""
    def __init__(self, weights, expected_return=0.10, expected_volatility=0.15,
                 sharpe_ratio=1.0, method="max_sharpe"):
        self.weights = weights
        self.expected_return = expected_return
        self.expected_volatility = expected_volatility
        self.sharpe_ratio = sharpe_ratio
        self.tickers = list(weights.keys())
        self.method = method


class _FakeCorrelationResult:
    """Minimal stand-in for CorrelationResult."""
    def __init__(self, matrix):
        self.matrix = matrix
        self.tickers = list(matrix.columns)


def _chart_exists(path: str) -> bool:
    return os.path.isfile(path) and os.path.getsize(path) > 0


class TestPlotScoreDistribution(unittest.TestCase):
    def tearDown(self):
        # Clean up any PNG files created during this test
        import glob
        for f in glob.glob("output/*score_dist*.png"):
            try:
                os.remove(f)
            except OSError:
                pass

    def test_creates_file(self):
        results = [_FakeResult(f"T{i}", float(i * 10)) for i in range(11)]
        path = plot_score_distribution(results, "Test")
        self.assertTrue(_chart_exists(path), f"File not created: {path}")

    def test_returns_string_path(self):
        results = [_FakeResult("A", 75.0)]
        path = plot_score_distribution(results, "Test")
        self.assertIsInstance(path, str)
        self.assertTrue(path.endswith(".png"))

    def test_empty_results_no_crash(self):
        path = plot_score_distribution([], "Empty")
        self.assertIsInstance(path, str)


class TestPlotSectorAllocation(unittest.TestCase):
    def tearDown(self):
        import glob
        for f in glob.glob("output/*sector*.png"):
            try:
                os.remove(f)
            except OSError:
                pass

    def test_creates_file(self):
        results = [_FakeResult("AAPL", 80), _FakeResult("MSFT", 70), _FakeResult("JPM", 60)]
        sector_map = {"AAPL": "Technology", "MSFT": "Technology", "JPM": "Financials"}
        path = plot_sector_allocation(results, sector_map, "Test")
        self.assertTrue(_chart_exists(path), f"File not created: {path}")


class TestPlotPortfolioWeights(unittest.TestCase):
    def tearDown(self):
        import glob
        for f in glob.glob("output/*portfolio*.png"):
            try:
                os.remove(f)
            except OSError:
                pass

    def test_creates_file(self):
        alloc = _FakeAllocation({"AAPL": 0.40, "MSFT": 0.35, "GOOG": 0.25})
        path = plot_portfolio_weights(alloc)
        self.assertTrue(_chart_exists(path), f"File not created: {path}")

    def test_equal_weight_portfolio(self):
        alloc = _FakeAllocation({f"T{i}": 0.1 for i in range(10)},
                                 expected_return=0.0, expected_volatility=0.0,
                                 sharpe_ratio=0.0, method="equal_weight")
        path = plot_portfolio_weights(alloc)
        self.assertIsInstance(path, str)


class TestPlotEfficientFrontier(unittest.TestCase):
    def tearDown(self):
        import glob
        for f in glob.glob("output/*frontier*.png"):
            try:
                os.remove(f)
            except OSError:
                pass

    def test_creates_file(self):
        np.random.seed(42)
        frontier = [
            {"vol": np.random.uniform(0.1, 0.4),
             "return": np.random.uniform(-0.05, 0.3),
             "sharpe": np.random.uniform(-0.5, 2.0)}
            for _ in range(50)
        ]
        optimal = {"vol": 0.2, "return": 0.15, "sharpe": 1.5}
        path = plot_efficient_frontier(frontier, optimal)
        self.assertTrue(_chart_exists(path), f"File not created: {path}")

    def test_no_optimal_point(self):
        frontier = [{"vol": 0.2, "return": 0.1, "sharpe": 0.5}]
        path = plot_efficient_frontier(frontier, None)
        self.assertIsInstance(path, str)

    def test_empty_frontier_no_crash(self):
        path = plot_efficient_frontier([], None)
        self.assertIsInstance(path, str)


class TestPlotCorrelationHeatmap(unittest.TestCase):
    def tearDown(self):
        import glob
        for f in glob.glob("output/*correlation*.png"):
            try:
                os.remove(f)
            except OSError:
                pass

    def test_creates_file(self):
        matrix = pd.DataFrame(
            [[1.0, 0.6, -0.3], [0.6, 1.0, 0.2], [-0.3, 0.2, 1.0]],
            index=["A", "B", "C"], columns=["A", "B", "C"]
        )
        corr_result = _FakeCorrelationResult(matrix)
        path = plot_correlation_heatmap(corr_result)
        self.assertTrue(_chart_exists(path), f"File not created: {path}")

    def test_empty_matrix_no_crash(self):
        corr_result = _FakeCorrelationResult(pd.DataFrame())
        path = plot_correlation_heatmap(corr_result)
        self.assertIsInstance(path, str)


if __name__ == "__main__":
    unittest.main()
