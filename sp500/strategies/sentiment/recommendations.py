"""Recommendation trends strategy — score based on buy/sell ratio and momentum."""

import logging
from typing import Any

import pandas as pd

from sp500.core.models import StrategyResult
from sp500.data.fields import DataField
from sp500.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class RecommendationTrendsStrategy(BaseStrategy):

    @property
    def name(self) -> str:
        return "recommendations"

    @property
    def description(self) -> str:
        return "Recommendation trends: buy/hold/sell ratio and momentum"

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.RECOMMENDATIONS}

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        recs = data.get(DataField.RECOMMENDATIONS)

        if recs is None:
            return None

        if isinstance(recs, pd.DataFrame):
            if recs.empty:
                return None
            df = recs
        else:
            return None

        # Ensure expected columns exist
        expected_cols = {"strongBuy", "buy", "hold", "sell", "strongSell"}
        if not expected_cols.issubset(set(df.columns)):
            return None

        # Most recent period (first row)
        latest = df.iloc[0]
        strong_buy = int(latest.get("strongBuy", 0))
        buy = int(latest.get("buy", 0))
        hold = int(latest.get("hold", 0))
        sell = int(latest.get("sell", 0))
        strong_sell = int(latest.get("strongSell", 0))

        total = strong_buy + buy + hold + sell + strong_sell
        if total < 5:
            return None

        # Weighted bullishness score
        weighted_bull = strong_buy * 2 + buy * 1
        weighted_bear = strong_sell * 2 + sell * 1
        bull_plus_bear = weighted_bull + weighted_bear

        if bull_plus_bear == 0:
            # All hold — neutral score
            score = 50.0
        else:
            score = (weighted_bull / bull_plus_bear) * 100

        # Trend bonus: compare to previous period if available
        trend_direction = "stable"
        if len(df) >= 2:
            prev = df.iloc[1]
            prev_bull = int(prev.get("strongBuy", 0)) * 2 + int(prev.get("buy", 0))
            prev_bear = int(prev.get("strongSell", 0)) * 2 + int(prev.get("sell", 0))
            prev_total = prev_bull + prev_bear

            if prev_total > 0:
                prev_ratio = prev_bull / prev_total
                curr_ratio = weighted_bull / bull_plus_bear if bull_plus_bear > 0 else 0.5
                shift = curr_ratio - prev_ratio

                if shift > 0.05:
                    trend_direction = "improving"
                    score = min(100.0, score + 10)
                elif shift < -0.05:
                    trend_direction = "declining"
                    score = max(0.0, score - 10)

        score = max(0.0, min(100.0, score))

        # Confidence based on total ratings
        confidence = min(1.0, total / 30)

        return StrategyResult(
            ticker=ticker,
            score=round(score, 1),
            details={
                "strong_buy": strong_buy,
                "buy": buy,
                "hold": hold,
                "sell": sell,
                "strong_sell": strong_sell,
                "total_ratings": total,
                "bull_ratio": round(weighted_bull / bull_plus_bear, 2) if bull_plus_bear > 0 else 0.5,
                "trend_direction": trend_direction,
            },
            confidence=round(confidence, 2),
        )
