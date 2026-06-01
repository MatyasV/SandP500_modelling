"""DataManager — smart fetching layer that resolves data requirements."""

import logging
from typing import Any

import pandas as pd

from sp500.data.cache import SQLiteCache
from sp500.data.fields import DataField
from sp500.data.providers.base import BaseProvider

logger = logging.getLogger(__name__)

_MACRO_FIELDS = frozenset({DataField.RISK_FREE_RATE, DataField.INFLATION_RATE, DataField.GDP_GROWTH})


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
        1. Handle CONSTITUENTS specially (universe-level, not per-ticker)
        2. Check SQLite cache for each (ticker, field) pair
        3. Group missing fields by provider
        4. Fetch from providers in rate-limited batches
        5. Cache the results and return the complete dataset
        """
        # Separate CONSTITUENTS and macro fields from per-ticker fields
        macro_fields_needed = fields & _MACRO_FIELDS
        per_ticker_fields = fields - {DataField.CONSTITUENTS} - _MACRO_FIELDS
        need_constituents = DataField.CONSTITUENTS in fields

        # Step 0: Fetch constituents once if needed
        constituents_df = None
        if need_constituents:
            constituents_df = self.fetch_constituents()

        # Fetch macro data once (e.g. risk-free rate) and cache under "__macro__" sentinel
        macro_data: dict = {}
        if macro_fields_needed:
            # Check cache first (use "__macro__" as the ticker key)
            cached_macro = self.cache.get("__macro__", macro_fields_needed)
            macro_data.update(cached_macro.found)
            if cached_macro.missing:
                # Find a provider for any of the missing macro fields
                provider = None
                for field in cached_macro.missing:
                    provider = self._field_to_provider.get(field)
                    if provider is not None:
                        break
                if provider is not None:
                    fetched = provider.fetch(["__macro__"], cached_macro.missing)
                    if "__macro__" in fetched:
                        new_macro = fetched["__macro__"]
                        self.cache.put("__macro__", new_macro)
                        macro_data.update(new_macro)

        # Step 1: Check cache for each ticker
        all_data: dict[str, dict[DataField, Any]] = {}
        tickers_needing: dict[str, set[DataField]] = {}

        for ticker in tickers:
            if per_ticker_fields:
                cache_result = self.cache.get(ticker, per_ticker_fields)
                all_data[ticker] = dict(cache_result.found)
                if cache_result.missing:
                    tickers_needing[ticker] = cache_result.missing
            else:
                all_data[ticker] = {}

        if tickers_needing:
            cached_count = len(tickers) - len(tickers_needing)
            logger.info("Cache hit for %d tickers, need to fetch %d",
                        cached_count, len(tickers_needing))

            # Step 2: Group missing fields by provider
            provider_requests: dict[BaseProvider, tuple[list[str], set[DataField]]] = {}
            for ticker, missing in tickers_needing.items():
                for field in missing:
                    provider = self._field_to_provider.get(field)
                    if provider is None:
                        logger.warning("No provider for field %s", field.name)
                        continue
                    if provider not in provider_requests:
                        provider_requests[provider] = ([], set())
                    req_tickers, req_fields = provider_requests[provider]
                    if ticker not in req_tickers:
                        req_tickers.append(ticker)
                    req_fields.add(field)

            # Step 3: Fetch from providers
            for provider, (req_tickers, req_fields) in provider_requests.items():
                logger.info("Fetching %d fields for %d tickers from %s",
                            len(req_fields), len(req_tickers), provider.name)
                fetched = provider.fetch(req_tickers, req_fields)

                # Step 4: Cache results and merge
                for ticker, ticker_data in fetched.items():
                    if ticker.startswith("__"):
                        continue  # skip sentinel keys
                    self.cache.put(ticker, ticker_data)
                    if ticker not in all_data:
                        all_data[ticker] = {}
                    all_data[ticker].update(ticker_data)

        # Step 5: Inject constituents into every ticker's data dict
        if need_constituents and constituents_df is not None:
            for ticker in all_data:
                all_data[ticker][DataField.CONSTITUENTS] = constituents_df

        # Inject macro data into every ticker's data dict
        if macro_data:
            for ticker in all_data:
                all_data[ticker].update(macro_data)

        return all_data

    def fetch_constituents(self) -> pd.DataFrame:
        """Fetch the S&P 500 list. Checks cache first, falls back to WikipediaProvider."""
        cached = self.cache.get_constituents()
        if cached is not None:
            logger.info("Using cached constituents list")
            return cached

        # Find the provider that supplies CONSTITUENTS
        provider = self._field_to_provider.get(DataField.CONSTITUENTS)
        if provider is None:
            raise RuntimeError("No provider registered for CONSTITUENTS")

        df = provider.fetch_constituents()
        self.cache.put_constituents(df)
        return df
