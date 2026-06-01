"""Revenue Trend strategy — revenue CAGR and trend quality."""

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


class RevenueTrendStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "revenue"

    @property
    def description(self) -> str:
        return "Revenue trend: revenue CAGR and trend quality"

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.INCOME_STMT_Q}

    def filter_universe(self, constituents: pd.DataFrame) -> pd.DataFrame:
        """Include all sectors."""
        return constituents

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        try:
            income_stmt_q = data.get(DataField.INCOME_STMT_Q)

            if income_stmt_q is None or not isinstance(income_stmt_q, pd.DataFrame) or income_stmt_q.empty:
                return None

            rev_row = _find_row(income_stmt_q, ["Total Revenue", "Revenue", "Net Revenue"])
            if rev_row is None:
                return None

            revenue_series = income_stmt_q.loc[rev_row].dropna().sort_index()
            n_quarters = len(revenue_series)

            if n_quarters < 4:
                return None

            first_val = float(revenue_series.iloc[0])
            last_val = float(revenue_series.iloc[-1])

            if first_val <= 0 or last_val <= 0:
                avg_val = float(revenue_series.mean())
                if avg_val <= 0:
                    return None
                growth_rate = 0.03
            else:
                cagr = (last_val / first_val) ** (4 / n_quarters) - 1
                growth_rate = min(cagr, 0.5)
                growth_rate = max(growth_rate, -0.3)

            slope, intercept, r_value, p_value, stderr = linregress(
                range(n_quarters), revenue_series.values
            )

            cagr_score = min(100.0, max(0.0, (growth_rate / 0.20) * 100))

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
                    "revenue_cagr_pct": round(growth_rate * 100, 1),
                    "quarters_of_data": n_quarters,
                    "trend_r2": round(r_value ** 2, 3),
                    "latest_revenue_billions": round(last_val / 1e9, 2),
                },
                confidence=confidence,
            )
        except Exception as e:
            logger.debug("RevenueTrendStrategy failed for %s: %s", ticker, e)
            return None
