"""Orchestrator — ties strategies to data and runs analysis end-to-end."""

import logging

from sp500.core.models import StrategyResult
from sp500.data.manager import DataManager
from sp500.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def run(self, strategy: BaseStrategy, top_n: int = 20) -> list[StrategyResult]:
        """
        Run a single strategy (including composite) end-to-end:
        1. Fetch S&P 500 constituents
        2. Let strategy filter the universe (e.g. exclude financials)
        3. Fetch ONLY the DataFields this strategy declared
        4. Run analysis
        5. Sort by score descending, return top N
        """
        # Step 1: Get constituents
        logger.info("Fetching S&P 500 constituents...")
        constituents = self.data_manager.fetch_constituents()
        logger.info("Got %d constituents", len(constituents))

        # Step 2: Filter universe
        filtered = strategy.filter_universe(constituents)
        tickers = filtered["Symbol"].tolist()
        logger.info("After filtering: %d tickers for strategy '%s'",
                     len(tickers), strategy.name)

        # Step 3: Fetch required data
        logger.info("Fetching data for fields: %s",
                     {f.name for f in strategy.required_fields})
        all_data = self.data_manager.fetch(tickers, strategy.required_fields)
        logger.info("Got data for %d tickers", len(all_data))

        # Step 4: Run analysis
        logger.info("Running analysis...")
        results = strategy.analyze_all(all_data)
        logger.info("Got %d results", len(results))

        # Step 5: Sort and return top N
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_n]
