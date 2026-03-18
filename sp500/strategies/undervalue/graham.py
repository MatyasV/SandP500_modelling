"""Graham Number strategy — classic Benjamin Graham valuation formula."""

import math
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
        """
        info = data.get(DataField.INFO)
        if not info or not isinstance(info, dict):
            return None

        eps = info.get("trailingEps")
        book_value = info.get("bookValue")
        price = info.get("currentPrice") or info.get("regularMarketPrice")

        if not all(v is not None for v in [eps, book_value, price]):
            return None
        if eps <= 0 or book_value <= 0:
            return None

        graham_number = math.sqrt(22.5 * eps * book_value)
        raw_score = ((graham_number - price) / graham_number) * 100
        score = max(0.0, min(100.0, raw_score))

        return StrategyResult(
            ticker=ticker,
            score=score,
            details={
                "graham_number": round(graham_number, 2),
                "current_price": round(price, 2),
                "eps": round(eps, 2),
                "book_value": round(book_value, 2),
                "margin_of_safety_pct": round(raw_score, 1),
            },
            confidence=1.0,
        )
