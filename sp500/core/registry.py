"""Strategy and provider auto-discovery registry."""

from sp500.data.providers.base import BaseProvider
from sp500.strategies.base import BaseStrategy


def discover_providers() -> list[BaseProvider]:
    """Auto-discover and instantiate all available providers."""
    # TODO: Implement provider discovery
    raise NotImplementedError


def discover_strategies() -> dict[str, BaseStrategy]:
    """Auto-discover and return all available strategies keyed by name."""
    # TODO: Implement strategy discovery
    raise NotImplementedError
