"""Volatility risk strategy — annualized vol, beta, and max drawdown."""

import logging
from math import sqrt
from typing import Any

import pandas as pd

from sp500.core.models import StrategyResult
from sp500.data.fields import DataField
from sp500.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class VolatilityStrategy(BaseStrategy):
    def __init__(self, config=None):
        cfg = (config or {}).get("volatility", {})
        self.w_vol = cfg.get("w_vol", 0.40)
        self.w_beta = cfg.get("w_beta", 0.30)
        self.w_dd = cfg.get("w_dd", 0.30)

    @property
    def name(self) -> str:
        return "volatility"

    @property
    def description(self) -> str:
        return "Volatility risk: annualized vol, beta, and max drawdown"

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.PRICE_HISTORY, DataField.INFO}

    def filter_universe(self, constituents: pd.DataFrame) -> pd.DataFrame:
        return constituents

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        raise NotImplementedError("VolatilityStrategy requires analyze_all()")

    def analyze_all(self, all_data: dict[str, dict[DataField, Any]]) -> list[StrategyResult]:
        tickers_list: list[str] = []
        vols: list[float] = []
        betas: list[float] = []
        drawdowns: list[float] = []
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
                ann_vol = daily_returns.std() * sqrt(252)

                info = data.get(DataField.INFO)
                if info and isinstance(info, dict):
                    beta_raw = info.get("beta")
                    beta = float(beta_raw) if beta_raw is not None else 1.0
                else:
                    beta = 1.0

                cummax = close.expanding().max()
                drawdown_series = (cummax - close) / cummax
                max_drawdown = float(drawdown_series.max())
                n_rows = len(close)

                tickers_list.append(ticker)
                vols.append(float(ann_vol))
                betas.append(beta)
                drawdowns.append(max_drawdown)
                n_rows_list.append(n_rows)
                raw_metrics[ticker] = {
                    "ann_vol": float(ann_vol),
                    "beta": beta,
                    "max_drawdown": max_drawdown,
                    "n_rows": n_rows,
                }

            except Exception as e:
                logger.warning("VolatilityStrategy: failed to process %s: %s", ticker, e)
                continue

        if not tickers_list:
            return []

        vol_pct = pd.Series(vols).rank(pct=True).values * 100
        beta_pct = pd.Series(betas).rank(pct=True).values * 100
        dd_pct = pd.Series(drawdowns).rank(pct=True).values * 100

        results: list[StrategyResult] = []
        for i, ticker in enumerate(tickers_list):
            m = raw_metrics[ticker]
            score = (
                self.w_vol * vol_pct[i]
                + self.w_beta * beta_pct[i]
                + self.w_dd * dd_pct[i]
            )
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
                    "ann_vol_pct": round(m["ann_vol"] * 100, 1),
                    "beta": round(m["beta"], 2),
                    "max_drawdown_pct": round(m["max_drawdown"] * 100, 1),
                    "vol_percentile": round(float(vol_pct[i]), 1),
                    "beta_percentile": round(float(beta_pct[i]), 1),
                    "dd_percentile": round(float(dd_pct[i]), 1),
                },
                confidence=confidence,
            ))

        return results
