"""Risk-adjusted returns strategy — inverted Sharpe and Sortino ratios."""

import logging
from math import sqrt
from typing import Any

import pandas as pd

from sp500.core.models import StrategyResult
from sp500.data.fields import DataField
from sp500.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class RiskAdjustedReturnsStrategy(BaseStrategy):
    def __init__(self, config=None):
        cfg = (config or {}).get("risk_adjusted", {})
        self.risk_free_rate = cfg.get("risk_free_rate", 0.05)
        self.w_sharpe = cfg.get("w_sharpe", 0.50)
        self.w_sortino = cfg.get("w_sortino", 0.50)

    @property
    def name(self) -> str:
        return "risk_adjusted"

    @property
    def description(self) -> str:
        return "Risk-adjusted returns: inverted Sharpe and Sortino ratios"

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.PRICE_HISTORY, DataField.RISK_FREE_RATE}

    def filter_universe(self, constituents: pd.DataFrame) -> pd.DataFrame:
        return constituents

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        raise NotImplementedError("RiskAdjustedReturnsStrategy requires analyze_all()")

    def analyze_all(self, all_data: dict[str, dict[DataField, Any]]) -> list[StrategyResult]:
        # Get live risk-free rate (injected by FREDProvider via DataManager macro handling)
        # Fall back to config value if not available
        rfr = self.risk_free_rate  # config fallback
        for ticker_data in all_data.values():
            live_rfr = ticker_data.get(DataField.RISK_FREE_RATE)
            if live_rfr is not None:
                rfr = float(live_rfr)
                break

        tickers_list: list[str] = []
        sharpes: list[float] = []
        sortinos: list[float] = []
        n_rows_list: list[int] = []
        raw_metrics: dict[str, dict] = {}

        for ticker, data in all_data.items():
            price_history = data.get(DataField.PRICE_HISTORY)
            if price_history is None or not isinstance(price_history, pd.DataFrame) or price_history.empty:
                continue

            try:
                close = price_history["Close"]
                if not isinstance(close, pd.Series):
                    close = pd.Series(close)
                close = close.dropna()
                if close.empty:
                    continue

                daily_returns = close.pct_change().dropna()
                ann_return = (1 + daily_returns.mean()) ** 252 - 1
                ann_vol = daily_returns.std() * sqrt(252)

                sharpe = (ann_return - rfr) / ann_vol if ann_vol > 0 else 0.0

                neg_returns = daily_returns[daily_returns < 0]
                if len(neg_returns) > 0:
                    downside_std = neg_returns.std() * sqrt(252)
                else:
                    downside_std = ann_vol

                sortino = (ann_return - rfr) / downside_std if downside_std > 0 else 0.0

                n_rows = len(close)

                tickers_list.append(ticker)
                sharpes.append(float(sharpe))
                sortinos.append(float(sortino))
                n_rows_list.append(n_rows)
                raw_metrics[ticker] = {
                    "sharpe": float(sharpe),
                    "sortino": float(sortino),
                    "ann_return": float(ann_return),
                    "ann_vol": float(ann_vol),
                    "n_rows": n_rows,
                }

            except Exception as e:
                logger.warning("RiskAdjustedReturnsStrategy: failed to process %s: %s", ticker, e)
                continue

        if not tickers_list:
            return []

        sharpe_pct = pd.Series(sharpes).rank(pct=True).values * 100
        sortino_pct = pd.Series(sortinos).rank(pct=True).values * 100

        results: list[StrategyResult] = []
        for i, ticker in enumerate(tickers_list):
            m = raw_metrics[ticker]

            inv_sharpe = 100.0 - sharpe_pct[i]
            inv_sortino = 100.0 - sortino_pct[i]
            score = self.w_sharpe * inv_sharpe + self.w_sortino * inv_sortino
            score = float(max(0.0, min(100.0, score)))

            n = m["n_rows"]
            if n >= 252:
                confidence = 1.0
            elif n >= 126:
                confidence = 0.6
            else:
                confidence = 0.3

            results.append(StrategyResult(
                ticker=ticker,
                score=score,
                details={
                    "sharpe": round(m["sharpe"], 2),
                    "sortino": round(m["sortino"], 2),
                    "ann_return_pct": round(m["ann_return"] * 100, 1),
                    "ann_vol_pct": round(m["ann_vol"] * 100, 1),
                    "sharpe_percentile": round(float(sharpe_pct[i]), 1),
                    "sortino_percentile": round(float(sortino_pct[i]), 1),
                },
                confidence=confidence,
            ))

        return results
