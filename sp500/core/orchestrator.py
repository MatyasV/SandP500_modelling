"""Orchestrator — ties strategies to data and runs analysis end-to-end."""

from sp500.core.models import StrategyResult
from sp500.data.manager import DataManager
from sp500.strategies.base import BaseStrategy


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
        # TODO: Implement the 5-step orchestration flow
        raise NotImplementedError
