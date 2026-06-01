"""Strategy and provider auto-discovery registry."""

from sp500.data.providers.base import BaseProvider
from sp500.strategies.base import BaseStrategy


def discover_providers(config: dict | None = None) -> list[BaseProvider]:
    """Instantiate all available providers."""
    from sp500.data.providers.wiki import WikipediaProvider
    from sp500.data.providers.yfinance_ import YFinanceProvider
    from sp500.data.providers.fred import FREDProvider
    return [WikipediaProvider(), YFinanceProvider(config), FREDProvider(config)]


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


def discover_risk_strategies(config: dict | None = None) -> dict[str, BaseStrategy]:
    """Instantiate all available risk profiling strategies keyed by name."""
    from sp500.strategies.risk.volatility import VolatilityStrategy
    from sp500.strategies.risk.risk_adjusted import RiskAdjustedReturnsStrategy
    from sp500.strategies.risk.composite import RiskCompositeStrategy

    volatility = VolatilityStrategy(config)
    risk_adjusted = RiskAdjustedReturnsStrategy(config)

    risk_cfg = (config or {}).get("risk", {})
    weights = risk_cfg.get("default_weights")
    weight_by_confidence = risk_cfg.get("weight_by_confidence", True)

    composite = RiskCompositeStrategy(
        strategies=[volatility, risk_adjusted],
        weights=weights,
        weight_by_confidence=weight_by_confidence,
    )

    return {
        "volatility": volatility,
        "risk_adjusted": risk_adjusted,
        "composite": composite,
    }


def discover_growth_strategies(config: dict | None = None) -> dict[str, BaseStrategy]:
    """Instantiate all available growth trend strategies keyed by name."""
    from sp500.strategies.growth.earnings import EarningsTrendStrategy
    from sp500.strategies.growth.revenue import RevenueTrendStrategy
    from sp500.strategies.growth.margins import MarginAnalysisStrategy
    from sp500.strategies.growth.composite import GrowthCompositeStrategy

    earnings = EarningsTrendStrategy()
    revenue = RevenueTrendStrategy()
    margins = MarginAnalysisStrategy()

    growth_cfg = (config or {}).get("growth", {})
    weights = growth_cfg.get("default_weights")
    weight_by_confidence = growth_cfg.get("weight_by_confidence", True)

    composite = GrowthCompositeStrategy(
        strategies=[earnings, revenue, margins],
        weights=weights,
        weight_by_confidence=weight_by_confidence,
    )

    return {
        "earnings": earnings,
        "revenue": revenue,
        "margins": margins,
        "composite": composite,
    }


def discover_all_strategies(config: dict | None = None) -> dict[str, dict[str, BaseStrategy]]:
    """Return all strategies grouped by category."""
    return {
        "undervalue": discover_strategies(config),
        "sentiment": discover_sentiment_strategies(config),
        "risk": discover_risk_strategies(config),
        "growth": discover_growth_strategies(config),
    }
