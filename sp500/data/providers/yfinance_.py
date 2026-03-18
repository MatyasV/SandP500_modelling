"""YFinanceProvider — fetches market data and financials via yfinance."""

import logging
import time
from typing import Any

import pandas as pd
import yfinance

from sp500.data.fields import DataField
from sp500.data.providers.base import BaseProvider

logger = logging.getLogger(__name__)

# Maps DataField to a callable that extracts data from a yfinance Ticker object
_FIELD_ACCESSORS: dict[DataField, Any] = {
    DataField.INFO: lambda t: t.info,
    DataField.INCOME_STMT: lambda t: t.income_stmt,
    DataField.INCOME_STMT_Q: lambda t: t.quarterly_income_stmt,
    DataField.BALANCE_SHEET: lambda t: t.balance_sheet,
    DataField.BALANCE_SHEET_Q: lambda t: t.quarterly_balance_sheet,
    DataField.CASH_FLOW: lambda t: t.cashflow,
    DataField.CASH_FLOW_Q: lambda t: t.quarterly_cashflow,
    DataField.PRICE_HISTORY: lambda t: t.history(period="5y"),
    DataField.DIVIDENDS: lambda t: t.dividends,
    DataField.ANALYST_TARGETS: lambda t: t.analyst_price_targets,
    DataField.RECOMMENDATIONS: lambda t: t.recommendations,
    DataField.INSTITUTIONAL_HOLDERS: lambda t: t.institutional_holders,
}


class YFinanceProvider(BaseProvider):
    def __init__(self, config: dict | None = None):
        rl = (config or {}).get("rate_limits", {}).get("yfinance", {})
        self._delay = rl.get("delay_seconds", 0.5)
        self._batch_size = rl.get("batch_size", 50)
        self._batch_delay = rl.get("batch_delay", 10)

    @property
    def name(self) -> str:
        return "yfinance"

    def provides(self) -> set[DataField]:
        return {
            DataField.INFO,
            DataField.INCOME_STMT, DataField.INCOME_STMT_Q,
            DataField.BALANCE_SHEET, DataField.BALANCE_SHEET_Q,
            DataField.CASH_FLOW, DataField.CASH_FLOW_Q,
            DataField.PRICE_HISTORY, DataField.DIVIDENDS,
            DataField.ANALYST_TARGETS, DataField.RECOMMENDATIONS,
            DataField.INSTITUTIONAL_HOLDERS,
        }

    def fetch(self, tickers: list[str], fields: set[DataField],
              **kwargs) -> dict[str, dict[DataField, Any]]:
        """Fetch requested fields from yfinance, respecting rate limits."""
        relevant = fields & self.provides()
        if not relevant:
            return {}

        result: dict[str, dict[DataField, Any]] = {}

        for i, ticker in enumerate(tickers):
            # Rate limiting: delay between tickers, extra delay between batches
            if i > 0:
                if i % self._batch_size == 0:
                    logger.info("Batch boundary at ticker %d, sleeping %ds...",
                                i, self._batch_delay)
                    time.sleep(self._batch_delay)
                else:
                    time.sleep(self._delay)

            try:
                t = yfinance.Ticker(ticker)
                ticker_data: dict[DataField, Any] = {}

                for field in relevant:
                    accessor = _FIELD_ACCESSORS.get(field)
                    if accessor is None:
                        continue
                    try:
                        val = accessor(t)
                        # Skip None or empty DataFrames/Series
                        if val is None:
                            continue
                        if isinstance(val, (pd.DataFrame, pd.Series)) and val.empty:
                            continue
                        ticker_data[field] = val
                    except Exception as e:
                        logger.warning("Failed to fetch %s for %s: %s",
                                       field.name, ticker, e)

                if ticker_data:
                    result[ticker] = ticker_data

                if (i + 1) % 50 == 0:
                    logger.info("Fetched %d / %d tickers", i + 1, len(tickers))

            except Exception as e:
                logger.warning("Failed to create Ticker for %s: %s", ticker, e)

        logger.info("Fetched data for %d / %d tickers", len(result), len(tickers))
        return result
