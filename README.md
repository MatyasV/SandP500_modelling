# S&P 500 Analysis Engine

A modular Python framework for screening S&P 500 companies. Fetches only the data each analysis needs, caches it in SQLite, and blends six independent valuation/quality strategies into a single composite score.

## Quick Start

```bash
pip install -r requirements.txt

# Composite screen (all 6 strategies blended) — top 20
python cli.py undervalue --top 20

# Single strategy
python cli.py undervalue --method graham --top 10
python cli.py undervalue --method momentum --top 15

# Custom composite weights
python cli.py undervalue --weights "graham=2,dcf=1,relative=1,momentum=0.5,quality=1,dividend=0.5"

# Verbose output (shows per-strategy detail columns)
python cli.py undervalue --top 10 --verbose

# Export
python cli.py undervalue --format csv --output results.csv
python cli.py undervalue --format json --output results.json

# Cache management
python cli.py cache --status
python cli.py cache --clear
python cli.py cache --clear --older-than 48h

# List all available strategies
python cli.py --list-strategies
```

## Strategies

Six strategies, each producing a normalised 0-100 score (higher = more undervalued or higher quality):

### Value Strategies

1. **Graham Number** — classic Benjamin Graham formula: `sqrt(22.5 x EPS x Book Value)`. If the stock price is well below this number, it may be undervalued. Pure balance-sheet metric, fast and deterministic. Excludes financial-sector stocks.

2. **DCF (Discounted Cash Flow)** — projects future free cash flows using historical CAGR, discounts them to present value via Gordon Growth Model. More forward-looking but requires assumptions (5-year projection, 10% discount rate, 2.5% terminal growth, growth capped at 20%). Excludes financial-sector stocks.

3. **Relative Valuation** — compares P/E, P/B, and EV/EBITDA ratios against sector peers. A stock at the 10th percentile P/E in its sector scores 90. Includes all sectors (like-for-like comparison).

### Momentum & Quality Strategies

4. **Momentum** — combines RSI(14), 50/200-day moving average crossover, and proximity to 52-week high. Each signal is percentile-ranked across the full universe, then blended. All sectors included.

5. **Quality/Safety** — scores on leverage (debt-to-equity), interest coverage, ROE, and revenue stability. Equal-weighted blend of the four metrics. Excludes financial-sector stocks.

6. **Dividend Quality** — evaluates yield attractiveness vs sector peers, payout sustainability, dividend consistency, and dividend growth rate. Penalises yields above 8% as potential yield traps. Excludes non-dividend-paying stocks.

## Composite Scoring

The composite strategy blends all six sub-strategies using configurable **relative weights** (they don't need to sum to 1). The final score is:

```
score = sum(strategy_score * effective_weight) / sum(effective_weight)
```

Default weights from `config.yaml`:

| Strategy | Default Weight | Rationale |
|---|---|---|
| Graham | 1.0 | Core value signal |
| DCF | 1.0 | Core value signal |
| Relative | 1.0 | Core value signal |
| Momentum | 0.8 | Not a pure value signal |
| Quality | 1.0 | Directly value-relevant |
| Dividend | 0.8 | Not all stocks pay dividends |

When `weight_by_confidence: true` (the default), each strategy's weight is scaled by its confidence: `effective_weight = base_weight * confidence`. This means strategies with incomplete data automatically contribute less.

## Confidence System

Each strategy assigns a confidence value (0-1) based on how complete its input data was. The composite confidence is the simple average of all contributing sub-strategy confidences.

| Strategy | Confidence = 1.0 when | Lower when |
|---|---|---|
| **Graham** | Always 1.0 (or no result at all) | N/A |
| **DCF** | 5+ years of cash flow data | 3-4 yrs → 0.6, <3 yrs → 0.3 |
| **Relative** | All 3 ratios available + sector ≥ 5 stocks | Fewer ratios → lower; small sector → 0.8x penalty |
| **Momentum** | 252+ trading days of price history | 126-251 days → 0.6, <126 → 0.3 |
| **Dividend** | 10+ years of dividend history | 5-9 yrs → 0.7, 2-4 → 0.4, <2 → 0.2 |
| **Quality** | 4+ years of financials + 3+ metrics computed | Fewer years or metrics → lower |

Financial-sector stocks naturally get lower composite confidence because Graham, DCF, and Quality all exclude them — only Relative, Momentum, and Dividend contribute scores. This is intentional: these valuation models don't work well for banks/insurers/REITs.

Confidence also explains run-to-run variation: if cached data expires (24-hour TTL) and yfinance returns a different number of historical years on re-fetch, confidence changes, which shifts both the composite confidence and the weighted score.

## Terminal Output

The report includes:

- **Color-coded scores** — red (0-15), orange (15-30), yellow (30-50), green (50-70), bold green (70+)
- **Inline score bars** — Unicode block characters (█░) providing a visual score at a glance
- **Score histogram** — distribution of scores across 10 bins (0-10 through 90-100)
- **Sector distribution chart** — horizontal bar chart showing which sectors appear in the results
- **Summary footer** — stock count, score range, and average confidence

Use `--verbose` to add per-strategy detail columns to the main table.

## Configuration

All tuneable parameters live in `config.yaml`:

- **Cache**: SQLite path, TTL (default 24 hours)
- **Rate limits**: per-ticker delay, batch size, batch pause (for yfinance)
- **DCF defaults**: projection years, discount rate, terminal growth, growth cap
- **Momentum**: RSI period, SMA windows, signal weights
- **Dividend**: yield trap threshold, minimum history
- **Composite**: per-strategy weights, confidence weighting toggle

## Tech Stack

Python 3.10+ with `yfinance`, `pandas`, `beautifulsoup4`, `numpy`, `scipy`, `rich`, `pyyaml`, and SQLite via `sqlite3`.

## Tests

```bash
python -m unittest discover tests -v
```

## Documentation

- [Project Overview](PROJECT_OVERVIEW.md) — goals, data sources, build order
- [Architecture](ARCHITECTURE.md) — design, components, extensibility
