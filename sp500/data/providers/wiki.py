"""WikipediaProvider — fetches S&P 500 constituent list from Wikipedia."""

import logging
from typing import Any

import pandas as pd

from sp500.data.fields import DataField
from sp500.data.providers.base import BaseProvider

logger = logging.getLogger(__name__)

_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


class WikipediaProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "Wikipedia"

    def provides(self) -> set[DataField]:
        return {DataField.CONSTITUENTS}

    def fetch(self, tickers: list[str], fields: set[DataField],
              **kwargs) -> dict[str, dict[DataField, Any]]:
        """Fetch S&P 500 constituent list via pandas.read_html."""
        if DataField.CONSTITUENTS not in fields:
            return {}
        df = self.fetch_constituents()
        # Return under a sentinel key; DataManager handles redistribution
        return {"__constituents__": {DataField.CONSTITUENTS: df}}

    def fetch_constituents(self) -> pd.DataFrame:
        """Fetch the S&P 500 constituent table from Wikipedia."""
        logger.info("Fetching S&P 500 constituent list from Wikipedia...")
        tables = pd.read_html(_WIKI_URL)
        df = tables[0]
        # Normalise ticker symbols: Wikipedia uses dots (BRK.B), yfinance uses dashes (BRK-B)
        df["Symbol"] = df["Symbol"].str.strip().str.replace(".", "-", regex=False)
        logger.info("Fetched %d constituents", len(df))
        return df
