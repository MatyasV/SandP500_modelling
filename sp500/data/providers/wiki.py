"""WikipediaProvider — fetches S&P 500 constituent list from Wikipedia."""

import logging
from io import StringIO
from typing import Any

import pandas as pd
import requests

from sp500.data.fields import DataField
from sp500.data.providers.base import BaseProvider

logger = logging.getLogger(__name__)

_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_HEADERS = {"User-Agent": "SP500AnalysisEngine/0.1 (educational project)"}


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
        resp = requests.get(_WIKI_URL, headers=_HEADERS)
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        df = tables[0]
        # Normalise ticker symbols: Wikipedia uses dots (BRK.B), yfinance uses dashes (BRK-B)
        df["Symbol"] = df["Symbol"].str.strip().str.replace(".", "-", regex=False)
        logger.info("Fetched %d constituents", len(df))
        return df
