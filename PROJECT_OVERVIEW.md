# S&P 500 Analysis Engine — Project Overview

## Purpose

A modular, extensible Python framework for analysing S&P 500 companies. The system fetches only the data each analysis requires, caches it in SQLite to avoid redundant API calls, and provides a clean interface for plugging in new analysis strategies without touching the data layer.

Designed to be run from the terminal (e.g. Cursor's integrated terminal), with the output layer separated so a web dashboard (Streamlit, Dash, etc.) can be added later without changing any data or strategy code.

## Core Goals

- **Lazy, demand-driven data fetching** — each analysis strategy declares exactly what data fields it needs; nothing extra is pulled.
- **Pluggable strategy system** — adding a new analysis (e.g. momentum scoring, dividend screening) means writing a single new class that conforms to a base interface. No changes to data plumbing.
- **Rate-limit awareness** — yfinance is unofficial and throttle-sensitive; the data layer handles batching, delays, and caching transparently.
- **Reproducibility** — cached datasets are timestamped so you can re-run analyses against the same snapshot or force a fresh pull.
- **Dashboard-ready** — the analysis core returns plain data objects, so a web frontend can be bolted on later with zero changes to data or strategy code.

## Data Sources

| Source | What it provides | Access method |
|---|---|---|
| **Wikipedia** | S&P 500 constituent list (ticker, name, sector, sub-industry, HQ, date added, CIK, founded) | `pandas.read_html` on the Wikipedia S&P 500 list page |
| **yfinance** | Historical prices, financial statements (income statement, balance sheet, cash flow), key statistics, analyst targets, institutional holdings, dividends | `yfinance` Python library (no API key) |
| **SEC EDGAR** *(future)* | Authoritative 10-K/10-Q filings, XBRL-tagged financials | `edgartools` library (no API key) |
| **FRED** *(future)* | Macroeconomic indicators (rates, inflation, GDP, yield curves) | `fredapi` library (free API key) |

## First Analysis Target

**Undervalued stock screening via composite scoring** — identify S&P 500 companies trading below estimated intrinsic value by blending multiple valuation methods into a single normalised score.

### Component Strategies (each also usable standalone)

1. **Graham Number** — classic Benjamin Graham formula: `sqrt(22.5 × EPS × Book Value Per Share)`. If the current stock price is well below this number, the stock may be undervalued. Pure balance-sheet metric, no forecasting needed. Fast and deterministic. **Excludes financial-sector stocks** (banks, insurers, REITs) because their balance sheets work differently and give misleading results with this formula.

2. **Discounted Cash Flow (DCF)** — estimates what a company is worth today by projecting its future cash flows and discounting them back to present value. More forward-looking, but requires assumptions (see DCF Defaults below). **Excludes financial-sector stocks** for the same reason as Graham. Uses these v1 defaults:
   - **Growth rate**: 5-year historical free cash flow CAGR (compound annual growth rate), capped at 20% to avoid runaway projections
   - **Projection period**: 5 years
   - **Terminal value**: Gordon Growth Model at 2.5% perpetual growth (roughly long-run inflation)
   - **Discount rate**: 10% flat (standard conservative assumption; a future improvement could estimate WACC per company using beta + risk-free rate)

3. **Relative Valuation** — compares a stock's valuation ratios (P/E, P/B, EV/EBITDA) against its sector and industry peers. A stock trading at the 10th percentile P/E in its sector might be cheap relative to comparable companies. **Includes all sectors** including financials, because it's comparing like-for-like within each sector.

### Composite Scoring

- Each component strategy outputs a normalised 0–100 score (higher = more undervalued).
- **Graham scoring**: margin of safety as a percentage. If price is 50% below Graham Number → score 50. Capped at 100.
- **DCF scoring**: upside to estimated fair value as a percentage. If DCF fair value is 40% above current price → score 40. Capped at 100.
- **Relative scoring**: inverted percentile rank within sector. If a stock's P/E is at the 10th percentile (cheaper than 90% of peers) → score 90.
- The composite blends these with configurable weights (default: equal weighting).
- Each result carries a **confidence value** (0–1) reflecting how complete the input data was. The composite weights by confidence by default, so stocks with patchy or missing financials don't silently rank high.
- Financial-sector stocks will only have a relative valuation score (since Graham and DCF are excluded for them), so their composite confidence will naturally be lower — this is correct behaviour.

## Tech Stack

- **Language**: Python 3.10+
- **Data fetching**: `yfinance`, `pandas`, `requests`/`beautifulsoup4` (Wikipedia scraping)
- **Storage/caching**: SQLite via Python's built-in `sqlite3`
- **Analysis**: `numpy`, `scipy` for numerical work
- **Output (v1)**: Terminal tables via `rich`
- **Output (future)**: Streamlit or Dash dashboard, matplotlib/plotly charts

## Build Order

Build in this order — each step depends on the one before it:

1. ~~Data source evaluation~~ ✅
2. ~~Architecture design~~ ✅
3. **Data layer** — `DataField` enum, providers (Wikipedia + yfinance), SQLite cache, `DataManager`
4. **Individual strategies** — Graham Number, DCF, Relative Valuation
5. **Composite strategy** — blends the three individual strategy scores
6. **CLI runner** — `python cli.py undervalue --method composite --top 20`
7. **Tests** — at minimum: provider fetch tests, strategy scoring tests, cache round-trip tests
8. Future: additional strategies, web dashboard, more data sources
