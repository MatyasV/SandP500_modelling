"""Output formatters: table, CSV, JSON."""

import csv
import json
from io import StringIO

from rich.table import Table

from sp500.core.models import StrategyResult


def format_table(results: list[StrategyResult], verbose: bool = False) -> Table:
    """Format results as a rich Table object."""
    table = Table(title="Undervalue Screening Results", show_lines=False)
    table.add_column("Rank", justify="right", style="dim", width=4)
    table.add_column("Ticker", style="cyan bold", width=8)
    table.add_column("Score", justify="right", style="green", width=8)
    table.add_column("Confidence", justify="right", width=10)

    if verbose and results:
        # Add columns for each detail key from the first result
        detail_keys = list(results[0].details.keys())
        for key in detail_keys:
            table.add_column(key, justify="right", width=14)

    for rank, r in enumerate(results, start=1):
        confidence_style = "green" if r.confidence >= 0.7 else "yellow" if r.confidence >= 0.4 else "red"
        row = [
            str(rank),
            r.ticker,
            f"{r.score:.1f}",
            f"[{confidence_style}]{r.confidence:.2f}[/{confidence_style}]",
        ]
        if verbose:
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
