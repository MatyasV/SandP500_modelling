"""Composite strategy — weighted blend of multiple valuation methods."""

from typing import Any

import pandas as pd

from sp500.core.models import StrategyResult
from sp500.data.fields import DataField
from sp500.strategies.base import BaseStrategy


class CompositeStrategy(BaseStrategy):
    def __init__(self, strategies: list[BaseStrategy],
                 weights: dict[str, float] | None = None,
                 weight_by_confidence: bool = True):
        self.strategies = strategies
        self.weights = weights or {s.name: 1.0 for s in strategies}
        self.weight_by_confidence = weight_by_confidence

    @property
    def name(self) -> str:
        return "composite"

    @property
    def description(self) -> str:
        return "Weighted composite of multiple valuation strategies"

    @property
    def required_fields(self) -> set[DataField]:
        """Union of all sub-strategy requirements."""
        return set().union(*(s.required_fields for s in self.strategies))

    def filter_universe(self, constituents: pd.DataFrame) -> pd.DataFrame:
        """No filtering — sub-strategies handle their own exclusions."""
        return constituents

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        """Not used directly — composite runs via analyze_all()."""
        raise NotImplementedError("CompositeStrategy requires analyze_all()")

    def analyze_all(self, all_data: dict[str, dict[DataField, Any]]) -> list[StrategyResult]:
        """
        Blend sub-strategy scores:
        1. Run each sub-strategy independently over the full dataset
        2. For each ticker, compute weighted average of available scores
        3. If weight_by_confidence is True, scale each sub-strategy's weight
           by its confidence for that ticker
        4. Financial-sector stocks will only have relative valuation scores,
           so their composite confidence will naturally be lower
        """
        # TODO: Implement composite scoring
        raise NotImplementedError
