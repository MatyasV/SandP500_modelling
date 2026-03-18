"""Core data models: StrategyResult, CacheResult, and other shared dataclasses."""

from dataclasses import dataclass
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
