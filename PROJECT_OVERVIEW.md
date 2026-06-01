# S&P 500 Analysis Engine — Project Overview

## Purpose

A modular, extensible Python framework for analysing S&P 500 companies across six independent categories. The system fetches only the data each analysis requires, caches it in SQLite, and presents results via a rich terminal interface with optional PNG chart output.

Designed to run from the terminal, with the analysis core returning plain data objects so a web dashboard can be bolted on later without touching the data or strategy code.

---

## Design Goals

- **Demand-driven data fetching** — each strategy declares exactly what data fields it needs; the data layer fetches only those fields, checking the cache first.
- **Pluggable strategies** — adding a new analysis means writing one new class. No changes to data plumbing, CLI, or existing strategies.
- **Multi-category analysis** — six independent analysis categories, each scoring 0–100 so they can be compared and combined.
- **Cross-category screening** — filter simultaneously across categories (e.g. "undervalued AND low-risk AND growing").
- **Scores for ranking, details for decisions** — every result also carries the actual financial data behind the score so users aren't flying blind.
- **Dashboard-ready** — the orchestrator returns plain data objects; a Streamlit or Dash frontend can consume them directly.

---

## Data Sources

| Source | What it provides |
|---|---|
| **Wikipedia** | S&P 500 constituent list: ticker, name, GICS sector, sub-industry, HQ, date added, CIK |
| **yfinance** | Historical prices (OHLCV), financial statements, key statistics, analyst targets, recommendations, dividends |
| **yfinance (^TNX)** | Live 10-year Treasury yield, used as the risk-free rate |
| **SEC EDGAR** *(future)* | Authoritative 10-K/10-Q filings via `edgartools` |

---

## Analysis Categories

### 1. Undervalue Screening

Identifies companies trading below estimated intrinsic value. All scores: higher = more undervalued.

| Strategy | Method | Excludes financials? |
|---|---|---|
| **Graham Number** | `sqrt(22.5 × EPS × Book Value)` vs current price | Yes |
| **DCF** | 5-year FCF projection discounted at 10%, Gordon Growth terminal value | Yes |
| **Relative Valuation** | Percentile rank on P/E, P/B, EV/EBITDA within GICS sector | No |
| **Momentum** | RSI(14), 50/200-day SMA crossover, 52-week high proximity | No |
| **Quality** | Leverage (D/E), ROE, interest coverage, revenue stability | Yes |
| **Dividend** | Yield vs peers, payout sustainability, consistency, CAGR; >8% yield penalised | No |
| **Composite** | Confidence-weighted blend of all above | Mixed |

Default composite weights (from `config.yaml`): graham=1.0, dcf=1.0, relative=1.0, quality=1.0, momentum=0.8, dividend=0.8. Weights are scaled by each strategy's confidence for that ticker so incomplete data contributes proportionally less.

Financial-sector stocks (banks, insurers, REITs) are excluded from Graham, DCF, and Quality because those models don't apply to their balance sheets. They still receive Relative, Momentum, Dividend, Sentiment, and Risk scores.

### 2. Market Sentiment

Forward-looking signals from analyst consensus. Higher score = more bullish.

| Strategy | Method |
|---|---|
| **Analyst Consensus** | Current price vs mean analyst price target (upside %) |
| **Recommendations** | Buy/hold/sell breakdown and trend direction over recent months |
| **Composite** | Confidence-weighted blend |

### 3. Risk Profiling

Measures how risky a stock is. Higher score = riskier (so `--risk-max 30` selects low-risk stocks).

| Strategy | Method |
|---|---|
| **Volatility** | Annualised historical vol, beta, max drawdown |
| **Risk-Adjusted Returns** | Inverted Sharpe/Sortino ratios (uses live risk-free rate from ^TNX) |
| **Composite** | Confidence-weighted blend |

### 4. Growth Trends

Detects accelerating or decelerating fundamentals using quarterly data. Higher score = faster improving.

| Strategy | Method |
|---|---|
| **Earnings Trend** | Quarterly EPS acceleration and YoY growth trajectory |
| **Revenue Trend** | Revenue growth rate and trend slope |
| **Margin Analysis** | Gross/operating/net margin expansion or compression |
| **Composite** | Confidence-weighted blend |

### 5. Correlation Analysis

Understands how stocks move relative to each other. Produces a matrix or pair list, not a ranked ticker list.

| Feature | What it does |
|---|---|
| **Diversification finder** | Top N least-correlated stock pairs (best for portfolio diversification) |
| **Correlated pairs** | Top N most-correlated pairs (for pairs trading or cluster analysis) |
| **Sector matrix** | Average pairwise correlation aggregated to GICS sector level |
| **Custom set** | Correlation matrix for any specified list of tickers |

Always outputs a heatmap PNG to `output/`.

### 6. Portfolio Construction

Suggests portfolio weights given a set of tickers.

| Feature | What it does |
|---|---|
| **Max-Sharpe optimisation** | SLSQP long-only optimisation maximising the Sharpe ratio |
| **Equal weight** | Simple 1/N baseline |
| **Efficient frontier** | Samples random portfolios to plot the risk/return trade-off |
| **From-screen** | Run a cross-category screen first, then optimise over the results |

Always outputs a weights chart PNG to `output/`. The live risk-free rate (10-year Treasury) is injected automatically.

---

## Cross-Category Screening

The `screen` command runs multiple category composites and returns only stocks satisfying all filters simultaneously:

```bash
python cli.py screen --undervalue-min 70 --risk-max 30 --growth-min 50 --top 20
```

Each category produces an independent 0–100 score. Filters use `--X-min` for "high score wanted" and `--X-max` for "low score wanted" (risk uses higher = riskier so `--risk-max` reads naturally).

---

## Output

| Mode | Description |
|---|---|
| **Terminal (rich)** | Colour-coded score tables, inline bar charts, sector distribution, score histogram |
| **Verbose** (`--verbose`) | Adds real-world detail columns: P/E ratios, FCF values, vol %, EPS figures, etc. |
| **Charts** (`--chart`) | PNG files saved to `output/` — score distributions, sector allocations, correlation heatmaps, portfolio weights, efficient frontiers |
| **CSV / JSON** | `--format csv/json` for notebooks and spreadsheets |

---

## What's Next

The core analysis engine is complete. Natural next areas to build on:

- **Web dashboard** — Streamlit or Dash; the orchestrator already returns clean data objects with no terminal coupling
- **SEC EDGAR integration** — more authoritative financial statement data via `edgartools`
- **Additional macro data** — inflation rate, GDP growth via FRED API (DataField enums already reserved)
- **Alerting** — scheduled runs with email/Slack notifications when scores cross thresholds
- **Backtesting** — replay historical data to evaluate strategy performance
