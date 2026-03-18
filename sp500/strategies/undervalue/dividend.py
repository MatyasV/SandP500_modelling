"""Dividend Quality strategy — yield, payout sustainability, consistency, growth."""

import logging
from typing import Any

import numpy as np
import pandas as pd

from sp500.core.models import StrategyResult
from sp500.data.fields import DataField
from sp500.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class DividendQualityStrategy(BaseStrategy):
    def __init__(self, config: dict | None = None):
        div_cfg = (config or {}).get("dividend", {})
        self.yield_trap_threshold = div_cfg.get("yield_trap_threshold", 0.08)
        self.min_history_years = div_cfg.get("min_history_years", 1)

    @property
    def name(self) -> str:
        return "dividend"

    @property
    def description(self) -> str:
        return "Dividend quality: yield vs peers, payout sustainability, growth"

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.INFO, DataField.DIVIDENDS, DataField.CONSTITUENTS}

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        raise NotImplementedError("DividendQualityStrategy requires analyze_all()")

    def analyze_all(self, all_data: dict[str, dict[DataField, Any]]) -> list[StrategyResult]:
        """
        Cross-stock dividend quality scoring:
        1. Extract yield, payout ratio, dividend history per ticker
        2. Rank yield within sector peers
        3. Score payout sustainability, consistency, growth
        4. Blend into final score
        """
        # Get constituents for sector mapping
        constituents = None
        for ticker_data in all_data.values():
            constituents = ticker_data.get(DataField.CONSTITUENTS)
            if constituents is not None:
                break
        if constituents is None:
            return []

        ticker_to_sector = dict(zip(constituents["Symbol"], constituents["GICS Sector"]))

        # Phase 1: Extract per-ticker dividend data
        records: list[dict[str, Any]] = []

        for ticker, data in all_data.items():
            info = data.get(DataField.INFO)
            if not info or not isinstance(info, dict):
                continue

            div_yield = info.get("dividendYield")
            if not div_yield or not isinstance(div_yield, (int, float)) or div_yield <= 0:
                continue

            payout_ratio = info.get("payoutRatio")
            sector = ticker_to_sector.get(ticker, "Unknown")

            # Dividend history analysis
            dividends = data.get(DataField.DIVIDENDS)
            annual_divs: dict[int, float] = {}
            if dividends is not None and isinstance(dividends, pd.Series) and not dividends.empty:
                for date, amount in dividends.items():
                    year = date.year if hasattr(date, 'year') else pd.Timestamp(date).year
                    annual_divs[year] = annual_divs.get(year, 0) + float(amount)

            years_of_dividends = len(annual_divs)

            # Consecutive years of non-decrease
            consecutive = 0
            if years_of_dividends >= 2:
                sorted_years = sorted(annual_divs.keys())
                for i in range(len(sorted_years) - 1, 0, -1):
                    if annual_divs[sorted_years[i]] >= annual_divs[sorted_years[i - 1]]:
                        consecutive += 1
                    else:
                        break

            # Dividend CAGR
            div_cagr = None
            if years_of_dividends >= 2:
                sorted_years = sorted(annual_divs.keys())
                first_div = annual_divs[sorted_years[0]]
                last_div = annual_divs[sorted_years[-1]]
                n_periods = len(sorted_years) - 1
                if first_div > 0 and last_div > 0 and n_periods > 0:
                    div_cagr = (last_div / first_div) ** (1 / n_periods) - 1

            # Confidence based on history length
            if years_of_dividends >= 10:
                confidence = 1.0
            elif years_of_dividends >= 5:
                confidence = 0.7
            elif years_of_dividends >= 2:
                confidence = 0.4
            else:
                confidence = 0.2

            records.append({
                "ticker": ticker,
                "sector": sector,
                "div_yield": div_yield,
                "payout_ratio": payout_ratio,
                "years_of_dividends": years_of_dividends,
                "consecutive_increases": consecutive,
                "div_cagr": div_cagr,
                "confidence": confidence,
            })

        if not records:
            return []

        df = pd.DataFrame(records)

        # Phase 2: Compute scores

        # 2a. Yield percentile within sector (with yield trap penalty)
        yield_scores = pd.Series(50.0, index=df.index)
        for sector, group in df.groupby("sector"):
            if len(group) < 2:
                continue
            pctl = group["div_yield"].rank(pct=True) * 100
            # Penalize suspected yield traps
            for idx in group.index:
                if group.loc[idx, "div_yield"] > self.yield_trap_threshold:
                    pctl[idx] = max(0, pctl[idx] - 30)
            yield_scores[group.index] = pctl

        # 2b. Payout sustainability
        def _payout_score(ratio) -> float:
            if ratio is None or not isinstance(ratio, (int, float)):
                return 50.0  # unknown = neutral
            if ratio < 0 or ratio > 1.0:
                return 0.0
            if ratio <= 0.3:
                return 100.0
            elif ratio <= 0.6:
                return 70.0
            elif ratio <= 0.8:
                return 40.0
            else:
                return 10.0

        payout_scores = df["payout_ratio"].apply(_payout_score)

        # 2c. Consistency score
        def _consistency_score(row) -> float:
            total = row["years_of_dividends"]
            if total <= 1:
                return 0.0
            return min(100.0, (row["consecutive_increases"] / (total - 1)) * 100)

        consistency_scores = df.apply(_consistency_score, axis=1)

        # 2d. Growth score (CAGR mapped to 0-100)
        def _growth_score(cagr) -> float:
            if cagr is None:
                return 0.0
            if cagr >= 0.10:
                return 100.0
            elif cagr >= 0.05:
                return 75.0
            elif cagr >= 0.0:
                return 50.0
            else:
                return 0.0

        growth_scores = df["div_cagr"].apply(_growth_score)

        # Phase 3: Blend
        results: list[StrategyResult] = []

        for i, row in df.iterrows():
            score = (0.30 * yield_scores.iloc[i]
                     + 0.30 * payout_scores.iloc[i]
                     + 0.20 * consistency_scores.iloc[i]
                     + 0.20 * growth_scores.iloc[i])
            score = max(0.0, min(100.0, score))

            results.append(StrategyResult(
                ticker=row["ticker"],
                score=score,
                details={
                    "dividend_yield_pct": round(row["div_yield"] * 100, 2),
                    "payout_ratio": round(row["payout_ratio"], 2) if isinstance(row["payout_ratio"], (int, float)) else None,
                    "years_of_dividends": row["years_of_dividends"],
                    "consecutive_increases": row["consecutive_increases"],
                    "dividend_cagr_pct": round(row["div_cagr"] * 100, 1) if row["div_cagr"] is not None else None,
                    "sector": row["sector"],
                },
                confidence=row["confidence"],
            ))

        return results
