"""Output formatters: table, CSV, JSON."""

import csv
import json
from io import StringIO

from rich.table import Table

from sp500.core.models import StrategyResult


def _score_style(score: float) -> str:
    """Return rich style string: red (low) -> yellow (mid) -> green (high)."""
    if score >= 70:
        return "bold green"
    elif score >= 50:
        return "green"
    elif score >= 30:
        return "yellow"
    elif score >= 15:
        return "dark_orange"
    else:
        return "red"


def _score_bar(score: float, width: int = 20) -> str:
    """Render an inline Unicode bar chart for a score 0-100."""
    filled = int(score / 100 * width)
    style = _score_style(score)
    return f"[{style}]{'█' * filled}[/{style}][dim]{'░' * (width - filled)}[/dim]"


def format_table(results: list[StrategyResult], title: str = "Screening Results") -> Table:
    """Format results as a rich Table object."""
    table = Table(title=title, show_lines=False)
    table.add_column("Rank", justify="right", style="dim", width=4)
    table.add_column("Ticker", style="cyan bold", width=8)
    table.add_column("Score", justify="right", width=8)
    table.add_column("", width=22)  # score bar
    table.add_column("Confidence", justify="right", width=10)

    for rank, r in enumerate(results, start=1):
        style = _score_style(r.score)
        confidence_style = "green" if r.confidence >= 0.7 else "yellow" if r.confidence >= 0.4 else "red"
        row = [
            str(rank),
            r.ticker,
            f"[{style}]{r.score:.1f}[/{style}]",
            _score_bar(r.score),
            f"[{confidence_style}]{r.confidence:.2f}[/{confidence_style}]",
        ]
        table.add_row(*row)

    return table


def format_detail_table(results: list[StrategyResult],
                        title: str = "Detail Breakdown") -> Table | None:
    """Format per-ticker detail columns as a separate table for verbose output."""
    if not results or not results[0].details:
        return None

    detail_keys = list(results[0].details.keys())
    table = Table(title=title, show_lines=False)
    table.add_column("Rank", justify="right", style="dim", width=4)
    table.add_column("Ticker", style="cyan bold", width=8)
    for key in detail_keys:
        table.add_column(key, justify="right", width=14)

    for rank, r in enumerate(results, start=1):
        row = [str(rank), r.ticker]
        for key in detail_keys:
            val = r.details.get(key)
            row.append(str(val) if val is not None else "—")
        table.add_row(*row)

    return table


def format_csv(results: list[StrategyResult], output_path: str | None = None) -> str:
    """Format results as CSV."""
    output = StringIO()
    writer = csv.writer(output)

    # Collect all detail keys
    all_keys: list[str] = []
    if results:
        seen: set[str] = set()
        for r in results:
            for k in r.details:
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)

    writer.writerow(["rank", "ticker", "score", "confidence"] + all_keys)
    for rank, r in enumerate(results, start=1):
        row = [rank, r.ticker, f"{r.score:.2f}", f"{r.confidence:.2f}"]
        for key in all_keys:
            row.append(r.details.get(key, ""))
        writer.writerow(row)

    csv_str = output.getvalue()

    if output_path:
        with open(output_path, "w") as f:
            f.write(csv_str)

    return csv_str


def format_json(results: list[StrategyResult]) -> str:
    """Format results as JSON."""
    data = []
    for rank, r in enumerate(results, start=1):
        data.append({
            "rank": rank,
            "ticker": r.ticker,
            "score": round(r.score, 2),
            "confidence": round(r.confidence, 2),
            "details": r.details,
        })
    return json.dumps(data, indent=2)


def format_screen_table(results: list, title: str = "Cross-Category Screen Results") -> Table:
    """Format ScreenResult list as a rich Table with one column per category."""
    if not results:
        table = Table(title=title)
        table.add_column("Info")
        table.add_row("No results")
        return table

    categories = list(results[0].scores.keys())
    table = Table(title=title, show_lines=False)
    table.add_column("Rank", justify="right", style="dim", width=4)
    table.add_column("Ticker", style="cyan bold", width=8)
    for cat in categories:
        table.add_column(cat.capitalize(), justify="right", width=12)
    table.add_column("Avg Conf", justify="right", width=10)

    for rank, r in enumerate(results, start=1):
        row = [str(rank), r.ticker]
        for cat in categories:
            score = r.scores.get(cat)
            if score is not None:
                style = _score_style(score)
                row.append(f"[{style}]{score:.1f}[/{style}]")
            else:
                row.append("—")
        if r.confidences:
            avg_conf = sum(r.confidences.values()) / len(r.confidences)
        else:
            avg_conf = 0.0
        conf_style = "green" if avg_conf >= 0.7 else "yellow" if avg_conf >= 0.4 else "red"
        row.append(f"[{conf_style}]{avg_conf:.2f}[/{conf_style}]")
        table.add_row(*row)

    return table


def format_pairs_table(pairs: list, title: str = "Correlation Pairs") -> Table:
    """Format a list of PairResult as a rich Table."""
    table = Table(title=title, show_lines=False)
    table.add_column("Rank", justify="right", style="dim", width=4)
    table.add_column("Ticker 1", style="cyan bold", width=8)
    table.add_column("Ticker 2", style="cyan bold", width=8)
    table.add_column("Correlation", justify="right", width=12)
    table.add_column("Sector 1", width=28)
    table.add_column("Sector 2", width=28)

    for rank, pair in enumerate(pairs, start=1):
        corr = pair.correlation
        if corr <= -0.3:
            style = "bold green"
        elif corr <= 0.0:
            style = "green"
        elif corr <= 0.5:
            style = "yellow"
        elif corr <= 0.7:
            style = "dark_orange"
        else:
            style = "red"
        table.add_row(
            str(rank),
            pair.ticker1,
            pair.ticker2,
            f"[{style}]{corr:+.3f}[/{style}]",
            pair.sector1 or "—",
            pair.sector2 or "—",
        )
    return table


def format_portfolio_table(allocation, title: str = "Portfolio Weights") -> Table:
    """Format an AllocationResult as a rich Table, sorted by weight descending."""
    table = Table(title=title, show_lines=False)
    table.add_column("Rank", justify="right", style="dim", width=4)
    table.add_column("Ticker", style="cyan bold", width=8)
    table.add_column("Weight", justify="right", width=10)
    table.add_column("", width=22)  # weight bar

    sorted_weights = sorted(allocation.weights.items(), key=lambda x: x[1], reverse=True)
    for rank, (ticker, weight) in enumerate(sorted_weights, start=1):
        pct = weight * 100
        filled = int(pct / 100 * 20)
        bar = f"[green]{'█' * filled}[/green][dim]{'░' * (20 - filled)}[/dim]"
        table.add_row(str(rank), ticker, f"{pct:.1f}%", bar)
    return table
