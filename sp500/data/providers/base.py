"""BaseProvider ABC — interface for all data source providers."""

from abc import ABC, abstractmethod
from typing import Any

from sp500.data.fields import DataField


class BaseProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name for logging."""
        ...

    @abstractmethod
    def provides(self) -> set[DataField]:
        """Which DataFields this provider can supply."""
        ...

    @abstractmethod
    def fetch(self, tickers: list[str], fields: set[DataField],
              **kwargs) -> dict[str, dict[DataField, Any]]:
        """
        Fetch the requested fields for the given tickers.
        Returns: {ticker: {DataField: data, ...}, ...}
        Only fetches the intersection of `fields` and `self.provides()`.
        Should handle missing data gracefully (return what's available, skip what isn't).
        """
        ...
