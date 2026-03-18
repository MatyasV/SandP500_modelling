"""Sentiment composite strategy — weighted blend of sentiment methods."""

import logging
from typing import Any

import pandas as pd

from sp500.core.models import StrategyResult
from sp500.data.fields import DataField
from sp500.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class SentimentCompositeStrategy(BaseStrategy):
    def __init__(self, strategies: list[BaseStrategy],
                 weights: dict[str, float] | None = None,
                 weight_by_confidence: bool = True):
        self.strategies = strategies
        self.weights = weights or {s.name: 1.0 for s in strategies}
        self.weight_by_confidence = weight_by_confidence

    @property
    def name(self) -> str:
        return "sentiment_composite"

    @property
    def description(self) -> str:
        return "Weighted composite of sentiment strategies"

    @property
    def required_fields(self) -> set[DataField]:
        """Union of all sub-strategy requirements."""
        return set().union(*(s.required_fields for s in self.strategies))

    def filter_universe(self, constituents: pd.DataFrame) -> pd.DataFrame:
        """No filtering — sub-strategies handle their own exclusions."""
        return constituents

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        """Not used directly — composite runs via analyze_all()."""
        raise NotImplementedError("SentimentCompositeStrategy requires analyze_all()")

    def analyze_all(self, all_data: dict[str, dict[DataField, Any]]) -> list[StrategyResult]:
        """
        Blend sub-strategy scores:
        1. Run each sub-strategy independently
        2. For each ticker, compute weighted average of available scores
        3. Scale weights by confidence if weight_by_confidence is True
        """
        # Step 1: Run each sub-strategy
        strategy_results: dict[str, dict[str, StrategyResult]] = {}

        for strategy in self.strategies:
            logger.info("Running sub-strategy: %s", strategy.name)
            results = strategy.analyze_all(all_data)
            strategy_results[strategy.name] = {r.ticker: r for r in results}

        # Step 2: Blend per-ticker
        all_tickers: set[str] = set()
        for by_ticker in strategy_results.values():
            all_tickers.update(by_ticker.keys())

        composite_results: list[StrategyResult] = []

        for ticker in all_tickers:
            weighted_score = 0.0
            total_weight = 0.0
            confidences: list[float] = []
            details: dict[str, Any] = {}

            for strategy_name, by_ticker in strategy_results.items():
                result = by_ticker.get(ticker)
                if result is None:
                    continue

                base_weight = self.weights.get(strategy_name, 1.0)
                if self.weight_by_confidence:
                    effective_weight = base_weight * result.confidence
                else:
                    effective_weight = base_weight

                weighted_score += result.score * effective_weight
                total_weight += effective_weight
                confidences.append(result.confidence)

                details[f"{strategy_name}_score"] = round(result.score, 1)
                details[f"{strategy_name}_confidence"] = round(result.confidence, 2)

            if total_weight == 0:
                continue

            score = weighted_score / total_weight
            confidence = sum(confidences) / len(confidences)

            composite_results.append(StrategyResult(
                ticker=ticker,
                score=max(0.0, min(100.0, score)),
                details=details,
                confidence=round(confidence, 2),
            ))

        return composite_results
