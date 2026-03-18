"""Strategy and provider auto-discovery registry."""

from sp500.data.providers.base import BaseProvider
from sp500.strategies.base import BaseStrategy


def discover_providers(config: dict | None = None) -> list[BaseProvider]:
    """Instantiate all available providers."""
    from sp500.data.providers.wiki import WikipediaProvider
    from sp500.data.providers.yfinance_ import YFinanceProvider
    return [WikipediaProvider(), YFinanceProvider(config)]


def discover_strategies(config: dict | None = None) -> dict[str, BaseStrategy]:
    """Instantiate all available strategies keyed by name."""
    from sp500.strategies.undervalue.graham import GrahamStrategy
    from sp500.strategies.undervalue.dcf import DCFStrategy
    from sp500.strategies.undervalue.relative import RelativeStrategy
    from sp500.strategies.undervalue.composite import CompositeStrategy

    graham = GrahamStrategy()
    dcf = DCFStrategy(config)
    relative = RelativeStrategy()

    composite_cfg = (config or {}).get("composite", {})
    weights = composite_cfg.get("default_weights")
    weight_by_confidence = composite_cfg.get("weight_by_confidence", True)

    composite = CompositeStrategy(
        strategies=[graham, dcf, relative],
        weights=weights,
        weight_by_confidence=weight_by_confidence,
    )

    return {
        "graham": graham,
        "dcf": dcf,
        "relative": relative,
        "composite": composite,
    }
