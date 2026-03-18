"""Rich terminal report generation."""

from datetime import datetime

from rich.console import Console

from sp500.core.models import StrategyResult
from sp500.output.formatters import format_table


def print_report(results: list[StrategyResult], strategy_name: str,
                 verbose: bool = False) -> None:
    """Print a formatted report to the terminal using rich."""
    console = Console()

    console.print()
    console.print(f"[bold]S&P 500 Undervalue Screen — {strategy_name.upper()}[/bold]")
    console.print(f"[dim]{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}[/dim]")
    console.print()

    if not results:
        console.print("[yellow]No results to display.[/yellow]")
        return

    table = format_table(results, verbose=verbose)
    console.print(table)

    # Summary
    console.print()
    scores = [r.score for r in results]
    avg_conf = sum(r.confidence for r in results) / len(results)
    console.print(f"[dim]Showing {len(results)} stocks | "
                  f"Score range: {min(scores):.1f} – {max(scores):.1f} | "
                  f"Avg confidence: {avg_conf:.2f}[/dim]")
    console.print()
