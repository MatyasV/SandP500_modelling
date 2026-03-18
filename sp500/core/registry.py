"""Strategy and provider auto-discovery registry."""

from sp500.data.providers.base import BaseProvider
from sp500.strategies.base import BaseStrategy


def discover_providers(config: dict | None = None) -> list[BaseProvider]:
    """Instantiate all available providers."""
    from sp500.data.providers.wiki import WikipediaProvider
    from sp500.data.providers.yfinance_ import YFinanceProvider
    return [WikipediaProvider(), YFinanceProvider(config)]


def discover_strategies(config: dict | None = None) -> dict[str, BaseStrategy]:
    """Instantiate all available undervalue strategies keyed by name."""
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


def discover_sentiment_strategies(config: dict | None = None) -> dict[str, BaseStrategy]:
    """Instantiate all available sentiment strategies keyed by name."""
    from sp500.strategies.sentiment.analyst import AnalystConsensusStrategy
    from sp500.strategies.sentiment.recommendations import RecommendationTrendsStrategy
    from sp500.strategies.sentiment.composite import SentimentCompositeStrategy

    analyst = AnalystConsensusStrategy(config)
    recommendations = RecommendationTrendsStrategy()

    sentiment_cfg = (config or {}).get("sentiment", {})
    weights = sentiment_cfg.get("default_weights")
    weight_by_confidence = sentiment_cfg.get("weight_by_confidence", True)

    composite = SentimentCompositeStrategy(
        strategies=[analyst, recommendations],
        weights=weights,
        weight_by_confidence=weight_by_confidence,
    )

    return {
        "analyst": analyst,
        "recommendations": recommendations,
        "composite": composite,
    }


def discover_all_strategies(config: dict | None = None) -> dict[str, dict[str, BaseStrategy]]:
    """Return all strategies grouped by category."""
    return {
        "undervalue": discover_strategies(config),
        "sentiment": discover_sentiment_strategies(config),
    }
