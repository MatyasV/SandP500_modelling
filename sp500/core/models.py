"""Core data models: StrategyResult, CacheResult, and other shared dataclasses."""

from dataclasses import dataclass, field
from typing import Any

from sp500.data.fields import DataField


@dataclass
class StrategyResult:
    ticker: str
    score: float              # normalised 0-100 (higher = more undervalued)
    details: dict[str, Any]   # strategy-specific breakdown (shown in verbose output)
    confidence: float         # 0-1, how complete the input data was for this ticker


@dataclass
class CacheResult:
    found: dict[DataField, Any]     # fields in cache and still fresh
    missing: set[DataField]         # fields that need fetching


@dataclass
class ScreenResult:
    ticker: str
    scores: dict[str, float]       # category -> composite score
    confidences: dict[str, float]  # category -> avg confidence
    details: dict[str, Any]        # merged details keyed as "category_key"


@dataclass
class CorrelationResult:
    matrix: Any              # pd.DataFrame: N×N correlation matrix, tickers as index/columns
    tickers: list[str]


@dataclass
class PairResult:
    ticker1: str
    ticker2: str
    correlation: float
    sector1: str = ""
    sector2: str = ""


@dataclass
class AllocationResult:
    weights: dict[str, float]     # ticker -> weight (should sum to ~1.0)
    expected_return: float        # annualized expected return (decimal, e.g. 0.12 = 12%)
    expected_volatility: float    # annualized volatility (decimal)
    sharpe_ratio: float           # (expected_return - risk_free_rate) / expected_volatility
    tickers: list[str]
    method: str = "max_sharpe"    # "max_sharpe" or "equal_weight"
