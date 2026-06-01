"""Matplotlib chart generation — all functions save to output/ directory and return the file path."""

import logging
import os
from collections import Counter
from datetime import datetime
from typing import Any

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — saves to file, no display
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)

_OUTPUT_DIR = "output"


def _save(fig: Any, name: str) -> str:
    """Save figure to output/ directory with timestamp suffix. Returns file path."""
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
    path = os.path.join(_OUTPUT_DIR, f"{name}_{ts}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Chart saved: %s", path)
    return path


def plot_score_distribution(results: list, category: str = "") -> str:
    """
    Histogram of scores across all results, binned into 10-point buckets (0–10, 10–20, ...).
    Color-coded: green for high scores, red for low scores.
    """
    if not results:
        logger.warning("No results to plot score distribution")
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No results", ha="center", va="center", transform=ax.transAxes)
        return _save(fig, "score_dist_empty")

    scores = [r.score for r in results]
    fig, ax = plt.subplots(figsize=(8, 4))
    bins = list(range(0, 105, 10))

    # Color buckets by score range
    n, _, patches = ax.hist(scores, bins=bins, edgecolor="white", linewidth=0.5)
    for patch, left_edge in zip(patches, bins[:-1]):
        mid = left_edge + 5
        if mid >= 70:
            patch.set_facecolor("#2ca02c")   # green
        elif mid >= 50:
            patch.set_facecolor("#98df8a")   # light green
        elif mid >= 30:
            patch.set_facecolor("#ffbb78")   # yellow/orange
        elif mid >= 15:
            patch.set_facecolor("#ff7f0e")   # orange
        else:
            patch.set_facecolor("#d62728")   # red

    ax.set_xlabel("Score", fontsize=12)
    ax.set_ylabel("Number of Stocks", fontsize=12)
    title = f"{category} Score Distribution" if category else "Score Distribution"
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlim(0, 100)
    ax.set_xticks(range(0, 101, 10))

    # Add mean/median lines
    ax.axvline(np.mean(scores), color="navy", linestyle="--", linewidth=1.5,
               label=f"Mean: {np.mean(scores):.1f}")
    ax.axvline(np.median(scores), color="darkred", linestyle=":", linewidth=1.5,
               label=f"Median: {np.median(scores):.1f}")
    ax.legend(fontsize=9)

    plt.tight_layout()
    name = f"{category.lower().replace(' ', '_')}_score_dist" if category else "score_dist"
    return _save(fig, name)


def plot_sector_allocation(results: list, sector_map: dict, category: str = "") -> str:
    """
    Horizontal bar chart showing sector distribution of results.
    Sorted by count descending.
    """
    if not results:
        logger.warning("No results to plot sector allocation")
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No results", ha="center", va="center", transform=ax.transAxes)
        return _save(fig, "sectors_empty")

    sectors = [sector_map.get(r.ticker, "Unknown") for r in results]
    counts = Counter(sectors)
    labels, values = zip(*sorted(counts.items(), key=lambda x: x[1]))

    fig, ax = plt.subplots(figsize=(10, max(4, len(labels) * 0.45)))
    colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
    bars = ax.barh(labels, values, color=colors, edgecolor="white")

    # Add value labels at end of bars
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", fontsize=10)

    ax.set_xlabel("Number of Stocks", fontsize=11)
    title = f"{category} — Sector Breakdown" if category else "Sector Breakdown"
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlim(0, max(values) * 1.15)
    plt.tight_layout()
    name = f"{category.lower().replace(' ', '_')}_sectors" if category else "sectors"
    return _save(fig, name)


def plot_correlation_heatmap(corr_result: Any) -> str:
    """
    Color-coded N×N correlation heatmap.
    - Red = negative correlation (good for diversification)
    - Green = positive correlation
    - Annotates values for matrices up to 30×30
    """
    matrix = corr_result.matrix
    if matrix is None or (hasattr(matrix, "empty") and matrix.empty):
        logger.warning("Empty correlation matrix — cannot plot heatmap")
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.text(0.5, 0.5, "No correlation data", ha="center", va="center",
                transform=ax.transAxes)
        return _save(fig, "correlation_heatmap_empty")

    import pandas as pd
    n = len(matrix)
    fig_size = (max(8, n * 0.55), max(6, n * 0.45))
    fig, ax = plt.subplots(figsize=fig_size)

    im = ax.imshow(matrix.values.astype(float), cmap="RdYlGn", vmin=-1, vmax=1, aspect="auto")
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Pearson Correlation", fontsize=10)

    tick_labels = list(matrix.columns)
    fontsize = max(4, min(9, 200 // n))
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(tick_labels, rotation=90, fontsize=fontsize)
    ax.set_yticklabels(tick_labels, fontsize=fontsize)
    ax.set_title("Return Correlation Matrix", fontsize=13, fontweight="bold", pad=12)

    # Annotate cells for small matrices only
    if n <= 25:
        for i in range(n):
            for j in range(n):
                val = float(matrix.iloc[i, j])
                if not pd.isna(val):
                    color = "black" if abs(val) < 0.6 else "white"
                    ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                            fontsize=max(5, 7 - n // 8), color=color)

    plt.tight_layout()
    return _save(fig, "correlation_heatmap")


def plot_portfolio_weights(allocation: Any) -> str:
    """
    Horizontal bar chart of portfolio weights (%), sorted descending.
    Shows only weights > 0.5%, or top 20 if all are small.
    """
    if allocation is None or not allocation.weights:
        logger.warning("Empty allocation — cannot plot weights")
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No allocation data", ha="center", va="center",
                transform=ax.transAxes)
        return _save(fig, "portfolio_weights_empty")

    items = sorted(allocation.weights.items(), key=lambda x: x[1], reverse=True)
    # Filter to meaningful weights
    meaningful = [(t, w) for t, w in items if w > 0.005]
    if not meaningful:
        meaningful = items[:20]  # fallback: show top 20

    labels, values = zip(*meaningful)
    pct_values = [v * 100 for v in values]

    fig, ax = plt.subplots(figsize=(9, max(4, len(labels) * 0.38)))
    colors = ["#2ca02c" if v > 5 else "#98df8a" if v > 2 else "#c7e9c0"
              for v in pct_values]
    bars = ax.barh(labels, pct_values, color=colors, edgecolor="white")

    for bar, val in zip(bars, pct_values):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", fontsize=9)

    ax.set_xlabel("Portfolio Weight (%)", fontsize=11)
    method_label = allocation.method.replace("_", " ").title()
    ax.set_title(f"Portfolio Weights — {method_label}", fontsize=13, fontweight="bold")
    ax.set_xlim(0, max(pct_values) * 1.18)

    # Add stats annotation
    stats_text = (f"Expected Return: {allocation.expected_return*100:.1f}%\n"
                  f"Volatility: {allocation.expected_volatility*100:.1f}%\n"
                  f"Sharpe: {allocation.sharpe_ratio:.2f}")
    ax.text(0.98, 0.02, stats_text, transform=ax.transAxes, fontsize=9,
            va="bottom", ha="right",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8))

    plt.tight_layout()
    return _save(fig, "portfolio_weights")


def plot_efficient_frontier(frontier_points: list[dict],
                            optimal_point: dict | None = None) -> str:
    """
    Scatter plot of random portfolios (vol vs return), color-coded by Sharpe ratio.
    Highlights the optimal (max Sharpe) point in red.

    frontier_points: list of {"vol": float, "return": float, "sharpe": float}
    optimal_point: {"vol": float, "return": float, "sharpe": float}
    """
    if not frontier_points:
        logger.warning("No frontier points to plot")
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "No frontier data", ha="center", va="center",
                transform=ax.transAxes)
        return _save(fig, "efficient_frontier_empty")

    vols = [p["vol"] * 100 for p in frontier_points]
    rets = [p["return"] * 100 for p in frontier_points]
    sharpes = [p["sharpe"] for p in frontier_points]

    fig, ax = plt.subplots(figsize=(9, 6))
    sc = ax.scatter(vols, rets, c=sharpes, cmap="viridis", s=15, alpha=0.5, zorder=2)
    cbar = plt.colorbar(sc, ax=ax, shrink=0.8)
    cbar.set_label("Sharpe Ratio", fontsize=10)

    if optimal_point:
        ax.scatter([optimal_point["vol"] * 100], [optimal_point["return"] * 100],
                   color="red", s=200, zorder=5, marker="*",
                   label=f"Max Sharpe ({optimal_point['sharpe']:.2f})")
        ax.legend(fontsize=10)

    ax.set_xlabel("Annualised Volatility (%)", fontsize=11)
    ax.set_ylabel("Annualised Expected Return (%)", fontsize=11)
    ax.set_title("Efficient Frontier", fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    return _save(fig, "efficient_frontier")
