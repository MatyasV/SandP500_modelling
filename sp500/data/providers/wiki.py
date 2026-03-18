"""WikipediaProvider — fetches S&P 500 constituent list from Wikipedia."""

from typing import Any

import pandas as pd

from sp500.data.fields import DataField
from sp500.data.providers.base import BaseProvider


class WikipediaProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "Wikipedia"

    def provides(self) -> set[DataField]:
        return {DataField.CONSTITUENTS}

    def fetch(self, tickers: list[str], fields: set[DataField],
              **kwargs) -> dict[str, dict[DataField, Any]]:
        """Fetch S&P 500 constituent list via pandas.read_html."""
        # TODO: Implement Wikipedia scraping with pandas.read_html
        raise NotImplementedError

    def fetch_constituents(self) -> pd.DataFrame:
        """Fetch the S&P 500 constituent table from Wikipedia."""
        # TODO: Implement constituent list scraping
        raise NotImplementedError
