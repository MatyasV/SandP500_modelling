"""Portfolio optimiser — mean-variance optimisation for S&P 500 stocks."""

import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from sp500.core.models import AllocationResult
from sp500.data.fields import DataField

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """
    Portfolio construction via mean-variance optimisation.
    NOT a BaseStrategy — different output type (AllocationResult, not StrategyResult).

    Supports:
      - equal_weight(): simple 1/N baseline
      - optimize_max_sharpe(): maximise Sharpe ratio via SLSQP
      - compute_efficient_frontier(): sample random portfolios for scatter plot
    """

    def __init__(self, config: dict | None = None):
        cfg = (config or {}).get("portfolio", {})
        self.lookback_days = cfg.get("lookback_days", 252)
        self.min_tickers = cfg.get("min_tickers", 2)

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.PRICE_HISTORY}

    def _build_returns(self, all_data: dict[str, dict]) -> pd.DataFrame:
        """
        Build aligned daily returns DataFrame from price histories.
        - Use last lookback_days rows of Close column per ticker
        - Require at least 60 rows of price data
        - Drop columns with > 20% NaN after alignment
        """
        returns_dict: dict[str, pd.Series] = {}

        for ticker, data in all_data.items():
            if ticker.startswith("__"):
                continue
            hist = data.get(DataField.PRICE_HISTORY)
            if hist is None or not isinstance(hist, pd.DataFrame) or hist.empty:
                continue
            if "Close" not in hist.columns:
                continue
            close = hist["Close"].tail(self.lookback_days)
            if len(close) < 60:
                continue
            returns = close.pct_change().dropna()
            returns_dict[ticker] = returns

        if not returns_dict:
            return pd.DataFrame()

        df = pd.DataFrame(returns_dict)
        # Drop tickers with > 20% missing values
        min_valid = int(len(df) * 0.8)
        df = df.dropna(axis=1, thresh=min_valid)
        df = df.fillna(0)  # fill remaining gaps with 0 (no movement)
        return df

    def equal_weight(self, all_data: dict[str, dict]) -> AllocationResult | None:
        """Simple 1/N equal-weight portfolio. Returns None if no valid tickers."""
        returns_df = self._build_returns(all_data)
        if returns_df.empty:
            return None
        tickers = list(returns_df.columns)
        n = len(tickers)
        if n < 1:
            return None

        mean_ret = returns_df.mean() * 252
        cov = returns_df.cov() * 252
        weights = np.ones(n) / n
        port_ret = float(weights @ mean_ret)
        port_vol = float(np.sqrt(weights @ cov.values @ weights))

        return AllocationResult(
            weights={t: round(1.0 / n, 4) for t in tickers},
            expected_return=round(port_ret, 4),
            expected_volatility=round(port_vol, 4),
            sharpe_ratio=0.0,  # no risk-free rate for baseline
            tickers=tickers,
            method="equal_weight",
        )

    def optimize_max_sharpe(self, all_data: dict[str, dict],
                            risk_free_rate: float = 0.045) -> AllocationResult | None:
        """
        Find the portfolio weights that maximise the Sharpe ratio.

        Uses scipy.optimize.minimize with SLSQP:
          - Objective: minimise negative Sharpe = -(return - rf) / vol
          - Constraints: weights sum to 1
          - Bounds: each weight in [0, 1] (long-only, no short selling)

        Falls back to equal-weight if optimisation fails or not enough tickers.
        """
        returns_df = self._build_returns(all_data)
        if returns_df.empty or len(returns_df.columns) < self.min_tickers:
            logger.warning("Not enough tickers for optimisation (need >= %d, got %d)",
                           self.min_tickers, len(returns_df.columns) if not returns_df.empty else 0)
            return None

        mean_ret = returns_df.mean() * 252
        cov = returns_df.cov() * 252
        n = len(mean_ret)
        tickers = list(mean_ret.index)

        cov_np = cov.values.astype(float)
        mean_ret_np = mean_ret.values.astype(float)

        def neg_sharpe(w: np.ndarray) -> float:
            port_ret = float(w @ mean_ret_np)
            port_vol = float(np.sqrt(w @ cov_np @ w))
            if port_vol < 1e-10:
                return 0.0
            return -(port_ret - risk_free_rate) / port_vol

        x0 = np.ones(n) / n
        constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0}]
        bounds = [(0.0, 1.0)] * n

        opt_result = minimize(
            neg_sharpe, x0, method="SLSQP",
            bounds=bounds, constraints=constraints,
            options={"maxiter": 1000, "ftol": 1e-9},
        )

        if opt_result.success and not np.any(np.isnan(opt_result.x)):
            weights = opt_result.x
            # Clip small negatives from numerical noise, renormalise
            weights = np.clip(weights, 0, 1)
            weights /= weights.sum()
        else:
            logger.warning("Optimisation did not converge (status %d: %s), "
                           "falling back to equal-weight", opt_result.status, opt_result.message)
            weights = np.ones(n) / n

        port_ret = float(weights @ mean_ret_np)
        port_vol = float(np.sqrt(weights @ cov_np @ weights))
        sharpe = (port_ret - risk_free_rate) / port_vol if port_vol > 1e-10 else 0.0

        return AllocationResult(
            weights={t: round(float(w), 4) for t, w in zip(tickers, weights)},
            expected_return=round(port_ret, 4),
            expected_volatility=round(port_vol, 4),
            sharpe_ratio=round(sharpe, 3),
            tickers=tickers,
            method="max_sharpe",
        )

    def compute_efficient_frontier(self, all_data: dict[str, dict],
                                   n_portfolios: int = 200,
                                   risk_free_rate: float = 0.045) -> list[dict]:
        """
        Generate n_portfolios random portfolios to approximate the efficient frontier.

        Returns a list of dicts: [{"vol": float, "return": float, "sharpe": float}, ...]
        Used for the frontier scatter plot.
        """
        returns_df = self._build_returns(all_data)
        if returns_df.empty or len(returns_df.columns) < 2:
            return []

        mean_ret = returns_df.mean() * 252
        cov = returns_df.cov() * 252
        n = len(mean_ret)
        cov_np = cov.values.astype(float)
        mean_ret_np = mean_ret.values.astype(float)

        np.random.seed(42)
        results = []
        for _ in range(n_portfolios):
            # Random weights via Dirichlet distribution (uniform on simplex)
            w = np.random.dirichlet(np.ones(n))
            port_ret = float(w @ mean_ret_np)
            port_vol = float(np.sqrt(w @ cov_np @ w))
            sharpe = (port_ret - risk_free_rate) / port_vol if port_vol > 1e-10 else 0.0
            results.append({
                "vol": round(port_vol, 4),
                "return": round(port_ret, 4),
                "sharpe": round(sharpe, 3),
            })

        return results
