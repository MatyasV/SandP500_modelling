"""Discounted Cash Flow (DCF) strategy — intrinsic value via projected cash flows."""

from typing import Any

import pandas as pd

from sp500.core.models import StrategyResult
from sp500.data.fields import DataField
from sp500.strategies.base import BaseStrategy


class DCFStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "dcf"

    @property
    def description(self) -> str:
        return "DCF: intrinsic value from projected free cash flows"

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.INFO, DataField.CASH_FLOW}

    def filter_universe(self, constituents: pd.DataFrame) -> pd.DataFrame:
        """Exclude financial-sector stocks."""
        return constituents[constituents["GICS Sector"] != "Financials"]

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        """
        DCF valuation:
        1. Extract FCF from last 5 years (Operating Cash Flow - CapEx)
        2. Compute 5-year FCF CAGR as growth rate, cap at 20%
        3. Project FCF forward 5 years
        4. Terminal value via Gordon Growth Model: TV = FCF_y5 * (1 + 2.5%) / (10% - 2.5%)
        5. Discount all projected FCFs and TV back to present at 10%
        6. Divide by shares outstanding for per-share fair value

        Score: ((fair_value - price) / fair_value) * 100, clamped 0-100.
        Confidence: based on years of FCF history (5y=1.0, 3y=0.6, fewer=0.3 or None).
        Edge cases: skip negative average FCF.
        """
        # TODO: Implement DCF calculation
        raise NotImplementedError
