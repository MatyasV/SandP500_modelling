# S&P 500 Analysis Engine — Project Overview

## Purpose

A modular, extensible Python framework for analysing S&P 500 companies. The system fetches only the data each analysis requires, caches it in SQLite to avoid redundant API calls, and provides a clean interface for plugging in new analysis strategies without touching the data layer.

Designed to be run from the terminal (e.g. Cursor's integrated terminal), with the output layer separated so a web dashboard (Streamlit, Dash, etc.) can be added later without changing any data or strategy code.

## Core Goals

- **Lazy, demand-driven data fetching** — each analysis strategy declares exactly what data fields it needs; nothing extra is pulled.
- **Pluggable strategy system** — adding a new analysis means writing a single new class that conforms to a base interface. No changes to data plumbing.
- **Multi-category analysis** — not just undervalue screening; the engine supports risk profiling, sentiment analysis, growth trend detection, correlation analysis, and portfolio construction — each as an independent category with its own strategies.
- **Cross-category screening** — combine results from multiple categories (e.g. "undervalued AND low-risk") via the `screen` command.
- **Real-world context** — scores are useful for ranking, but users also see the actual financial data behind the scores (P/E ratios, FCF values, dividend yields, volatility %, etc.) so they can make informed decisions.
- **Rate-limit awareness** — yfinance is unofficial and throttle-sensitive; the data layer handles batching, delays, and caching transparently.
- **Reproducibility** — cached datasets are timestamped so you can re-run analyses against the same snapshot or force a fresh pull.
- **Dashboard-ready** — the analysis core returns plain data objects, so a web frontend can be bolted on later with zero changes to data or strategy code.

## Data Sources

| Source | What it provides | Access method |
|---|---|---|
| **Wikipedia** | S&P 500 constituent list (ticker, name, sector, sub-industry, HQ, date added, CIK, founded) | `pandas.read_html` on the Wikipedia S&P 500 list page |
| **yfinance** | Historical prices, financial statements (income statement, balance sheet, cash flow), key statistics, analyst targets, recommendations, institutional holdings, dividends | `yfinance` Python library (no API key) |
| **SEC EDGAR** *(future)* | Authoritative 10-K/10-Q filings, XBRL-tagged financials | `edgartools` library (no API key) |
| **FRED** *(future — Phase 3)* | Macroeconomic indicators (rates, inflation, GDP, yield curves) | `fredapi` library (free API key) |

## Analysis Categories

### 1. Undervalue Screening (implemented)

Identify S&P 500 companies trading below estimated intrinsic value by blending multiple valuation methods.

**Strategies:**

| Strategy | What it does | Key real-world data shown | Excludes financials? |
|---|---|---|---|
| **Graham Number** | Classic `sqrt(22.5 × EPS × Book Value)` formula | EPS, book value, Graham number, current price, margin of safety % | Yes |
| **DCF** | Projects future cash flows, discounts to present value | FCF history, growth rate used, fair value estimate, current price | Yes |
| **Relative Valuation** | Compares P/E, P/B, EV/EBITDA against sector peers | Actual ratios, sector median ratios, percentile rank | No |
| **Momentum** | RSI, SMA crossover, 52-week high proximity | RSI value, 50/200 SMA values, current vs 52-week high | No |
| **Quality** | Leverage, interest coverage, ROE, revenue stability | D/E ratio, ROE %, interest coverage ratio, revenue CV | Yes |
| **Dividend** | Yield, payout sustainability, consistency, growth | Dividend yield %, payout ratio, years of history, CAGR | No |
| **Composite** | Weighted blend of all above | Sub-scores from each strategy | Mixed |

**Composite weights** (from config.yaml): graham=1.0, dcf=1.0, relative=1.0, momentum=0.8, quality=1.0, dividend=0.8. Weights are relative, not summing to 1. Momentum and dividend are weighted lower because momentum is not a value signal and not all stocks pay dividends. Composite optionally scales each sub-strategy's weight by its confidence for that ticker (`weight_by_confidence: true`).

**Confidence system:** Each strategy result carries a confidence value (0–1) reflecting data completeness:

| Strategy | Confidence = 1.0 when | Lower when |
|---|---|---|
| Graham | Always 1.0 (or no result) | N/A — returns None if data missing |
| DCF | 5+ years cash flow data | 3-4 yrs → 0.6, <3 yrs → 0.3 |
| Relative | All 3 ratios + sector ≥5 stocks | Fewer ratios → lower; small sector → 0.8× penalty |
| Momentum | 252+ trading days | 126-251 → 0.6, <126 → 0.3 |
| Quality | 4+ years financials + all metrics | Fewer years or metrics → lower |
| Dividend | 10+ years dividend history | 5-9 yrs → 0.7, 2-4 → 0.4, <2 → 0.2 |

Financial-sector stocks only get scores from relative, momentum, and dividend (since Graham, DCF, and quality exclude them), so their composite confidence is naturally lower — this is correct behaviour.

### 2. Market Sentiment (planned — Phase 1)

Forward-looking signals from analyst consensus and institutional activity. Kept **separate from undervalue scoring** because these are opinions, not fundamental measurements — useful context, but fundamentally different from data grounded in actual financials. Users can see convergence: "Stock X scores 82 on undervalue AND analysts have a 30% upside target."

**Strategies:**

| Strategy | What it does | Key real-world data shown |
|---|---|---|
| **Analyst Consensus** | Compares current price to analyst price targets | Current price, mean/median/high/low targets, % upside, number of analysts |
| **Recommendation Trends** | Tracks buy/hold/sell rating changes over time | Current breakdown, 3-month trend direction, upgrade/downgrade count |

**Graphical output:**
- Target price range chart (low—median—high vs current price)
- Recommendation trend sparklines (buy/hold/sell over time)

### 3. Risk Profiling (planned — Phase 2)

Measure and rank stocks by various risk dimensions.

**Strategies:**

| Strategy | What it does | Key real-world data shown |
|---|---|---|
| **Volatility** | Historical standard deviation, beta, max drawdown | Annualised vol %, beta value, max drawdown %, drawdown period |
| **Risk-adjusted Returns** | Sharpe ratio, Sortino ratio | Annualised return %, Sharpe ratio, Sortino ratio, downside deviation |

**Scoring convention:** 0–100, **higher = riskier**. This means `--risk-max 30` in the screen command selects low-risk stocks.

**Graphical output:**
- Volatility distribution histogram across S&P 500
- Drawdown chart for individual stocks (verbose mode)
- Risk-return scatter plot (return vs volatility, with selected stocks highlighted)

### 4. Growth Trends (planned — Phase 2)

Detect companies with accelerating or decelerating fundamentals using quarterly data.

**Strategies:**

| Strategy | What it does | Key real-world data shown |
|---|---|---|
| **Earnings Trend** | Quarterly EPS acceleration/deceleration | Last 4-8 quarters of EPS, QoQ and YoY growth rates, acceleration direction |
| **Revenue Trend** | Revenue growth trajectory | Quarterly revenue figures, growth rates, trend line slope |
| **Margin Analysis** | Gross/operating/net margin expansion or compression | Margin % per quarter, expansion/compression direction, magnitude |

**Graphical output:**
- Quarterly trend sparklines for key metrics
- Sector-level growth comparison bars

### 5. Correlation Analysis (planned — Phase 3)

Understand how stocks move relative to each other. This produces **pair/matrix output**, not a ranked ticker list — a different output shape from other categories.

**Capabilities:**

| Feature | What it does | Key real-world data shown |
|---|---|---|
| **Pair correlation** | Correlation between two specific tickers | Correlation coefficient, rolling correlation chart, shared sector info |
| **Sector correlation matrix** | Intra/inter-sector average correlations | Heatmap of sector-to-sector correlations |
| **Diversification finder** | Identify lowly-correlated stock pairs | Top N least-correlated pairs with correlation values |

**Graphical output:**
- Correlation heatmaps (sector-level and stock-level)
- Rolling correlation line charts for pairs
- Dual-axis price overlay for compared stocks

### 6. Portfolio Construction (planned — Phase 3)

Takes results from other analysis categories and suggests portfolio weightings.

**Capabilities:**

| Feature | What it does | Key real-world data shown |
|---|---|---|
| **Mean-variance optimisation** | Efficient frontier allocation | Suggested weights, expected return, expected volatility, Sharpe ratio |
| **Diversification scoring** | How well-diversified is a given portfolio? | Sector concentration %, top-holding concentration, effective N |
| **Risk budget allocation** | Weight by equal risk contribution | Per-stock risk contribution %, suggested rebalance |

**Graphical output:**
- Efficient frontier curve with selected portfolio marked
- Sector allocation pie/donut chart
- Weight comparison bar chart (current vs optimised)

## Cross-Category Screening

The `screen` command combines scores from multiple categories to find stocks matching multi-factor criteria:

```bash
python cli.py screen --undervalue-min 70 --risk-max 30 --growth-min 50 --top 20
```

This runs undervalue, risk, and growth analyses, then returns only stocks that satisfy ALL filters. Each category produces its standardised 0–100 score, making cross-category filtering straightforward.

**Real-world data in screen output:** The screen results table shows the composite filter results plus key real-world metrics from each category (e.g. P/E, FCF yield, volatility %, EPS growth rate) so the user isn't just looking at abstract scores.

## Output Modes

### Terminal (rich) — implemented
- Color-coded score tables with inline Unicode bar charts
- Sector distribution charts
- Score histograms
- Strategy-specific detail columns in verbose mode

### Graphical (matplotlib — planned)
- Saved to `output/` directory as PNG files
- Inline terminal display where supported (iTerm2, Kitty)
- Charts are analysis-specific (see each category above)

### Data export — implemented
- CSV and JSON for further analysis in notebooks or spreadsheets

## Tech Stack

- **Language**: Python 3.10+
- **Data fetching**: `yfinance`, `pandas`, `beautifulsoup4` (Wikipedia scraping)
- **Storage/caching**: SQLite via Python's built-in `sqlite3`
- **Analysis**: `numpy`, `scipy` for numerical work
- **Terminal output**: `rich` (tables, panels, progress bars)
- **Graphical output** *(planned)*: `matplotlib` for charts and plots
- **Configuration**: `pyyaml`
- **Output (future)**: Streamlit or Dash dashboard

## Build Roadmap

| Phase | What | Status |
|---|---|---|
| ✅ Done | Data layer (providers, cache, DataManager) | Complete |
| ✅ Done | Undervalue strategies (Graham, DCF, Relative, Momentum, Quality, Dividend, Composite) | Complete |
| ✅ Done | CLI runner + rich terminal output | Complete |
| ✅ Done | Unit tests (cache, providers, strategies, output) | Complete |
| Phase 1 | Sentiment analysis (analyst consensus, recommendation trends) | Planned |
| Phase 1 | Multi-category CLI structure (subcommands per category) | Planned |
| Phase 2 | Risk profiling (volatility, risk-adjusted returns) | Planned |
| Phase 2 | Growth trend analysis (earnings, revenue, margins) | Planned |
| Phase 2 | `screen` command (cross-category filtering) | Planned |
| Phase 3 | Correlation analysis (pairs, matrices, diversification finder) | Planned |
| Phase 3 | Portfolio construction (optimisation, risk budgeting) | Planned |
| Phase 3 | FRED macro data integration | Planned |
| Phase 3 | Graphical output (matplotlib charts) | Planned |
