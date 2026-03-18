"""Quality/Safety strategy — financial health: leverage, coverage, ROE, stability."""

import logging
from typing import Any

import numpy as np
import pandas as pd

from sp500.core.models import StrategyResult
from sp500.data.fields import DataField
from sp500.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


def _find_row(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Find a row in a DataFrame by case-insensitive substring match."""
    for idx in df.index:
        idx_lower = str(idx).lower()
        for candidate in candidates:
            if candidate.lower() in idx_lower:
                return idx
    return None


def _map_to_score(value: float, best: float, worst: float) -> float:
    """Linearly map a value to a 0-100 score where best=100 and worst=0."""
    if best == worst:
        return 50.0
    score = (value - worst) / (best - worst) * 100
    return max(0.0, min(100.0, score))


class QualityStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "quality"

    @property
    def description(self) -> str:
        return "Financial quality/safety: leverage, coverage, profitability, stability"

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.INFO, DataField.BALANCE_SHEET, DataField.INCOME_STMT}

    def filter_universe(self, constituents: pd.DataFrame) -> pd.DataFrame:
        """Exclude financial-sector stocks (different capital structure)."""
        return constituents[constituents["GICS Sector"] != "Financials"]

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        """
        Quality scoring:
        1. Leverage (D/E ratio) — lower is better
        2. Interest coverage (EBIT / interest) — higher is better
        3. ROE — higher is better
        4. Revenue stability (low coefficient of variation) — lower is better
        """
        info = data.get(DataField.INFO)
        bs_df = data.get(DataField.BALANCE_SHEET)
        is_df = data.get(DataField.INCOME_STMT)

        if info is None or not isinstance(info, dict):
            return None

        sub_scores: list[float] = []
        details: dict[str, Any] = {}
        years_of_data = 0

        # 1. Leverage: debt-to-equity from INFO
        de = info.get("debtToEquity")
        if de is not None and isinstance(de, (int, float)):
            de_ratio = de / 100.0 if de > 10 else de  # yfinance sometimes returns as percentage
            leverage_score = _map_to_score(de_ratio, best=0.0, worst=3.0)
            sub_scores.append(leverage_score)
            details["debt_to_equity"] = round(de_ratio, 2)

        # 2. ROE from INFO
        roe = info.get("returnOnEquity")
        if roe is not None and isinstance(roe, (int, float)):
            roe_score = _map_to_score(roe, best=0.25, worst=0.0)
            sub_scores.append(roe_score)
            details["roe_pct"] = round(roe * 100, 1)

        # 3. Interest coverage from income statement
        if is_df is not None and isinstance(is_df, pd.DataFrame) and not is_df.empty:
            ebit_row = _find_row(is_df, ["EBIT", "Operating Income"])
            interest_row = _find_row(is_df, ["Interest Expense"])

            if ebit_row is not None and interest_row is not None:
                ebit_vals = is_df.loc[ebit_row].dropna()
                interest_vals = is_df.loc[interest_row].dropna()
                common = ebit_vals.index.intersection(interest_vals.index)

                if len(common) > 0:
                    latest_ebit = float(ebit_vals[common[0]])
                    latest_interest = abs(float(interest_vals[common[0]]))
                    if latest_interest > 0:
                        coverage = latest_ebit / latest_interest
                        coverage_score = _map_to_score(coverage, best=10.0, worst=1.5)
                        sub_scores.append(coverage_score)
                        details["interest_coverage"] = round(coverage, 1)

            # 4. Revenue stability from income statement
            revenue_row = _find_row(is_df, ["Total Revenue", "Revenue"])
            if revenue_row is not None:
                rev_vals = is_df.loc[revenue_row].dropna()
                years_of_data = len(rev_vals)
                if years_of_data >= 2:
                    rev_arr = rev_vals.values.astype(float)
                    mean_rev = np.mean(rev_arr)
                    if mean_rev > 0:
                        cv = float(np.std(rev_arr) / mean_rev)
                        stability_score = _map_to_score(cv, best=0.0, worst=0.3)
                        sub_scores.append(stability_score)
                        details["revenue_cv"] = round(cv, 3)

        if not sub_scores:
            return None

        score = sum(sub_scores) / len(sub_scores)
        details["metrics_used"] = len(sub_scores)
        details["years_of_data"] = years_of_data

        # Confidence based on data completeness
        if years_of_data >= 4 and len(sub_scores) >= 3:
            confidence = 1.0
        elif years_of_data >= 2 and len(sub_scores) >= 2:
            confidence = 0.6
        else:
            confidence = 0.3

        return StrategyResult(
            ticker=ticker,
            score=max(0.0, min(100.0, score)),
            details=details,
            confidence=confidence,
        )
