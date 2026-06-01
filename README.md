# S&P 500 Analysis Engine

A modular Python framework for screening and analysing S&P 500 companies across six independent categories: undervalue, sentiment, risk, growth, correlation, and portfolio construction. Data is fetched on demand, cached in SQLite, and all scores are normalised 0–100 so categories can be combined freely.

## Setup

```bash
pip install -r requirements.txt
python cli.py --list-strategies   # verify everything is working
```

---

## Commands

### Undervalue screening

Blends six valuation/quality strategies. Higher score = more undervalued.

```bash
python cli.py undervalue                            # composite (default), top 20
python cli.py undervalue --method graham            # single strategy
python cli.py undervalue --method dcf
python cli.py undervalue --method relative
python cli.py undervalue --method momentum
python cli.py undervalue --method quality
python cli.py undervalue --method dividend

python cli.py undervalue --top 10 --verbose         # show per-strategy detail columns
python cli.py undervalue --weights "graham=2,dcf=1" # override composite weights
python cli.py undervalue --chart                    # save score + sector charts to output/
python cli.py undervalue --format csv --output results.csv
python cli.py undervalue --format json
```

### Sentiment screening

Analyst consensus and recommendation trends. Higher score = more bullish.

```bash
python cli.py sentiment                             # composite (default)
python cli.py sentiment --method analyst
python cli.py sentiment --method recommendations
python cli.py sentiment --top 10 --chart
```

### Risk profiling

Historical volatility and risk-adjusted returns. Higher score = riskier.

```bash
python cli.py risk                                  # composite (default)
python cli.py risk --method volatility
python cli.py risk --method risk_adjusted
python cli.py risk --top 20 --chart
```

### Growth trend screening

Earnings, revenue, and margin trajectory. Higher score = faster improving.

```bash
python cli.py growth                                # composite (default)
python cli.py growth --method earnings
python cli.py growth --method revenue
python cli.py growth --method margins
python cli.py growth --top 20 --chart
```

### Cross-category screening

Combine filters across categories. Only stocks satisfying all conditions are returned.

```bash
python cli.py screen --undervalue-min 60 --risk-max 40
python cli.py screen --undervalue-min 70 --risk-max 30 --growth-min 50 --top 20
python cli.py screen --undervalue-min 50 --top 50
```

Score conventions: `--X-min` means "I want a high score in X"; `--risk-max` means "I want low risk."

### Correlation analysis

Pairwise return correlations. Produces a matrix/pair list, not a ranked ticker list.

```bash
python cli.py correlation --diversification-pairs --top 20   # lowest-corr pairs
python cli.py correlation --correlated --top 20              # highest-corr pairs
python cli.py correlation --sector-matrix                    # sector-level heatmap
python cli.py correlation --pair AAPL MSFT GOOG              # specific tickers
python cli.py correlation --tickers AAPL,MSFT,AMZN,GOOG
```

A correlation heatmap PNG is always saved to `output/`.

### Portfolio construction

Mean-variance optimisation or equal-weight allocation over a given set of tickers.

```bash
python cli.py portfolio --tickers AAPL,MSFT,AMZN,GOOG
python cli.py portfolio --tickers AAPL,MSFT,AMZN --method equal-weight
python cli.py portfolio --tickers AAPL,MSFT,AMZN --frontier   # add efficient frontier chart

# Optimise over stocks from a screen
python cli.py portfolio --from-screen --undervalue-min 60 --top 20
python cli.py portfolio --from-screen --undervalue-min 60 --risk-max 40 --top 20 --frontier
```

A portfolio weights chart PNG is always saved to `output/`. The live risk-free rate is fetched automatically via the 10-year Treasury yield (^TNX).

### Cache management

```bash
python cli.py cache --status
python cli.py cache --clear
python cli.py cache --clear --older-than 48h
```

Use `--no-cache` on any command to bypass the cache for that run.

---

## Strategies

| Category | Method name | What it measures |
|---|---|---|
| undervalue | `graham` | Graham Number vs current price |
| undervalue | `dcf` | Discounted cash flow fair value |
| undervalue | `relative` | P/E, P/B, EV/EBITDA vs sector peers |
| undervalue | `momentum` | RSI, SMA crossover, 52-week high proximity |
| undervalue | `quality` | Leverage, ROE, interest coverage, revenue stability |
| undervalue | `dividend` | Yield, payout sustainability, consistency, growth |
| sentiment | `analyst` | Current price vs analyst price targets |
| sentiment | `recommendations` | Buy/hold/sell trend and direction |
| risk | `volatility` | Historical vol, beta, max drawdown |
| risk | `risk_adjusted` | Sharpe and Sortino ratios (inverted) |
| growth | `earnings` | Quarterly EPS acceleration |
| growth | `revenue` | Revenue growth trajectory |
| growth | `margins` | Gross/operating/net margin expansion |

Each category also has a `composite` method (the default) that blends its strategies using configurable weights.

---

## Composite scoring

The composite uses a confidence-weighted average:

```
score = Σ(sub_score × weight × confidence) / Σ(weight × confidence)
```

Default weights are in `config.yaml`. Strategies with incomplete data automatically contribute less via confidence scaling (`weight_by_confidence: true`).

---

## Configuration

All tunable parameters are in `config.yaml`: cache TTL, yfinance rate limits, DCF assumptions (discount rate, terminal growth), composite weights, momentum signal weights, risk-free rate fallback, and more.

---

## Output

- **Terminal tables** — colour-coded scores (red → orange → yellow → green), inline score bars, sector distribution panel, score histogram
- **Verbose mode** (`--verbose`) — adds per-strategy detail columns (actual ratios, FCF values, etc.)
- **Charts** (`--chart`) — saves PNG files to `output/`; correlation and portfolio always produce a chart
- **Export** — `--format csv` or `--format json` for use in notebooks or spreadsheets

---

## Tests

```bash
python -m unittest discover tests -v   # 152 tests
```

---

## Documentation

- [Project Overview](PROJECT_OVERVIEW.md) — goals, analysis categories, design decisions
- [Architecture](ARCHITECTURE.md) — components, interfaces, extensibility guide
