"""DataManager — smart fetching layer that resolves data requirements."""

from typing import Any

import pandas as pd

from sp500.data.cache import SQLiteCache
from sp500.data.fields import DataField
from sp500.data.providers.base import BaseProvider


class DataManager:
    def __init__(self, providers: list[BaseProvider], cache: SQLiteCache, config: dict):
        self.providers = providers
        self.cache = cache
        self.config = config
        self._field_to_provider: dict[DataField, BaseProvider] = self._build_field_map()

    def _build_field_map(self) -> dict[DataField, BaseProvider]:
        """Map each DataField to the provider that supplies it."""
        field_map: dict[DataField, BaseProvider] = {}
        for provider in self.providers:
            for field in provider.provides():
                field_map[field] = provider
        return field_map

    def fetch(self, tickers: list[str], fields: set[DataField]) -> dict[str, dict[DataField, Any]]:
        """
        Fetch only the requested fields for the given tickers.
        1. Check SQLite cache for each (ticker, field) pair
        2. Group missing fields by provider
        3. Fetch from providers in rate-limited batches
        4. Cache the results
        5. Return the complete dataset
        """
        # TODO: Implement the 5-step fetch flow
        raise NotImplementedError

    def fetch_constituents(self) -> pd.DataFrame:
        """Fetch the S&P 500 list. Checks cache first, falls back to WikipediaProvider."""
        # TODO: Implement constituents fetching with cache
        raise NotImplementedError
