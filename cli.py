"""CLI entry point for S&P 500 Analysis Engine."""

import argparse
import logging
import os

import yaml


def load_config(path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def _output_results(args, results, strategy_name, orchestrator=None,
                    category="Undervalue"):
    """Shared output logic for all category commands."""
    if args.output_format == "csv":
        from sp500.output.formatters import format_csv
        output = format_csv(results, args.output)
        if not args.output:
            print(output)
    elif args.output_format == "json":
        from sp500.output.formatters import format_json
        output = format_json(results)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
        else:
            print(output)
    else:
        from sp500.output.report import print_report
        sector_map = None
        if orchestrator and hasattr(orchestrator, 'constituents') and orchestrator.constituents is not None:
            sector_map = dict(zip(orchestrator.constituents["Symbol"],
                                  orchestrator.constituents["GICS Sector"]))
        print_report(results, strategy_name, verbose=args.verbose,
                     sector_map=sector_map, category=category)


def _setup_data_manager(args, config):
    """Create DataManager with cache and providers."""
    from sp500.core.registry import discover_providers
    from sp500.data.cache import SQLiteCache
    from sp500.data.manager import DataManager

    db_path = config["cache"]["db_path"]
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    ttl = 0 if args.no_cache else config["cache"]["ttl_hours"]
    cache = SQLiteCache(db_path, ttl)
    providers = discover_providers(config)
    return DataManager(providers, cache, config)


def cmd_undervalue(args, config):
    """Run undervalue screening."""
    from sp500.core.orchestrator import Orchestrator
    from sp500.core.registry import discover_strategies

    data_manager = _setup_data_manager(args, config)
    strategies = discover_strategies(config)

    # Handle custom weights for composite
    if args.weights and args.method == "composite":
        from sp500.strategies.undervalue.composite import CompositeStrategy
        weights = {}
        for pair in args.weights.split(","):
            name, val = pair.split("=")
            weights[name.strip()] = float(val)
        sub = [strategies["graham"], strategies["dcf"], strategies["relative"]]
        strategies["composite"] = CompositeStrategy(sub, weights)

    strategy = strategies[args.method]
    orchestrator = Orchestrator(data_manager)
    results = orchestrator.run(strategy, args.top)

    _output_results(args, results, strategy.name, orchestrator,
                    category="Undervalue")


def cmd_sentiment(args, config):
    """Run sentiment screening."""
    from sp500.core.orchestrator import Orchestrator
    from sp500.core.registry import discover_sentiment_strategies

    data_manager = _setup_data_manager(args, config)
    strategies = discover_sentiment_strategies(config)

    strategy = strategies[args.method]
    orchestrator = Orchestrator(data_manager)
    results = orchestrator.run(strategy, args.top)

    _output_results(args, results, strategy.name, orchestrator,
                    category="Sentiment")


def cmd_cache(args, config):
    """Cache management commands."""
    from sp500.data.cache import SQLiteCache

    db_path = config["cache"]["db_path"]
    if not os.path.exists(db_path):
        print("No cache database found.")
        return

    cache = SQLiteCache(db_path, config["cache"]["ttl_hours"])

    if args.status:
        size = os.path.getsize(db_path)
        count = cache.conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        oldest, newest = cache.conn.execute(
            "SELECT MIN(fetched_at), MAX(fetched_at) FROM cache"
        ).fetchone()
        print(f"Cache DB: {db_path}")
        print(f"Size: {size / 1024:.1f} KB")
        print(f"Entries: {count}")
        print(f"Oldest: {oldest or 'N/A'}")
        print(f"Newest: {newest or 'N/A'}")
    elif args.clear:
        if args.older_than:
            from datetime import datetime, timedelta
            hours = int(args.older_than.rstrip("h"))
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            deleted = cache.invalidate(older_than=cutoff)
        else:
            deleted = cache.invalidate()
        print(f"Cleared {deleted} cache entries.")


def main():
    parser = argparse.ArgumentParser(description="S&P 500 Analysis Engine")
    parser.add_argument("--list-strategies", action="store_true",
                        help="List available strategies")
    parser.add_argument("-v", "--verbose-log", action="store_true",
                        help="Enable verbose logging")
    subparsers = parser.add_subparsers(dest="command")

    # undervalue subcommand
    uv = subparsers.add_parser("undervalue", help="Run undervalue screening")
    uv.add_argument("--method", default="composite",
                    choices=["graham", "dcf", "relative", "momentum",
                             "quality", "dividend", "composite"])
    uv.add_argument("--top", type=int, default=20)
    uv.add_argument("--weights", type=str, default=None,
                    help="Comma-separated weights, e.g. graham=2,dcf=1,relative=1")
    uv.add_argument("--format", dest="output_format", default="table",
                    choices=["table", "csv", "json"])
    uv.add_argument("--output", type=str, default=None)
    uv.add_argument("--no-cache", action="store_true")
    uv.add_argument("--verbose", action="store_true")

    # sentiment subcommand
    sent = subparsers.add_parser("sentiment", help="Run sentiment screening")
    sent.add_argument("--method", default="composite",
                      choices=["analyst", "recommendations", "composite"])
    sent.add_argument("--top", type=int, default=20)
    sent.add_argument("--format", dest="output_format", default="table",
                      choices=["table", "csv", "json"])
    sent.add_argument("--output", type=str, default=None)
    sent.add_argument("--no-cache", action="store_true")
    sent.add_argument("--verbose", action="store_true")

    # cache subcommand
    cache_p = subparsers.add_parser("cache", help="Cache management")
    cache_p.add_argument("--status", action="store_true")
    cache_p.add_argument("--clear", action="store_true")
    cache_p.add_argument("--older-than", type=str, default=None)

    args = parser.parse_args()
    config = load_config()

    # Set up logging
    level = logging.INFO if args.verbose_log else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")

    if args.list_strategies:
        from sp500.core.registry import discover_all_strategies
        all_strats = discover_all_strategies(config)
        for category, strategies in all_strats.items():
            print(f"\n{category}:")
            for name, s in strategies.items():
                print(f"  {name:20s}  {s.description}")
        return

    if args.command == "undervalue":
        cmd_undervalue(args, config)
    elif args.command == "sentiment":
        cmd_sentiment(args, config)
    elif args.command == "cache":
        cmd_cache(args, config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
