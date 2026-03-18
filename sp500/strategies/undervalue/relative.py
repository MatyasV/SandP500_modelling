"""Relative Valuation strategy — peer comparison within sectors."""

from typing import Any

import pandas as pd

from sp500.core.models import StrategyResult
from sp500.data.fields import DataField
from sp500.strategies.base import BaseStrategy


class RelativeStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "relative"

    @property
    def description(self) -> str:
        return "Relative valuation: P/E, P/B, EV/EBITDA percentile vs sector peers"

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.CONSTITUENTS, DataField.INFO}

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        """Not used — this strategy requires cross-stock comparison via analyze_all()."""
        raise NotImplementedError("RelativeStrategy requires analyze_all()")

    def analyze_all(self, all_data: dict[str, dict[DataField, Any]]) -> list[StrategyResult]:
        """
        Cross-stock relative valuation:
        1. Group all stocks by GICS Sector (from constituents)
        2. For each stock, compute percentile rank within sector for:
           P/E (trailingPE), P/B (priceToBook), EV/EBITDA (enterpriseToEbitda)
        3. Invert percentile: 10th percentile (cheaper than 90%) -> score 90
        4. Average inverted percentiles across the three ratios

        Confidence: 1.0 for all 3 ratios, 0.67 for 2, 0.33 for 1, None for 0.
        Sectors with <5 stocks get a confidence penalty.
        Negative P/E stocks excluded from P/E percentile (still scored on P/B, EV/EBITDA).
        """
        # TODO: Implement cross-stock relative valuation
        raise NotImplementedError
