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

        # Weighted average on 1–5 scale, then normalise to 0–100
        weighted_sum = (strong_buy * 5 + buy * 4 + hold * 3 + sell * 2 + strong_sell * 1)
        avg_rating = weighted_sum / total          # range [1, 5]
        score = (avg_rating - 1) / 4 * 100         # normalise to [0, 100]

        # Trend bonus: compare to previous period if available
        trend_direction = "stable"
        if len(df) >= 2:
            prev = df.iloc[1]
            prev_ws = (int(prev.get("strongBuy", 0)) * 5 + int(prev.get("buy", 0)) * 4
                       + int(prev.get("hold", 0)) * 3 + int(prev.get("sell", 0)) * 2
                       + int(prev.get("strongSell", 0)) * 1)
            prev_total = (int(prev.get("strongBuy", 0)) + int(prev.get("buy", 0))
                          + int(prev.get("hold", 0)) + int(prev.get("sell", 0))
                          + int(prev.get("strongSell", 0)))

            if prev_total > 0:
                prev_avg = prev_ws / prev_total
                shift = avg_rating - prev_avg

                if shift > 0.2:
                    trend_direction = "improving"
                    score = min(100.0, score + 10)
                elif shift < -0.2:
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
                "avg_rating": round(avg_rating, 2),
                "trend_direction": trend_direction,
            },
            confidence=round(confidence, 2),
        )
