"""Analyst consensus strategy — score based on upside to mean price target."""

import logging
from typing import Any

import pandas as pd

from sp500.core.models import StrategyResult
from sp500.data.fields import DataField
from sp500.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class AnalystConsensusStrategy(BaseStrategy):
    def __init__(self, config: dict | None = None):
        analyst_cfg = (config or {}).get("analyst", {})
        self.upside_cap = analyst_cfg.get("upside_cap_pct", 100)
        self.min_analysts = analyst_cfg.get("min_analysts", 3)

    @property
    def name(self) -> str:
        return "analyst"

    @property
    def description(self) -> str:
        return "Analyst consensus: upside to mean price target"

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.INFO, DataField.ANALYST_TARGETS}

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        info = data.get(DataField.INFO)
        targets = data.get(DataField.ANALYST_TARGETS)

        if not info or targets is None:
            return None

        # Extract current price
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price or price <= 0:
            return None

        # Extract analyst targets — handle both DataFrame and Series
        try:
            if isinstance(targets, pd.DataFrame):
                if targets.empty:
                    return None
                row = targets.iloc[0]
            elif isinstance(targets, pd.Series):
                row = targets
            elif isinstance(targets, dict):
                row = targets
            else:
                return None

            mean_target = _get_value(row, "mean")
            median_target = _get_value(row, "median")
            low_target = _get_value(row, "low")
            high_target = _get_value(row, "high")
            num_analysts = int(_get_value(row, "numberOfAnalystOpinions") or 0)
        except (KeyError, TypeError, ValueError):
            return None

        if not mean_target or mean_target <= 0:
            return None

        if num_analysts < self.min_analysts:
            return None

        # Score based on upside to mean target
        upside_pct = (mean_target - price) / price * 100
        score = max(0.0, min(100.0, upside_pct / self.upside_cap * 100))

        # Confidence based on analyst coverage
        confidence = min(1.0, num_analysts / 20)

        return StrategyResult(
            ticker=ticker,
            score=round(score, 1),
            details={
                "current_price": round(price, 2),
                "mean_target": round(mean_target, 2),
                "median_target": round(median_target, 2) if median_target else None,
                "low_target": round(low_target, 2) if low_target else None,
                "high_target": round(high_target, 2) if high_target else None,
                "num_analysts": num_analysts,
                "upside_pct": round(upside_pct, 1),
            },
            confidence=round(confidence, 2),
        )


def _get_value(row, key):
    """Extract a value from a Series, dict, or DataFrame row."""
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except (KeyError, IndexError):
        return None
