"""FREDProvider — macro data via yfinance proxy (no API key required)."""

import logging
from typing import Any

import yfinance

from sp500.data.fields import DataField
from sp500.data.providers.base import BaseProvider

logger = logging.getLogger(__name__)

_FALLBACK_RATE = 0.045  # 4.5% — used if yfinance fetch fails


class FREDProvider(BaseProvider):
    def __init__(self, config: dict | None = None):
        self._fallback = (config or {}).get("fred", {}).get("fallback_risk_free_rate", _FALLBACK_RATE)

    @property
    def name(self) -> str:
        return "FRED"

    def provides(self) -> set[DataField]:
        return {DataField.RISK_FREE_RATE}

    def fetch(self, tickers: list[str], fields: set[DataField],
              **kwargs) -> dict[str, dict[DataField, Any]]:
        """
        Fetch macro data. Returns {"__macro__": {field: value, ...}}.
        Uses "__macro__" as sentinel key (not a ticker symbol).
        """
        if DataField.RISK_FREE_RATE not in fields:
            return {}

        rate = self._fetch_risk_free_rate()
        return {"__macro__": {DataField.RISK_FREE_RATE: rate}}

    def _fetch_risk_free_rate(self) -> float:
        """Fetch 10-year Treasury yield via yfinance ^TNX. Returns rate as decimal (e.g. 0.045)."""
        try:
            tnx = yfinance.Ticker("^TNX")
            hist = tnx.history(period="5d")
            if not hist.empty:
                # ^TNX Close prices are already in percent (4.5 means 4.5%)
                rate = float(hist["Close"].iloc[-1]) / 100.0
                logger.info("Fetched risk-free rate from ^TNX: %.3f", rate)
                return rate
        except Exception as e:
            logger.warning("Failed to fetch ^TNX: %s — using fallback %.3f", e, self._fallback)
        return self._fallback
