"""Rich terminal report generation."""

from sp500.core.models import StrategyResult


def print_report(results: list[StrategyResult], strategy_name: str,
                 verbose: bool = False) -> None:
    """Print a formatted report to the terminal using rich."""
    # TODO: Implement rich report output
    raise NotImplementedError
