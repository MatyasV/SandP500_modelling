"""CLI entry point for S&P 500 Analysis Engine."""

import argparse

import yaml


def load_config(path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def cmd_undervalue(args, config):
    """Run undervalue screening."""
    # TODO: Wire up orchestrator, strategy selection, output formatting
    raise NotImplementedError


def cmd_cache(args, config):
    """Cache management commands."""
    # TODO: Implement cache status, clear, clear-older-than
    raise NotImplementedError


def main():
    parser = argparse.ArgumentParser(description="S&P 500 Analysis Engine")
    parser.add_argument("--list-strategies", action="store_true",
                        help="List available strategies")
    subparsers = parser.add_subparsers(dest="command")

    # undervalue subcommand
    uv = subparsers.add_parser("undervalue", help="Run undervalue screening")
    uv.add_argument("--method", default="composite",
                    choices=["graham", "dcf", "relative", "composite"])
    uv.add_argument("--top", type=int, default=20)
    uv.add_argument("--weights", type=str, default=None,
                    help="Comma-separated weights, e.g. graham=2,dcf=1,relative=1")
    uv.add_argument("--format", dest="output_format", default="table",
                    choices=["table", "csv", "json"])
    uv.add_argument("--output", type=str, default=None)
    uv.add_argument("--no-cache", action="store_true")
    uv.add_argument("--verbose", action="store_true")

    # cache subcommand
    cache_p = subparsers.add_parser("cache", help="Cache management")
    cache_p.add_argument("--status", action="store_true")
    cache_p.add_argument("--clear", action="store_true")
    cache_p.add_argument("--older-than", type=str, default=None)

    args = parser.parse_args()
    config = load_config()

    if args.list_strategies:
        # TODO: List all discovered strategies
        print("TODO: list strategies")
        return

    if args.command == "undervalue":
        cmd_undervalue(args, config)
    elif args.command == "cache":
        cmd_cache(args, config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
