"""Momentum strategy — technical signals: RSI, moving averages, 52-week high."""

import logging
from typing import Any

import numpy as np
import pandas as pd

from sp500.core.models import StrategyResult
from sp500.data.fields import DataField
from sp500.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


def _compute_rsi(prices: np.ndarray, period: int = 14) -> float | None:
    """Compute RSI from a price array. Returns None if insufficient data."""
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices[-(period + 1):])
    gains = np.maximum(deltas, 0)
    losses = np.abs(np.minimum(deltas, 0))
    avg_gain = gains.mean()
    avg_loss = losses.mean()
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


class MomentumStrategy(BaseStrategy):
    def __init__(self, config: dict | None = None):
        mom_cfg = (config or {}).get("momentum", {})
        self.rsi_period = mom_cfg.get("rsi_period", 14)
        self.sma_short = mom_cfg.get("sma_short", 50)
        self.sma_long = mom_cfg.get("sma_long", 200)
        self._weights = mom_cfg.get("weights", {})
        self.w_rsi = self._weights.get("rsi", 0.35)
        self.w_ma = self._weights.get("ma_crossover", 0.35)
        self.w_high = self._weights.get("high_proximity", 0.30)

    @property
    def name(self) -> str:
        return "momentum"

    @property
    def description(self) -> str:
        return "Technical momentum: RSI, MA crossover, 52-week high proximity"

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.PRICE_HISTORY}

    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        raise NotImplementedError("MomentumStrategy requires analyze_all()")

    def analyze_all(self, all_data: dict[str, dict[DataField, Any]]) -> list[StrategyResult]:
        """
        Cross-stock momentum scoring:
        1. Compute raw signals per ticker (RSI, MA crossover, 52wk proximity)
        2. Percentile-rank each signal across all tickers
        3. Blend into final score
        """
        # Phase 1: Extract raw signals
        signals: list[dict[str, Any]] = []

        for ticker, data in all_data.items():
            hist = data.get(DataField.PRICE_HISTORY)
            if hist is None or not isinstance(hist, pd.DataFrame) or hist.empty:
                continue

            close = hist["Close"].dropna().values
            if len(close) < self.sma_short:
                continue

            n_days = len(close)
            current_price = float(close[-1])

            # RSI
            rsi = _compute_rsi(close, self.rsi_period)
            if rsi is None:
                continue

            # Moving averages
            sma_short = float(np.mean(close[-self.sma_short:]))
            sma_long_val = float(np.mean(close[-self.sma_long:])) if n_days >= self.sma_long else None
            ma_signal = ((sma_short - sma_long_val) / sma_long_val) if sma_long_val else None

            # 52-week high proximity (252 trading days)
            lookback = min(n_days, 252)
            high_52wk = float(np.max(close[-lookback:]))
            pct_from_high = current_price / high_52wk if high_52wk > 0 else None

            # Confidence
            if n_days >= 252:
                confidence = 1.0
            elif n_days >= 126:
                confidence = 0.6
            else:
                confidence = 0.3

            signals.append({
                "ticker": ticker,
                "rsi": rsi,
                "ma_signal": ma_signal,
                "pct_from_high": pct_from_high,
                "sma_short": round(sma_short, 2),
                "sma_long": round(sma_long_val, 2) if sma_long_val else None,
                "confidence": confidence,
                "n_days": n_days,
            })

        if not signals:
            return []

        # Phase 2: Percentile ranking
        df = pd.DataFrame(signals)

        def _percentile_rank(series: pd.Series) -> pd.Series:
            valid = series.dropna()
            if len(valid) < 2:
                return pd.Series(50.0, index=series.index)
            return series.rank(pct=True, na_option="keep") * 100

        rsi_pctl = _percentile_rank(df["rsi"])
        ma_pctl = _percentile_rank(df["ma_signal"]) if df["ma_signal"].notna().sum() > 1 else pd.Series(50.0, index=df.index)
        high_pctl = _percentile_rank(df["pct_from_high"]) if df["pct_from_high"].notna().sum() > 1 else pd.Series(50.0, index=df.index)

        # Phase 3: Blend
        results: list[StrategyResult] = []

        for i, row in df.iterrows():
            rsi_score = rsi_pctl.iloc[i] if pd.notna(rsi_pctl.iloc[i]) else 50.0
            ma_score = ma_pctl.iloc[i] if pd.notna(ma_pctl.iloc[i]) else 50.0
            high_score = high_pctl.iloc[i] if pd.notna(high_pctl.iloc[i]) else 50.0

            score = self.w_rsi * rsi_score + self.w_ma * ma_score + self.w_high * high_score
            score = max(0.0, min(100.0, score))

            results.append(StrategyResult(
                ticker=row["ticker"],
                score=score,
                details={
                    "rsi": round(row["rsi"], 1),
                    "sma_short": row["sma_short"],
                    "sma_long": row["sma_long"],
                    "pct_from_52wk_high": round(row["pct_from_high"] * 100, 1) if row["pct_from_high"] is not None else None,
                    "ma_signal": round(row["ma_signal"] * 100, 2) if row["ma_signal"] is not None else None,
                },
                confidence=row["confidence"],
            ))

        return results
