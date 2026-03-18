"""Tests for analysis strategies."""

import unittest

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
        # TODO: Test filter_universe excludes financial sector
        pass

    def test_analyze_scoring(self):
        # TODO: Test Graham Number calculation and scoring
        pass


class TestDCFStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = DCFStrategy()

    def test_name(self):
        self.assertEqual(self.strategy.name, "dcf")

    def test_required_fields(self):
        self.assertEqual(self.strategy.required_fields, {DataField.INFO, DataField.CASH_FLOW})

    def test_analyze_scoring(self):
        # TODO: Test DCF calculation and scoring
        pass


class TestRelativeStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = RelativeStrategy()

    def test_name(self):
        self.assertEqual(self.strategy.name, "relative")

    def test_required_fields(self):
        self.assertEqual(self.strategy.required_fields, {DataField.CONSTITUENTS, DataField.INFO})

    def test_analyze_all_scoring(self):
        # TODO: Test relative valuation percentile scoring
        pass


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
        # TODO: Test composite score blending
        pass


if __name__ == "__main__":
    unittest.main()
