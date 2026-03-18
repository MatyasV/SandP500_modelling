"""Relative Valuation strategy — peer comparison within sectors."""

import logging
from typing import Any

import pandas as pd

from sp500.core.models import StrategyResult
from sp500.data.fields import DataField
from sp500.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)

# Valuation ratios to compare (yfinance .info keys)
_RATIOS = ["trailingPE", "priceToBook", "enterpriseToEbitda"]


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
        1. Build ticker→sector mapping from constituents
        2. Compute percentile rank within sector for P/E, P/B, EV/EBITDA
        3. Invert percentiles (lower ratio = higher score)
        4. Average across available ratios
        """
        # Get constituents from any ticker's data
        constituents = None
        for ticker_data in all_data.values():
            constituents = ticker_data.get(DataField.CONSTITUENTS)
            if constituents is not None:
                break

        if constituents is None:
            logger.warning("No constituents data available for relative valuation")
            return []

        # Build ticker → sector mapping
        ticker_to_sector: dict[str, str] = {}
        for _, row in constituents.iterrows():
            ticker_to_sector[row["Symbol"]] = row["GICS Sector"]

        # Build a working DataFrame with ratios
        rows = []
        for ticker, data in all_data.items():
            info = data.get(DataField.INFO)
            if not info or not isinstance(info, dict):
                continue
            sector = ticker_to_sector.get(ticker)
            if not sector:
                continue
            row = {"ticker": ticker, "sector": sector}
            for ratio in _RATIOS:
                val = info.get(ratio)
                if val is not None and isinstance(val, (int, float)) and val > 0:
                    row[ratio] = val
            rows.append(row)

        if not rows:
            return []

        df = pd.DataFrame(rows)

        # Compute inverted percentile ranks within each sector
        results: list[StrategyResult] = []

        for sector, group in df.groupby("sector"):
            sector_size = len(group)

            for _, stock in group.iterrows():
                scores: list[float] = []
                available_ratios = 0

                for ratio in _RATIOS:
                    if ratio not in stock or pd.isna(stock[ratio]):
                        continue
                    # Get all valid values for this ratio in the sector
                    valid = group[ratio].dropna()
                    if len(valid) < 2:
                        continue
                    # Percentile rank (0 to 1, lower ratio = lower percentile)
                    rank = (valid < stock[ratio]).sum() / len(valid)
                    # Invert: cheaper (lower ratio) = higher score
                    inverted = (1 - rank) * 100
                    scores.append(inverted)
                    available_ratios += 1

                if available_ratios == 0:
                    continue

                avg_score = sum(scores) / len(scores)
                confidence = available_ratios / 3.0

                # Confidence penalty for small sectors
                if sector_size < 5:
                    confidence *= 0.8

                results.append(StrategyResult(
                    ticker=stock["ticker"],
                    score=max(0.0, min(100.0, avg_score)),
                    details={
                        "sector": sector,
                        "sector_size": sector_size,
                        "ratios_used": available_ratios,
                        "trailingPE": round(stock.get("trailingPE", 0), 2) if pd.notna(stock.get("trailingPE")) else None,
                        "priceToBook": round(stock.get("priceToBook", 0), 2) if pd.notna(stock.get("priceToBook")) else None,
                        "enterpriseToEbitda": round(stock.get("enterpriseToEbitda", 0), 2) if pd.notna(stock.get("enterpriseToEbitda")) else None,
                    },
                    confidence=confidence,
                ))

        return results
