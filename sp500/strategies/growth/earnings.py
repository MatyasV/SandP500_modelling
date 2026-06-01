"""Earnings Trend strategy — Net Income CAGR and trend quality."""

import logging
from typing import Any

import pandas as pd
from scipy.stats import linregress

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


class EarningsTrendStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "earnings"

    @property
    def description(self) -> str:
        return "Earnings trend: Net Income CAGR and trend quality"

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.INCOME_STMT_Q, DataField.INFO}

    def filter_universe(self, constituents: pd.DataFrame) -> pd.DataFrame:
        """Include all sectors — financials are valid for earnings analysis."""
        return constituents

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        try:
            income_stmt_q = data.get(DataField.INCOME_STMT_Q)
            info = data.get(DataField.INFO, {}) or {}

            if income_stmt_q is None or not isinstance(income_stmt_q, pd.DataFrame) or income_stmt_q.empty:
                return None

            net_income_row = _find_row(income_stmt_q, ["Net Income", "Net Income Common Stockholders"])
            if net_income_row is None:
                return None

            net_income_series = income_stmt_q.loc[net_income_row].dropna().sort_index()
            n_quarters = len(net_income_series)

            if n_quarters < 4:
                return None

            first_val = float(net_income_series.iloc[0])
            last_val = float(net_income_series.iloc[-1])

            if first_val <= 0 or last_val <= 0:
                avg_val = float(net_income_series.mean())
                if avg_val <= 0:
                    return None
                growth_rate = 0.05
            else:
                cagr = (last_val / first_val) ** (4 / n_quarters) - 1
                growth_rate = min(cagr, 1.0)
                growth_rate = max(growth_rate, -0.5)

            slope, intercept, r_value, p_value, stderr = linregress(
                range(n_quarters), net_income_series.values
            )

            cagr_score = min(100.0, max(0.0, (growth_rate / 0.30) * 100))

            trend_r2 = r_value ** 2
            if slope < 0:
                trend_r2 = -trend_r2
            trend_quality_score = min(100.0, max(0.0, (trend_r2 + 1) / 2 * 100))

            score = 0.6 * cagr_score + 0.4 * trend_quality_score

            if n_quarters >= 8:
                confidence = 1.0
            else:
                confidence = 0.6  # already guaranteed >= 4 at this point

            return StrategyResult(
                ticker=ticker,
                score=round(float(score), 2),
                details={
                    "eps_cagr_pct": round(growth_rate * 100, 1),
                    "quarters_of_data": n_quarters,
                    "trend_r2": round(r_value ** 2, 3),
                    "latest_net_income_billions": round(last_val / 1e9, 2),
                },
                confidence=confidence,
            )
        except Exception as e:
            logger.debug("EarningsTrendStrategy failed for %s: %s", ticker, e)
            return None
