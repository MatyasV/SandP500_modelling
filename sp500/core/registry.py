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
    from sp500.strategies.undervalue.momentum import MomentumStrategy
    from sp500.strategies.undervalue.quality import QualityStrategy
    from sp500.strategies.undervalue.dividend import DividendQualityStrategy
    from sp500.strategies.undervalue.composite import CompositeStrategy

    graham = GrahamStrategy()
    dcf = DCFStrategy(config)
    relative = RelativeStrategy()
    momentum = MomentumStrategy(config)
    quality = QualityStrategy()
    dividend = DividendQualityStrategy(config)

    composite_cfg = (config or {}).get("composite", {})
    weights = composite_cfg.get("default_weights")
    weight_by_confidence = composite_cfg.get("weight_by_confidence", True)

    composite = CompositeStrategy(
        strategies=[graham, dcf, relative, momentum, quality, dividend],
        weights=weights,
        weight_by_confidence=weight_by_confidence,
    )

    return {
        "graham": graham,
        "dcf": dcf,
        "relative": relative,
        "momentum": momentum,
        "quality": quality,
        "dividend": dividend,
        "composite": composite,
    }
