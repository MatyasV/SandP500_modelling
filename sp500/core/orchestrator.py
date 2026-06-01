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
        self.constituents = constituents
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

    def run_screen(self, strategies: dict[str, BaseStrategy], top_n: int = 20,
                   filters: dict[str, tuple] | None = None) -> list:
        """
        Run multiple category strategies, merge results into ScreenResults.

        strategies: dict of category_name -> strategy (typically composites)
        filters: dict of category_name -> (min_score, max_score) where None means no bound
                 e.g. {"undervalue": (50, None), "risk": (None, 30), "growth": (40, None)}
        """
        from sp500.core.models import ScreenResult

        # Fetch constituents once, shared across all categories
        logger.info("Fetching S&P 500 constituents for screen...")
        constituents = self.data_manager.fetch_constituents()
        self.constituents = constituents
        logger.info("Got %d constituents", len(constituents))

        # Run each category strategy independently
        category_results: dict[str, dict[str, StrategyResult]] = {}
        for cat_name, strategy in strategies.items():
            logger.info("Running %s strategy for screen...", cat_name)
            filtered = strategy.filter_universe(constituents)
            tickers = filtered["Symbol"].tolist()
            all_data = self.data_manager.fetch(tickers, strategy.required_fields)
            results = strategy.analyze_all(all_data)
            category_results[cat_name] = {r.ticker: r for r in results}
            logger.info("Got %d %s results", len(results), cat_name)

        # Merge: include any ticker appearing in at least one category
        if not category_results:
            return []
        all_tickers: set[str] = set()
        for by_ticker in category_results.values():
            all_tickers.update(by_ticker.keys())

        screen_results: list[ScreenResult] = []
        for ticker in all_tickers:
            scores: dict[str, float] = {}
            confidences: dict[str, float] = {}
            details: dict = {}
            for cat_name, by_ticker in category_results.items():
                if ticker in by_ticker:
                    r = by_ticker[ticker]
                    scores[cat_name] = round(r.score, 1)
                    confidences[cat_name] = round(r.confidence, 2)
                    for k, v in r.details.items():
                        details[f"{cat_name}_{k}"] = v
            screen_results.append(ScreenResult(
                ticker=ticker,
                scores=scores,
                confidences=confidences,
                details=details,
            ))

        # Apply score filters
        if filters:
            for cat, (lo, hi) in filters.items():
                screen_results = [
                    r for r in screen_results
                    if cat in r.scores
                    and (lo is None or r.scores[cat] >= lo)
                    and (hi is None or r.scores[cat] <= hi)
                ]

        # Sort by first category's score descending
        first_cat = next(iter(strategies))
        screen_results.sort(key=lambda r: r.scores.get(first_cat, 0.0), reverse=True)
        return screen_results[:top_n]
