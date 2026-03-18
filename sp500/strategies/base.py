"""BaseStrategy ABC — interface for all analysis strategies."""

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from sp500.core.models import StrategyResult
from sp500.data.fields import DataField


class BaseStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy identifier, used in CLI and composite references."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line description shown in --list-strategies."""
        ...

    @property
    @abstractmethod
    def required_fields(self) -> set[DataField]:
        """DataFields this strategy needs to run."""
        ...

    @abstractmethod
    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        """
        Run analysis on a single ticker.
        Returns None if there's not enough data to produce a meaningful result.
        """
        ...

    def analyze_all(self, all_data: dict[str, dict[DataField, Any]]) -> list[StrategyResult]:
        """
        Run analysis across the full universe.
        Default implementation: call analyze() per ticker.
        Override for strategies that need cross-stock comparison (e.g. relative valuation).
        """
        results = []
        for ticker, data in all_data.items():
            result = self.analyze(ticker, data)
            if result is not None:
                results.append(result)
        return results

    def filter_universe(self, constituents: pd.DataFrame) -> pd.DataFrame:
        """
        Optional: pre-filter the S&P 500 list before any data is fetched.
        Default: no filtering (analyse all ~500 companies).
        Override to e.g. exclude financial-sector stocks, saving API calls.
        The constituents DataFrame has columns: Symbol, Security, GICS Sector,
        GICS Sub-Industry, Headquarters Location, Date added, CIK, Founded.
        """
        return constituents
