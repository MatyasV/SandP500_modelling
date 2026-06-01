"""Margin Analysis strategy — gross, operating, and net margin levels and trends."""

import logging
from typing import Any

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


class MarginAnalysisStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "margins"

    @property
    def description(self) -> str:
        return "Margin analysis: gross, operating, and net margins"

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.INCOME_STMT_Q}

    def filter_universe(self, constituents: pd.DataFrame) -> pd.DataFrame:
        """Include all sectors — financials may lack Gross Profit but are handled gracefully."""
        return constituents

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        try:
            income_stmt_q = data.get(DataField.INCOME_STMT_Q)

            if income_stmt_q is None or not isinstance(income_stmt_q, pd.DataFrame) or income_stmt_q.empty:
                return None

            revenue_row = _find_row(income_stmt_q, ["Total Revenue", "Revenue", "Net Revenue"])
            gross_row = _find_row(income_stmt_q, ["Gross Profit"])  # optional
            op_row = _find_row(income_stmt_q, ["EBIT", "Operating Income", "Operating Profit"])
            net_row = _find_row(income_stmt_q, ["Net Income", "Net Income Common Stockholders"])

            if revenue_row is None:
                return None

            revenue_series = income_stmt_q.loc[revenue_row].dropna().sort_index()
            n_quarters = len(revenue_series)

            if n_quarters < 4:
                return None

            # Filter out zero or negative revenue points before computing margins
            valid_revenue = revenue_series[revenue_series > 0]
            if len(valid_revenue) < 4:
                return None

            margin_scores: list[float] = []
            details: dict[str, Any] = {}

            margin_definitions = []
            if gross_row is not None:
                margin_definitions.append(("gross", gross_row, "gross_margin_pct"))
            if op_row is not None:
                margin_definitions.append(("operating", op_row, "operating_margin_pct"))
            if net_row is not None:
                margin_definitions.append(("net", net_row, "net_margin_pct"))

            for margin_name, num_row, detail_key in margin_definitions:
                try:
                    numerator_series = income_stmt_q.loc[num_row].dropna().sort_index()
                    common_idx = valid_revenue.index.intersection(numerator_series.index)
                    if len(common_idx) < 4:
                        continue

                    rev_aligned = valid_revenue.loc[common_idx]
                    num_aligned = numerator_series.loc[common_idx]
                    margin_series = num_aligned / rev_aligned

                    # Drop NaN values
                    margin_series = margin_series.dropna()
                    if len(margin_series) < 4:
                        continue

                    current_margin = float(margin_series.iloc[-1])
                    hist_avg = float(margin_series.mean())

                    if pd.isna(current_margin):
                        continue

                    details[detail_key] = round(current_margin * 100, 1)

                    margin_level_score = min(100.0, max(0.0, current_margin * 200))

                    if hist_avg != 0:
                        improvement = (current_margin - hist_avg) / abs(hist_avg)
                        improvement_score = min(100.0, max(0.0, 50.0 + improvement * 100))
                    else:
                        improvement_score = 50.0

                    combined = 0.6 * margin_level_score + 0.4 * improvement_score
                    margin_scores.append(combined)

                    # Track whether this margin is improving or declining for trend label
                    if margin_name == "net":
                        details["margin_trend"] = "improving" if current_margin > hist_avg else "declining"

                except Exception as e:
                    logger.debug("Margin computation failed for %s (%s): %s", ticker, margin_name, e)
                    continue

            if not margin_scores:
                return None

            score = sum(margin_scores) / len(margin_scores)

            if n_quarters >= 8:
                confidence = 1.0
            else:
                confidence = 0.6  # already guaranteed >= 4 at this point

            return StrategyResult(
                ticker=ticker,
                score=round(float(score), 2),
                details=details,
                confidence=confidence,
            )
        except Exception as e:
            logger.debug("MarginAnalysisStrategy failed for %s: %s", ticker, e)
            return None
