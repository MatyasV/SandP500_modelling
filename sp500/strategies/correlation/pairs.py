"""Correlation analysis — pairwise returns correlation, sector matrix, diversification pairs."""

import logging
from typing import Any

import numpy as np
import pandas as pd

from sp500.core.models import CorrelationResult, PairResult
from sp500.data.fields import DataField

logger = logging.getLogger(__name__)


class CorrelationAnalyzer:
    """
    Computes pairwise return correlations across S&P 500 stocks.
    NOT a BaseStrategy — different output type (matrix/pairs, not ranked StrategyResults).
    """

    def __init__(self, config: dict | None = None):
        cfg = (config or {}).get("correlation", {})
        self.lookback_days = cfg.get("lookback_days", 252)

    @property
    def required_fields(self) -> set[DataField]:
        return {DataField.PRICE_HISTORY}

    def filter_universe(self, constituents: pd.DataFrame) -> pd.DataFrame:
        return constituents

    def compute_matrix(self, all_data: dict[str, dict]) -> CorrelationResult:
        """
        Compute N×N pairwise return correlation matrix.

        1. For each ticker with PRICE_HISTORY, compute daily log returns
           using the last lookback_days rows of the Close column.
        2. Build a DataFrame of all returns, aligned by date.
        3. Drop tickers with more than 20% missing returns.
        4. Compute Pearson correlation matrix.
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
            if len(close) < 30:
                continue
            returns = close.pct_change().dropna()
            returns_dict[ticker] = returns

        if not returns_dict:
            logger.warning("No valid price histories found for correlation matrix")
            return CorrelationResult(matrix=pd.DataFrame(), tickers=[])

        # Align on common dates
        returns_df = pd.DataFrame(returns_dict)
        # Drop tickers with > 20% missing values
        min_valid = int(len(returns_df) * 0.8)
        returns_df = returns_df.dropna(axis=1, thresh=min_valid)
        # Forward-fill small gaps, then drop remaining NaN rows
        returns_df = returns_df.ffill(limit=5).dropna(how="any")

        if returns_df.empty or len(returns_df.columns) < 2:
            logger.warning("Insufficient data for correlation matrix after alignment")
            return CorrelationResult(matrix=pd.DataFrame(), tickers=[])

        corr_matrix = returns_df.corr()
        tickers = list(corr_matrix.columns)
        logger.info("Computed %d×%d correlation matrix", len(tickers), len(tickers))
        return CorrelationResult(matrix=corr_matrix, tickers=tickers)

    def find_pairs(self, corr_result: CorrelationResult, top_n: int = 20,
                   mode: str = "diversifying",
                   sector_map: dict[str, str] | None = None) -> list[PairResult]:
        """
        Extract top N pairs from the correlation matrix.

        mode="diversifying": lowest correlation (best for portfolio diversification)
        mode="correlated": highest correlation (pairs trading, cluster identification)

        Returns a list of PairResult sorted by correlation (ascending for diversifying,
        descending for correlated).
        """
        matrix = corr_result.matrix
        if matrix.empty:
            return []

        tickers = corr_result.tickers
        pairs: list[PairResult] = []

        # Extract upper triangle only (i < j to avoid duplicates)
        for i in range(len(tickers)):
            for j in range(i + 1, len(tickers)):
                corr = matrix.iloc[i, j]
                if pd.isna(corr):
                    continue
                t1, t2 = tickers[i], tickers[j]
                pair = PairResult(
                    ticker1=t1,
                    ticker2=t2,
                    correlation=round(float(corr), 4),
                    sector1=sector_map.get(t1, "") if sector_map else "",
                    sector2=sector_map.get(t2, "") if sector_map else "",
                )
                pairs.append(pair)

        if mode == "diversifying":
            pairs.sort(key=lambda p: p.correlation)  # ascending: most negative first
        else:
            pairs.sort(key=lambda p: p.correlation, reverse=True)  # descending: most correlated

        return pairs[:top_n]

    def sector_matrix(self, corr_result: CorrelationResult,
                      sector_map: dict[str, str]) -> pd.DataFrame:
        """
        Aggregate to a sector-level correlation matrix.

        For each pair of sectors (including same-sector pairs), compute the
        mean pairwise correlation of all ticker pairs belonging to those sectors.

        Returns a square DataFrame with sector names as index and columns.
        """
        matrix = corr_result.matrix
        if matrix.empty:
            return pd.DataFrame()

        tickers = corr_result.tickers
        sectors = sorted(set(sector_map.get(t, "Unknown") for t in tickers))

        # Group tickers by sector (only tickers present in the correlation matrix)
        sector_tickers: dict[str, list[str]] = {s: [] for s in sectors}
        for t in tickers:
            s = sector_map.get(t, "Unknown")
            if s in sector_tickers:
                sector_tickers[s].append(t)

        # Compute mean pairwise correlation for each sector pair
        n = len(sectors)
        data = np.zeros((n, n))

        for i, s1 in enumerate(sectors):
            for j, s2 in enumerate(sectors):
                t1_list = sector_tickers[s1]
                t2_list = sector_tickers[s2]
                corr_values = []
                for t1 in t1_list:
                    for t2 in t2_list:
                        if t1 == t2:
                            continue
                        if t1 in matrix.index and t2 in matrix.columns:
                            val = matrix.loc[t1, t2]
                            if not pd.isna(val):
                                corr_values.append(float(val))
                data[i, j] = np.mean(corr_values) if corr_values else 0.0

        return pd.DataFrame(data, index=sectors, columns=sectors).round(3)
