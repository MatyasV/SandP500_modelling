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
    return f"[{style}]{'â–ˆ' * filled}[/{style}][dim]{'â–‘' * (width - filled)}[/dim]"


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
            row.append(str(val) if val is not None else "â€”")
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
                row.append("â€”")
        if r.confidences:
            avg_conf = sum(r.confidences.values()) / len(r.confidences)
        else:
            avg_conf = 0.0
        conf_style = "green" if avg_conf >= 0.7 else "yellow" if avg_conf >= 0.4 else "red"
        row.append(f"[{conf_style}]{avg_conf:.2f}[/{conf_style}]")
        table.add_row(*row)

    return table


