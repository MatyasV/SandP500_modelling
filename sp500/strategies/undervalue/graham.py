"""Graham Number strategy — classic Benjamin Graham valuation formula."""

from typing import Any

import pandas as pd

from sp500.core.models import StrategyResult
from sp500.data.fields import DataField
from sp500.strategies.base import BaseStrategy


class GrahamStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "graham"

    @property
    def description(self) -> str:
        return "Graham Number: sqrt(22.5 * EPS * Book Value Per Share)"

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.INFO}

    def filter_universe(self, constituents: pd.DataFrame) -> pd.DataFrame:
        """Exclude financial-sector stocks (banks, insurers, REITs)."""
        return constituents[constituents["GICS Sector"] != "Financials"]

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        """
        Compute Graham Number and score.
        Formula: graham_number = sqrt(22.5 * EPS * Book Value Per Share)
        Score: ((graham_number - price) / graham_number) * 100, clamped 0-100.
        Confidence: 1.0 if both EPS and book value available, 0.0 otherwise.
        Edge cases: skip negative EPS or negative book value.
        """
        # TODO: Implement Graham Number calculation
        raise NotImplementedError
