"""Tests for output formatting and visual helpers."""

import unittest

from sp500.core.models import StrategyResult
from sp500.output.formatters import _score_style, _score_bar, format_table


class TestScoreStyle(unittest.TestCase):
    def test_high_score(self):
        self.assertEqual(_score_style(85), "bold green")

    def test_mid_score(self):
        self.assertEqual(_score_style(50), "green")

    def test_low_score(self):
        self.assertEqual(_score_style(35), "yellow")

    def test_very_low_score(self):
        self.assertEqual(_score_style(5), "red")

    def test_boundary_70(self):
        self.assertEqual(_score_style(70), "bold green")

    def test_boundary_15(self):
        self.assertEqual(_score_style(15), "dark_orange")


class TestScoreBar(unittest.TestCase):
    def test_full_bar(self):
        bar = _score_bar(100, width=10)
        self.assertIn("█" * 10, bar)

    def test_empty_bar(self):
        bar = _score_bar(0, width=10)
        self.assertIn("░" * 10, bar)

    def test_half_bar(self):
        bar = _score_bar(50, width=10)
        self.assertIn("█" * 5, bar)


class TestFormatTable(unittest.TestCase):
    def test_table_has_bar_column(self):
        results = [StrategyResult(ticker="AAPL", score=75.0,
                                  details={"fair_value": 200}, confidence=0.9)]
        table = format_table(results)
        # Table should have 5 columns: Rank, Ticker, Score, bar, Confidence
        self.assertEqual(len(table.columns), 5)

    def test_verbose_adds_detail_columns(self):
        results = [StrategyResult(ticker="AAPL", score=75.0,
                                  details={"fair_value": 200, "pe": 15}, confidence=0.9)]
        table = format_table(results, verbose=True)
        # 5 base + 2 detail columns
        self.assertEqual(len(table.columns), 7)


if __name__ == "__main__":
    unittest.main()
