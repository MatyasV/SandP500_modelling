# S&P 500 Analysis Engine — Architecture

## Design Philosophy

Two core principles drive the design:

**Declare-then-fetch** — each strategy declares exactly which data fields it needs via `required_fields`. The data layer reads that declaration, checks the SQLite cache, and fetches only what's missing. No strategy fetches data directly; no data is fetched that isn't needed.

**Scores for ranking, details for decisions** — every result carries a normalised 0–100 score (for ranking and cross-category filtering) and a `details` dict of real-world data (P/E ratios, FCF values, volatility %, etc.) so users can see what's behind the number.

---

## High-Level Flow

```
CLI
 │
 ├─ cmd_undervalue / cmd_sentiment / cmd_risk / cmd_growth
 │     │
 │     └─▶  Orchestrator.run(strategy, top_n)
 │               │
 │               ├─ 1. fetch_constituents()  ──▶  DataManager  ──▶  SQLite / WikipediaProvider
 │               ├─ 2. strategy.filter_universe(constituents)
 │               ├─ 3. fetch(tickers, strategy.required_fields)  ──▶  SQLite / YFinanceProvider / FREDProvider
 │               ├─ 4. strategy.analyze_all(all_data)
 │               └─ 5. sort by score, return top N  ──▶  Output (rich / CSV / JSON / charts)
 │
 ├─ cmd_correlation
 │     └─▶  CorrelationAnalyzer.compute_matrix(all_data)  ──▶  find_pairs / sector_matrix
 │
 └─ cmd_portfolio
       └─▶  PortfolioOptimizer.optimize_max_sharpe / equal_weight / compute_efficient_frontier
```

---

## Directory Structure

```
SandP500_modelling/
├── cli.py                       # CLI entry point — all subcommands
├── config.yaml                  # cache TTLs, rate limits, strategy parameters
├── requirements.txt
├── README.md
├── PROJECT_OVERVIEW.md
├── ARCHITECTURE.md
├── CLAUDE.md
│
├── data/                        # created at runtime, gitignored
│   └── sp500_cache.db
│
├── output/                      # created at runtime, gitignored
│   └── *.png                    # saved chart files
│
├── sp500/
│   ├── core/
│   │   ├── models.py            # StrategyResult, CacheResult, CorrelationResult, PairResult, AllocationResult
│   │   ├── orchestrator.py      # ties strategies to data, runs analysis end-to-end
│   │   └── registry.py          # discovers all strategies and providers
│   │
│   ├── data/
│   │   ├── fields.py            # DataField enum — the central data contract
│   │   ├── manager.py           # DataManager: cache-first fetching, macro field injection
│   │   ├── cache.py             # SQLiteCache implementation
│   │   └── providers/
│   │       ├── base.py          # BaseProvider ABC
│   │       ├── wiki.py          # S&P 500 constituent list from Wikipedia
│   │       ├── yfinance_.py     # prices, financials, stats, analyst data, dividends
│   │       ├── fred.py          # risk-free rate via yfinance ^TNX proxy
│   │       └── edgar.py         # (future) SEC EDGAR filings
│   │
│   ├── strategies/
│   │   ├── base.py              # BaseStrategy ABC
│   │   ├── undervalue/
│   │   │   ├── graham.py        # Graham Number
│   │   │   ├── dcf.py           # Discounted Cash Flow
│   │   │   ├── relative.py      # Peer-relative valuation
│   │   │   ├── momentum.py      # Price momentum signals
│   │   │   ├── quality.py       # Financial health metrics
│   │   │   ├── dividend.py      # Dividend quality
│   │   │   └── composite.py     # Weighted blend of all undervalue strategies
│   │   ├── sentiment/
│   │   │   ├── analyst.py       # Price target vs current price
│   │   │   ├── recommendations.py  # Buy/hold/sell trend
│   │   │   └── composite.py
│   │   ├── risk/
│   │   │   ├── volatility.py    # Historical vol, beta, max drawdown
│   │   │   ├── risk_adjusted.py # Sharpe/Sortino (uses live risk-free rate)
│   │   │   └── composite.py
│   │   ├── growth/
│   │   │   ├── earnings.py      # Quarterly EPS acceleration
│   │   │   ├── revenue.py       # Revenue growth trajectory
│   │   │   ├── margins.py       # Margin expansion/compression
│   │   │   └── composite.py
│   │   ├── correlation/
│   │   │   └── pairs.py         # CorrelationAnalyzer — matrix, pairs, sector aggregation
│   │   └── portfolio/
│   │       └── optimizer.py     # PortfolioOptimizer — max-Sharpe, equal-weight, frontier
│   │
│   └── output/
│       ├── formatters.py        # format_table, format_csv, format_json, format_pairs_table, format_portfolio_table
│       ├── report.py            # print_report, print_screen_report, print_pairs_report, print_portfolio_report
│       └── charts.py            # matplotlib chart generation — all functions save to output/ and return path
│
└── tests/
    ├── test_cache.py
    ├── test_providers.py
    ├── test_strategies.py
    ├── test_report.py
    ├── test_sentiment_strategies.py
    ├── test_risk_strategies.py
    ├── test_growth_strategies.py
    ├── test_screen.py
    ├── test_fred.py
    ├── test_correlation.py
    ├── test_portfolio.py
    └── test_charts.py
```

---

## Key Components

### DataField — The Data Contract

Every fetchable piece of data has a canonical name in this enum. Strategies reference it to declare requirements. Providers reference it to declare supply. DataManager uses it to route requests.

```python
class DataField(Enum):
    CONSTITUENTS = auto()       # S&P 500 list (Wikipedia)
    INFO = auto()               # yfinance .info dict (P/E, P/B, EPS, beta, etc.)
    INCOME_STMT = auto()        # annual income statement
    INCOME_STMT_Q = auto()      # quarterly income statement
    BALANCE_SHEET = auto()      # annual balance sheet
    BALANCE_SHEET_Q = auto()    # quarterly balance sheet
    CASH_FLOW = auto()          # annual cash flow statement
    CASH_FLOW_Q = auto()        # quarterly cash flow statement
    PRICE_HISTORY = auto()      # OHLCV daily prices
    DIVIDENDS = auto()          # dividend history
    ANALYST_TARGETS = auto()    # analyst price targets
    RECOMMENDATIONS = auto()    # buy/hold/sell recommendations
    INSTITUTIONAL_HOLDERS = auto()
    RISK_FREE_RATE = auto()     # 10-year Treasury yield (FREDProvider / ^TNX)
    INFLATION_RATE = auto()     # (future)
    GDP_GROWTH = auto()         # (future)
```

### BaseProvider

```python
class BaseProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def provides(self) -> set[DataField]: ...

    @abstractmethod
    def fetch(self, tickers: list[str], fields: set[DataField],
              **kwargs) -> dict[str, dict[DataField, Any]]:
        """Returns {ticker: {DataField: data}}. Handles missing data gracefully."""
```

The three active providers and what they supply:

| Provider | Supplies |
|---|---|
| `WikipediaProvider` | `CONSTITUENTS` — fetched once under `"__constituents__"` sentinel key |
| `YFinanceProvider` | `INFO`, `INCOME_STMT`, `INCOME_STMT_Q`, `BALANCE_SHEET`, `BALANCE_SHEET_Q`, `CASH_FLOW`, `CASH_FLOW_Q`, `PRICE_HISTORY`, `DIVIDENDS`, `ANALYST_TARGETS`, `RECOMMENDATIONS`, `INSTITUTIONAL_HOLDERS` |
| `FREDProvider` | `RISK_FREE_RATE` — fetched once under `"__macro__"` sentinel key |

### DataManager — Smart Fetching

`DataManager.fetch(tickers, fields)`:

1. Separates requested fields into per-ticker fields and macro fields (`RISK_FREE_RATE`, etc.)
2. Checks SQLite cache for each `(ticker, field)` pair
3. Fetches only missing fields from the appropriate provider, in rate-limited batches
4. Caches new results
5. Injects macro data (e.g. `RISK_FREE_RATE`) into every ticker's data dict
6. Returns the complete `{ticker: {DataField: data}}` dict

Macro fields are global values (one value shared across all tickers). They are fetched once under a sentinel key (`"__macro__"`) and injected into every ticker's dict automatically. This is the same pattern used for `CONSTITUENTS`.

```python
_MACRO_FIELDS = frozenset({DataField.RISK_FREE_RATE, DataField.INFLATION_RATE, DataField.GDP_GROWTH})
```

### BaseStrategy

```python
@dataclass
class StrategyResult:
    ticker: str
    score: float           # normalised 0–100
    details: dict          # real-world data behind the score (shown in --verbose)
    confidence: float      # 0–1, reflects data completeness

class BaseStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def required_fields(self) -> set[DataField]: ...

    @abstractmethod
    def analyze(self, ticker: str, data: dict) -> StrategyResult | None:
        """Single-ticker analysis. Return None if data is insufficient."""

    def analyze_all(self, all_data: dict) -> list[StrategyResult]:
        """Default: call analyze() per ticker. Override for cross-stock strategies."""

    def filter_universe(self, constituents: pd.DataFrame) -> pd.DataFrame:
        """Pre-filter the S&P 500 list before data is fetched. Default: no filter."""
```

Cross-stock strategies (relative valuation, momentum, dividend, risk, growth) override `analyze_all()` because they need percentile ranking across the full universe.

Financial-sector stocks are excluded from Graham, DCF, and Quality via `filter_universe()` — those models don't apply to banks, insurers, or REITs. All other strategies include all sectors.

### Result Types

Different analysis shapes have dedicated result types:

```python
@dataclass
class StrategyResult:
    ticker: str
    score: float
    details: dict
    confidence: float

@dataclass
class CorrelationResult:
    matrix: pd.DataFrame   # N×N correlation matrix, tickers as index/columns
    tickers: list[str]

@dataclass
class PairResult:
    ticker1: str
    ticker2: str
    correlation: float
    sector1: str = ""
    sector2: str = ""

@dataclass
class AllocationResult:
    weights: dict[str, float]   # ticker → weight, sums to ~1.0
    expected_return: float      # annualised decimal
    expected_volatility: float  # annualised decimal
    sharpe_ratio: float
    tickers: list[str]
    method: str                 # "max_sharpe" or "equal_weight"
```

### Composite Strategy

The `CompositeStrategy` runs its sub-strategies independently and blends their scores:

```
score = Σ(sub_score × weight × confidence) / Σ(weight × confidence)
```

If `weight_by_confidence = True` (default), strategies with incomplete data for a particular ticker contribute proportionally less. This means financial-sector stocks naturally score differently on the composite — only the strategies that actually run on them contribute.

### CorrelationAnalyzer

`CorrelationAnalyzer` is **not** a `BaseStrategy` subclass — it produces matrix/pair output, not a ranked ticker list.

```python
class CorrelationAnalyzer:
    def compute_matrix(self, all_data) -> CorrelationResult
        # Builds aligned daily return DataFrame, computes Pearson correlation matrix

    def find_pairs(self, corr_result, top_n, mode="diversifying", sector_map=None) -> list[PairResult]
        # mode="diversifying": sort ascending (lowest correlation first)
        # mode="correlated":   sort descending (highest correlation first)

    def sector_matrix(self, corr_result, sector_map) -> pd.DataFrame
        # Aggregates to sector level by taking mean pairwise correlation per sector pair
```

### PortfolioOptimizer

`PortfolioOptimizer` is also **not** a `BaseStrategy` subclass — it produces allocation weights, not a ranked ticker list.

```python
class PortfolioOptimizer:
    def optimize_max_sharpe(self, all_data, risk_free_rate=0.045) -> AllocationResult | None
        # SLSQP, long-only (weights in [0,1]), sum-to-1 constraint
        # Falls back to equal-weight if optimisation fails

    def equal_weight(self, all_data) -> AllocationResult | None
        # 1/N weights with actual expected return and volatility computed

    def compute_efficient_frontier(self, all_data, n_portfolios=200, risk_free_rate=0.045) -> list[dict]
        # Random Dirichlet-sampled portfolios; each point is {"vol", "return", "sharpe"}
```

### SQLite Cache

Data is stored as JSON blobs keyed by `(ticker, field)`:

```sql
CREATE TABLE cache (
    ticker     TEXT NOT NULL,
    field      TEXT NOT NULL,   -- DataField enum name, e.g. "INFO"
    data       TEXT NOT NULL,   -- JSON-serialised payload
    fetched_at TIMESTAMP NOT NULL,
    PRIMARY KEY (ticker, field)
);

CREATE TABLE constituents (
    data       TEXT NOT NULL,
    fetched_at TIMESTAMP NOT NULL
);
```

DataFrames are serialised via `df.to_json()` / `pd.read_json()` — safe, inspectable, version-stable. TTL is configurable (default 24 hours). `--no-cache` sets TTL to 0 for a single run.

### Charts

All chart functions in `sp500/output/charts.py` use the `Agg` (non-interactive) matplotlib backend, save to `output/<name>_<timestamp>.png`, and return the file path.

```python
plot_score_distribution(results, category)   # histogram of scores in 10-point bins
plot_sector_allocation(results, sector_map, category)   # horizontal bar chart
plot_correlation_heatmap(corr_result)        # colour-coded N×N heatmap
plot_portfolio_weights(allocation)           # horizontal bar chart sorted by weight
plot_efficient_frontier(frontier_points, optimal_point)  # scatter with Sharpe colourmap
```

---

## Score Conventions

All categories use 0–100. Interpretation varies:

| Category | Higher means |
|---|---|
| Undervalue | More undervalued |
| Sentiment | More bullish analyst consensus |
| Risk | **Riskier** — so `--risk-max 30` selects low-risk stocks |
| Growth | Faster improving fundamentals |

This convention makes cross-category filtering natural: `--undervalue-min 60 --risk-max 30` reads as "undervalued stocks that aren't too risky."

### Confidence

Each `StrategyResult` carries a `confidence` value (0–1) reflecting how complete the input data was. Rules vary by strategy:

| Strategy | Confidence = 1.0 | Lower when |
|---|---|---|
| Graham | Always (or returns None) | N/A |
| DCF | 5+ years of cash flow data | 3–4 yrs → 0.6, <3 → 0.3 |
| Relative | All 3 ratios + sector ≥5 stocks | Fewer ratios; small sector → 0.8× |
| Momentum | 252+ trading days | 126–251 → 0.6, <126 → 0.3 |
| Quality | 4+ years + all metrics present | Fewer years or metrics |
| Dividend | 10+ years of dividend history | 5–9 yrs → 0.7, 2–4 → 0.4, <2 → 0.2 |

---

## Execution Flow Examples

### `python cli.py undervalue --top 20`

```
1. Load CompositeStrategy([Graham, DCF, Relative, Momentum, Quality, Dividend])
2. required_fields = {CONSTITUENTS, INFO, BALANCE_SHEET, INCOME_STMT, CASH_FLOW,
                      PRICE_HISTORY, DIVIDENDS}
3. fetch_constituents() → cache or WikipediaProvider
4. Graham/DCF/Quality filter out Financials via filter_universe()
5. DataManager: check cache, fetch missing from yfinance in batches
6. Each sub-strategy runs analyze_all(); cross-stock strategies rank within sector/universe
7. Composite blends scores weighted by confidence
8. Sort descending, output top 20 via rich table + sector chart + histogram
```

### `python cli.py screen --undervalue-min 70 --risk-max 30`

```
1. Run undervalue composite → 500 tickers scored
2. Run risk composite → 500 tickers scored
   (DataManager shares cache — no duplicate fetches for overlapping fields)
3. Filter: undervalue_score ≥ 70 AND risk_score ≤ 30
4. Output table with both scores side by side
```

### `python cli.py portfolio --from-screen --undervalue-min 60 --top 20 --frontier`

```
1. Run cross-category screen → top 20 tickers by undervalue score
2. DataManager fetches PRICE_HISTORY for those 20 tickers
3. PortfolioOptimizer builds aligned returns DataFrame
4. SLSQP optimises for maximum Sharpe ratio (live risk-free rate from ^TNX injected)
5. Print AllocationResult table + stats panel
6. Save portfolio_weights_*.png to output/
7. Sample 200 random portfolios for efficient frontier
8. Save efficient_frontier_*.png to output/
```

---

## Extensibility

### Adding a strategy

1. Create `sp500/strategies/<category>/your_strategy.py`, subclass `BaseStrategy`
2. Set `required_fields` — the only coupling to the data layer
3. Implement `analyze()` for per-ticker logic, or `analyze_all()` for cross-stock logic
4. Optionally override `filter_universe()` to skip irrelevant stocks before data is fetched
5. Register in `sp500/core/registry.py` in the appropriate `discover_X_strategies()` function

No changes needed anywhere else. The strategy is immediately available via CLI.

### Adding an analysis category

1. Create `sp500/strategies/<category>/` with strategies + composite
2. Add `discover_<category>_strategies(config)` to `registry.py`
3. Add a `cmd_<category>` function and subparser in `cli.py`
4. Optionally add `--<category>-min/max` to the `screen` subparser and `cmd_screen`

### Adding a data source

1. Create `sp500/data/providers/your_provider.py`, subclass `BaseProvider`
2. Declare `provides()` and implement `fetch()`
3. Add new `DataField` entries to `fields.py` if needed
4. Register in `registry.py` `discover_providers()`

DataManager auto-routes requests based on `provides()`. Existing strategies automatically benefit if they already declare those fields.

### Adding a web dashboard

`Orchestrator.run()` and `CorrelationAnalyzer` / `PortfolioOptimizer` return plain data objects with no terminal coupling. A Streamlit or Dash app can call them directly. The SQLite cache file can also be read directly for fast dashboard loads.
