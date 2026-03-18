"""Discounted Cash Flow (DCF) strategy — intrinsic value via projected cash flows."""

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


class DCFStrategy(BaseStrategy):
    def __init__(self, config: dict | None = None):
        dcf_cfg = (config or {}).get("dcf", {})
        self.projection_years = dcf_cfg.get("projection_years", 5)
        self.terminal_growth = dcf_cfg.get("terminal_growth_rate", 0.025)
        self.discount_rate = dcf_cfg.get("discount_rate", 0.10)
        self.max_growth_cap = dcf_cfg.get("max_growth_cap", 0.20)

    @property
    def name(self) -> str:
        return "dcf"

    @property
    def description(self) -> str:
        return "DCF: intrinsic value from projected free cash flows"

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.INFO, DataField.CASH_FLOW}

    def filter_universe(self, constituents: pd.DataFrame) -> pd.DataFrame:
        """Exclude financial-sector stocks."""
        return constituents[constituents["GICS Sector"] != "Financials"]

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        """
        DCF valuation:
        1. Extract FCF from cash flow history
        2. Compute CAGR, cap at max_growth_cap
        3. Project FCF forward, compute terminal value
        4. Discount to present, divide by shares outstanding
        """
        info = data.get(DataField.INFO)
        cf_df = data.get(DataField.CASH_FLOW)

        if info is None or not isinstance(info, dict):
            return None
        if cf_df is None or not isinstance(cf_df, pd.DataFrame) or cf_df.empty:
            return None

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        shares = info.get("sharesOutstanding")
        if not price or not shares:
            return None

        # Extract Operating Cash Flow and Capital Expenditure rows
        # Check for "Free Cash Flow" row first (some yfinance versions provide it)
        fcf_row = _find_row(cf_df, ["Free Cash Flow"])
        if fcf_row is not None:
            fcf_series = cf_df.loc[fcf_row].dropna()
        else:
            ocf_row = _find_row(cf_df, [
                "Operating Cash Flow",
                "Total Cash From Operating Activities",
                "Cash Flow From Continuing Operating Activities",
            ])
            capex_row = _find_row(cf_df, [
                "Capital Expenditure",
                "Capital Expenditures",
            ])
            if ocf_row is None or capex_row is None:
                return None

            ocf = cf_df.loc[ocf_row].dropna()
            capex = cf_df.loc[capex_row].dropna()
            common = ocf.index.intersection(capex.index)
            if len(common) < 2:
                return None
            # CapEx is typically negative in yfinance; FCF = OCF - |CapEx|
            fcf_series = ocf[common] - abs(capex[common])

        # Sort chronologically
        fcf_series = fcf_series.sort_index()
        years_available = len(fcf_series)

        if years_available < 2:
            return None

        avg_fcf = fcf_series.mean()
        if avg_fcf <= 0:
            return None

        # Compute CAGR
        first_fcf = float(fcf_series.iloc[0])
        last_fcf = float(fcf_series.iloc[-1])

        if first_fcf <= 0:
            # Can't compute CAGR with non-positive starting value; use simple average growth
            growth_rate = min(0.05, self.max_growth_cap)
        else:
            n_periods = years_available - 1
            growth_rate = (last_fcf / first_fcf) ** (1 / n_periods) - 1
            growth_rate = min(growth_rate, self.max_growth_cap)
            growth_rate = max(growth_rate, 0.0)  # floor at 0 for negative growth

        # Project FCF forward
        base_fcf = float(last_fcf)
        projected = []
        for year in range(1, self.projection_years + 1):
            projected.append(base_fcf * (1 + growth_rate) ** year)

        # Terminal value (Gordon Growth Model)
        terminal_value = (projected[-1] * (1 + self.terminal_growth)
                          / (self.discount_rate - self.terminal_growth))

        # Discount to present value
        npv = 0.0
        for year, fcf in enumerate(projected, start=1):
            npv += fcf / (1 + self.discount_rate) ** year
        npv += terminal_value / (1 + self.discount_rate) ** self.projection_years

        fair_value_per_share = npv / shares

        raw_score = ((fair_value_per_share - price) / fair_value_per_share) * 100
        score = max(0.0, min(100.0, raw_score))

        # Confidence based on years of history
        if years_available >= 5:
            confidence = 1.0
        elif years_available >= 3:
            confidence = 0.6
        else:
            confidence = 0.3

        return StrategyResult(
            ticker=ticker,
            score=score,
            details={
                "fair_value": round(fair_value_per_share, 2),
                "current_price": round(price, 2),
                "growth_rate_pct": round(growth_rate * 100, 1),
                "years_of_data": years_available,
                "latest_fcf": round(last_fcf / 1e9, 2),  # in billions
                "npv_billions": round(npv / 1e9, 2),
            },
            confidence=confidence,
        )
