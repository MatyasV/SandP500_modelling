"""Output formatters: table, CSV, JSON."""

from sp500.core.models import StrategyResult


def format_table(results: list[StrategyResult], verbose: bool = False) -> str:
    """Format results as a rich terminal table."""
    # TODO: Implement rich table formatting
    raise NotImplementedError


def format_csv(results: list[StrategyResult], output_path: str | None = None) -> str:
    """Format results as CSV."""
    # TODO: Implement CSV formatting
    raise NotImplementedError


def format_json(results: list[StrategyResult]) -> str:
    """Format results as JSON."""
    # TODO: Implement JSON formatting
    raise NotImplementedError
