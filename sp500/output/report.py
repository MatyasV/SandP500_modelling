"""Rich terminal report generation."""

from collections import Counter
from datetime import datetime

from rich.console import Console
from rich.panel import Panel

from sp500.core.models import StrategyResult
from sp500.output.formatters import format_table


def _print_sector_distribution(results: list[StrategyResult],
                               sector_map: dict[str, str],
                               console: Console) -> None:
    """Show a horizontal bar chart of sector representation in results."""
    sectors = [sector_map.get(r.ticker, "Unknown") for r in results]
    counts = Counter(sectors)
    max_count = max(counts.values())

    lines = []
    for sector, count in sorted(counts.items(), key=lambda x: -x[1]):
        bar_width = int(count / max_count * 25)
        lines.append(f"  {sector:30s} {'█' * bar_width} {count}")

    panel = Panel("\n".join(lines), title="Sector Distribution",
                  border_style="dim", expand=False)
    console.print(panel)


def _print_score_histogram(results: list[StrategyResult],
                           console: Console) -> None:
    """Show a horizontal histogram of score distribution across bins."""
    bins = [0] * 10
    for r in results:
        idx = min(int(r.score // 10), 9)
        bins[idx] += 1
    max_count = max(bins) if max(bins) > 0 else 1

    lines = []
    for i in range(9, -1, -1):
        label = f"{i * 10:>3d}-{i * 10 + 10:<3d}"
        bar_width = int(bins[i] / max_count * 30)
        count_str = str(bins[i]) if bins[i] else ""
        lines.append(f"  {label} │{'█' * bar_width} {count_str}")

    panel = Panel("\n".join(lines), title="Score Distribution",
                  border_style="dim", expand=False)
    console.print(panel)


def print_report(results: list[StrategyResult], strategy_name: str,
                 verbose: bool = False,
                 sector_map: dict[str, str] | None = None) -> None:
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

    # Sector distribution
    if sector_map:
        console.print()
        _print_sector_distribution(results, sector_map, console)

    # Score histogram (only useful with enough data points)
    if len(results) > 5:
        console.print()
        _print_score_histogram(results, console)

    # Summary
    console.print()
    scores = [r.score for r in results]
    avg_conf = sum(r.confidence for r in results) / len(results)
    console.print(f"[dim]Showing {len(results)} stocks | "
                  f"Score range: {min(scores):.1f} – {max(scores):.1f} | "
                  f"Avg confidence: {avg_conf:.2f}[/dim]")
    console.print()
