# S&P 500 Analysis Engine — Architecture

## Design Philosophy

The central problem: different analyses need different data, and we don't want to fetch everything for every run. The architecture solves this with a **declare-then-fetch** pattern — each strategy declares its data requirements upfront, and the data layer fetches only what's needed, checking the cache first.

A second design principle: **scores for ranking, real data for decisions**. Every strategy produces a normalised 0–100 score for ranking and filtering, but results also carry the actual financial data (P/E ratios, FCF values, volatility %, etc.) in a `details` dict so users can see what's behind the number.

## High-Level Flow

```
┌─────────────┐     declares      ┌──────────────┐     requests     ┌──────────────┐
│   Strategy   │ ──────────────▶  │  Orchestrator │ ──────────────▶ │ Data Manager │
│ (e.g. DCF)   │                  │               │                  │              │
└──────┬───────┘                  └──────┬────────┘                  └──────┬───────┘
       │                                 │                                  │
       │  receives clean data            │  receives results                │  checks SQLite
       │◀────────────────────────────────│◀─────────────────────────────────│  then fetches
       │                                 │                                  │  only missing
       ▼                                 ▼                                  ▼
   Analysis logic                   Format & output              ┌──────────────────┐
   returns scores                   (rich tables +               │   Data Providers  │
   + real-world details             charts to terminal)          │  ┌─────────────┐  │
                                                                 │  │  Wikipedia   │  │
                                                                 │  │  yfinance    │  │
                                                                 │  │  EDGAR (opt) │  │
                                                                 │  │  FRED (opt)  │  │
                                                                 │  └─────────────┘  │
                                                                 └──────────────────┘
```

## Directory Structure

```
sp500-engine/
├── README.md
├── PROJECT_OVERVIEW.md
├── ARCHITECTURE.md
├── CLAUDE.md
├── requirements.txt
├── config.yaml                  # cache TTLs, rate limits, strategy params, composite weights
│
├── data/                        # SQLite DB (gitignored)
│   └── sp500_cache.db           # main SQLite cache database
│
├── sp500/
│   ├── __init__.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── orchestrator.py      # ties strategies to data, runs analysis
│   │   ├── registry.py          # strategy + provider auto-discovery
│   │   └── models.py            # StrategyResult, CacheResult dataclasses
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── manager.py           # DataManager: resolves requirements → fetches
│   │   ├── cache.py             # SQLiteCache implementation
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # BaseProvider ABC
│   │   │   ├── wiki.py          # WikipediaProvider — S&P 500 constituents
│   │   │   ├── yfinance_.py     # YFinanceProvider — prices, financials, stats, analyst data
│   │   │   ├── edgar.py         # (future) SEC EDGAR provider
│   │   │   └── fred.py          # (future) FRED macro data provider
│   │   └── fields.py            # DataField enum — canonical field names
│   │
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseStrategy ABC
│   │   ├── undervalue/          # "what's cheap?" — value-oriented analysis
│   │   │   ├── __init__.py
│   │   │   ├── graham.py        # Graham Number strategy
│   │   │   ├── dcf.py           # Discounted Cash Flow strategy
│   │   │   ├── relative.py      # Peer-relative valuation (P/E, P/B, EV/EBITDA)
│   │   │   ├── momentum.py      # Price momentum signals (RSI, SMA, 52-wk high)
│   │   │   ├── quality.py       # Financial health (leverage, ROE, coverage, stability)
│   │   │   ├── dividend.py      # Dividend quality (yield, payout, consistency, growth)
│   │   │   └── composite.py     # Weighted composite of all undervalue methods
│   │   ├── sentiment/           # (planned) "what does the market think?"
│   │   │   ├── __init__.py
│   │   │   ├── analyst.py       # Analyst price targets vs current price
│   │   │   └── recommendations.py  # Buy/hold/sell trend analysis
│   │   ├── risk/                # (planned) "how risky is it?"
│   │   │   ├── __init__.py
│   │   │   ├── volatility.py    # Historical vol, beta, max drawdown
│   │   │   └── sharpe.py        # Risk-adjusted returns (Sharpe, Sortino)
│   │   ├── growth/              # (planned) "is it improving?"
│   │   │   ├── __init__.py
│   │   │   ├── earnings_trend.py   # Quarterly EPS acceleration
│   │   │   ├── revenue_trend.py    # Revenue growth trajectory
│   │   │   └── margin.py           # Margin expansion/compression
│   │   ├── correlation/         # (planned) "what moves together?"
│   │   │   ├── __init__.py
│   │   │   └── pairs.py         # Correlation matrix, pair identification
│   │   └── portfolio/           # (planned) "how to allocate?"
│   │       ├── __init__.py
│   │       └── optimizer.py     # Mean-variance, diversification, risk budget
│   │
│   └── output/
│       ├── __init__.py
│       ├── formatters.py        # table, CSV, JSON output formatters
│       ├── report.py            # rich terminal report generation
│       └── charts.py            # (planned) matplotlib chart generation
│
├── output/                      # (planned) saved chart images (gitignored)
│
├── cli.py                       # CLI entry point
└── tests/
    ├── test_cache.py
    ├── test_providers.py
    ├── test_strategies.py
    └── test_report.py
```

---

## Key Components

### 1. DataField Enum — The Data Contract

Every piece of fetchable data has a canonical name. Strategies reference these to declare what they need. Providers reference these to declare what they supply. The DataManager uses these to route requests.

```python
class DataField(Enum):
    # --- From Wikipedia ---
    CONSTITUENTS = auto()        # full S&P 500 list: ticker, name, sector, sub-industry, etc.

    # --- From yfinance: info dict ---
    INFO = auto()                # .info dict: P/E, P/B, market cap, beta, EPS, book value, etc.

    # --- From yfinance: financial statements ---
    INCOME_STMT = auto()         # annual income statement
    INCOME_STMT_Q = auto()       # quarterly income statement
    BALANCE_SHEET = auto()       # annual balance sheet
    BALANCE_SHEET_Q = auto()     # quarterly balance sheet
    CASH_FLOW = auto()           # annual cash flow statement
    CASH_FLOW_Q = auto()         # quarterly cash flow statement

    # --- From yfinance: market data ---
    PRICE_HISTORY = auto()       # OHLCV historical prices
    DIVIDENDS = auto()           # dividend history
    ANALYST_TARGETS = auto()     # analyst price targets (used by sentiment)
    RECOMMENDATIONS = auto()     # analyst recommendations (used by sentiment)
    INSTITUTIONAL_HOLDERS = auto()

    # --- From FRED (future) ---
    RISK_FREE_RATE = auto()      # 10-year Treasury yield
    INFLATION_RATE = auto()
    GDP_GROWTH = auto()
```

### 2. BaseProvider — Data Source Interface

```python
class BaseProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name for logging."""
        ...

    @abstractmethod
    def provides(self) -> set[DataField]:
        """Which DataFields this provider can supply."""
        ...

    @abstractmethod
    def fetch(self, tickers: list[str], fields: set[DataField],
              **kwargs) -> dict[str, dict[DataField, Any]]:
        """
        Fetch the requested fields for the given tickers.
        Returns: {ticker: {DataField: data, ...}, ...}
        Only fetches the intersection of `fields` and `self.provides()`.
        Should handle missing data gracefully (return what's available, skip what isn't).
        """
        ...
```

### 3. BaseStrategy — Analysis Interface

```python
@dataclass
class StrategyResult:
    ticker: str
    score: float              # normalised 0–100
    details: dict[str, Any]   # real-world data shown to user (P/E, vol%, etc.)
    confidence: float         # 0–1, how complete the input data was

class BaseStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy identifier, used in CLI and composite references."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line description shown in --list-strategies."""
        ...

    @property
    @abstractmethod
    def required_fields(self) -> set[DataField]:
        """DataFields this strategy needs to run."""
        ...

    @abstractmethod
    def analyze(self, ticker: str, data: dict[DataField, Any]) -> StrategyResult | None:
        """
        Run analysis on a single ticker.
        Returns None if there's not enough data to produce a meaningful result.
        """
        ...

    def analyze_all(self, all_data: dict[str, dict[DataField, Any]]) -> list[StrategyResult]:
        """
        Run analysis across the full universe.
        Default implementation: call analyze() per ticker.
        Override for strategies that need cross-stock comparison (e.g. relative valuation).
        """
        results = []
        for ticker, data in all_data.items():
            result = self.analyze(ticker, data)
            if result is not None:
                results.append(result)
        return results

    def filter_universe(self, constituents: pd.DataFrame) -> pd.DataFrame:
        """
        Optional: pre-filter the S&P 500 list before any data is fetched.
        Default: no filtering (analyse all ~500 companies).
        Override to e.g. exclude financial-sector stocks, saving API calls.
        The constituents DataFrame has columns: Symbol, Security, GICS Sector,
        GICS Sub-Industry, Headquarters Location, Date added, CIK, Founded.
        """
        return constituents
```

**Important conventions:**
- `details` dict carries the actual financial data behind the score — this is what gets shown to users alongside the score in verbose output
- Cross-stock strategies (relative valuation, risk profiling) override `analyze_all()` instead of `analyze()`
- Financial-sector stocks are excluded from Graham, DCF, and Quality (not from relative, momentum, dividend, sentiment, or risk)

### 4. Result Types

**Ranked results** (undervalue, sentiment, risk, growth): `list[StrategyResult]` — a scored, ranked list of tickers. Each result carries both the score (for ranking/filtering) and real-world details (for user context).

**Matrix results** (correlation — planned): A different return type — `MatrixResult` or similar — since the output is a correlation matrix or pair list, not a ranked ticker list.

**Portfolio results** (portfolio construction — planned): Takes other results as input, outputs allocation weights. Another specialised return type.

### 5. SQLite Cache

Stores fetched data as JSON blobs keyed by (ticker, field). Each entry is timestamped so we can expire stale data.

```sql
CREATE TABLE IF NOT EXISTS cache (
    ticker     TEXT NOT NULL,
    field      TEXT NOT NULL,        -- DataField enum name (e.g. "INFO", "BALANCE_SHEET")
    data       TEXT NOT NULL,        -- JSON-serialised payload
    fetched_at TIMESTAMP NOT NULL,
    PRIMARY KEY (ticker, field)
);

CREATE TABLE IF NOT EXISTS constituents (
    data       TEXT NOT NULL,        -- JSON-serialised DataFrame
    fetched_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cache_fetched ON cache(fetched_at);
```

```python
@dataclass
class CacheResult:
    found: dict[DataField, Any]     # fields in cache and still fresh
    missing: set[DataField]         # fields that need fetching

class SQLiteCache:
    def __init__(self, db_path: str, ttl_hours: int = 24):
        self.db_path = db_path
        self.ttl_hours = ttl_hours
        self.conn = sqlite3.connect(db_path)
        self._init_tables()

    def get(self, ticker: str, fields: set[DataField]) -> CacheResult:
        """Check cache for each requested field. Returns what's fresh + what's missing."""
        ...

    def put(self, ticker: str, data: dict[DataField, Any]) -> None:
        """Upsert data for a ticker. Serialises DataFrames to JSON."""
        ...

    def invalidate(self, ticker: str | None = None,
                   field: DataField | None = None,
                   older_than: datetime | None = None) -> int:
        """Flexible cache clearing. Returns number of rows deleted."""
        ...

    def get_constituents(self) -> pd.DataFrame | None:
        """Get cached constituents if fresh, else None."""
        ...

    def put_constituents(self, df: pd.DataFrame) -> None:
        """Cache the constituents DataFrame."""
        ...
```

**Serialisation note**: yfinance returns pandas DataFrames for financial statements. These are stored as JSON via `df.to_json()` and restored via `pd.read_json()`. This is slightly slower than pickle but safe, inspectable, and version-stable.

### 6. DataManager — Smart Fetching Layer

```python
class DataManager:
    def __init__(self, providers: list[BaseProvider], cache: SQLiteCache, config: dict):
        self.providers = providers
        self.cache = cache
        self.config = config
        self._field_to_provider: dict[DataField, BaseProvider] = self._build_field_map()

    def fetch(self, tickers: list[str], fields: set[DataField]) -> dict[str, dict[DataField, Any]]:
        """
        Fetch only the requested fields for the given tickers.
        1. Check SQLite cache for each (ticker, field) pair
        2. Group missing fields by provider
        3. Fetch from providers in rate-limited batches
        4. Cache the results
        5. Return the complete dataset
        """
        ...

    def fetch_constituents(self) -> pd.DataFrame:
        """Fetch the S&P 500 list. Checks cache first, falls back to WikipediaProvider."""
        ...
```

### 7. Orchestrator

```python
class Orchestrator:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def run(self, strategy: BaseStrategy, top_n: int = 20) -> list[StrategyResult]:
        """
        Run a single strategy (including composite) end-to-end:
        1. Fetch S&P 500 constituents
        2. Let strategy filter the universe (e.g. exclude financials)
        3. Fetch ONLY the DataFields this strategy declared
        4. Run analysis
        5. Sort by score descending, return top N
        """
        ...
```

### 8. Composite Strategy

The composite doesn't do its own maths — it runs the component strategies and blends their scores.

```python
class CompositeStrategy(BaseStrategy):
    def __init__(self, strategies: list[BaseStrategy],
                 weights: dict[str, float] | None = None,
                 weight_by_confidence: bool = True):
        self.strategies = strategies
        self.weights = weights or {s.name: 1.0 for s in strategies}
        self.weight_by_confidence = weight_by_confidence

    @property
    def required_fields(self) -> set[DataField]:
        # Union of all sub-strategy requirements
        return set().union(*(s.required_fields for s in self.strategies))

    def analyze_all(self, all_data: dict[str, dict[DataField, Any]]) -> list[StrategyResult]:
        """
        1. Run each sub-strategy independently over the full dataset
        2. For each ticker, compute weighted average of available scores
        3. If weight_by_confidence is True, scale each sub-strategy's weight
           by its confidence for that ticker
        4. Financial-sector stocks will only have relative/momentum/dividend scores,
           so their composite confidence will naturally be lower
        """
        ...
```

---

## Score Conventions

All categories use 0–100 scores. The interpretation varies by category:

| Category | Score meaning | Higher = |
|---|---|---|
| Undervalue | Margin of safety / upside | More undervalued |
| Sentiment | Analyst bullishness | More bullish consensus |
| Risk | Risk level | **Riskier** (so `--risk-max 30` = low risk) |
| Growth | Improvement rate | Faster improving |

This convention means `screen` filters use `--<category>-min` for "I want high scores" and `--<category>-max` for "I want low scores". Risk is intentionally "higher = riskier" so that `--risk-max` reads naturally.

---

## Strategy Implementation Details

### Undervalue: Graham Number

- **Formula**: `Graham Number = sqrt(22.5 × EPS × Book Value Per Share)`
- **Required fields**: `{DataField.INFO}` — yfinance `.info` contains `trailingEps` and `bookValue`
- **Scoring**: `score = ((graham_number - price) / graham_number) * 100`, clamped to 0–100
- **Details shown to user**: EPS, book value per share, Graham number, current price, margin of safety %
- **Confidence**: 1.0 if both EPS and book value are available, 0.0 otherwise (returns None)
- **Universe filter**: excludes `GICS Sector == "Financials"`
- **Edge cases**: skip stocks with negative EPS or negative book value (Graham Number undefined)

### Undervalue: DCF

- **Required fields**: `{DataField.INFO, DataField.CASH_FLOW}`
- **Method**:
  1. Extract Free Cash Flow (FCF) from the last 5 years of annual cash flow statements. FCF = Operating Cash Flow − Capital Expenditure.
  2. Compute 5-year FCF CAGR as the growth rate. Cap at 20% to prevent runaway projections.
  3. Project FCF forward 5 years at the growth rate.
  4. Compute terminal value using Gordon Growth Model: `TV = FCF_year5 × (1 + 2.5%) / (10% − 2.5%)`
  5. Discount all projected FCFs and terminal value back to present at 10%.
  6. Divide by shares outstanding to get per-share fair value.
- **Scoring**: `score = ((fair_value - price) / fair_value) * 100`, clamped to 0–100
- **Details shown to user**: historical FCF values, growth rate used, projected fair value, current price, upside %
- **Confidence**: 5 years = 1.0, 3 years = 0.6, fewer = 0.3 or None
- **Universe filter**: excludes `GICS Sector == "Financials"`
- **Edge cases**: skip stocks with negative average FCF

### Undervalue: Relative Valuation

- **Required fields**: `{DataField.CONSTITUENTS, DataField.INFO}`
- **Method**:
  1. Group all S&P 500 stocks by GICS Sector
  2. Compute percentile rank within sector for: P/E, P/B, EV/EBITDA
  3. Invert the percentile: 10th percentile (cheaper than 90%) → score 90
  4. Average the inverted percentiles across three ratios
- **Details shown to user**: actual P/E, P/B, EV/EBITDA values, sector median for each, percentile rank
- **Confidence**: 1.0 for three ratios, 0.67 for two, 0.33 for one, None for zero
- **Uses**: `analyze_all()` (cross-stock)
- **Includes**: all sectors

### Undervalue: Momentum

- **Required fields**: `{DataField.PRICE_HISTORY}`
- **Method**: RSI (14-period, weight 0.35), SMA 50/200 crossover (0.35), 52-week high proximity (0.30). Cross-stock percentile ranking.
- **Details shown to user**: RSI value, 50-day SMA, 200-day SMA, current vs 52-week high %
- **Confidence**: 1.0 with 252+ days, 0.6 with 126-251, 0.3 with fewer
- **Uses**: `analyze_all()` (cross-stock)

### Undervalue: Quality

- **Required fields**: `{DataField.INFO, DataField.BALANCE_SHEET, DataField.INCOME_STMT}`
- **Method**: Scores D/E ratio, ROE, interest coverage, revenue stability (coefficient of variation). Each mapped 0–100, then averaged.
- **Details shown to user**: D/E ratio, ROE %, interest coverage ratio, revenue CV
- **Confidence**: varies by data completeness (years of financials + number of metrics available)
- **Universe filter**: excludes `GICS Sector == "Financials"`

### Undervalue: Dividend

- **Required fields**: `{DataField.INFO, DataField.DIVIDENDS, DataField.CONSTITUENTS}`
- **Method**: Yield percentile (30%), payout sustainability (30%), consistency (20%), CAGR (20%). Yield trap detection (>8% penalised).
- **Details shown to user**: dividend yield %, payout ratio, years of history, CAGR %, yield trap flag
- **Confidence**: 1.0 with 10+ years, 0.7 with 5-9, 0.4 with 2-4, 0.2 with fewer
- **Uses**: `analyze_all()` (cross-stock)

### Undervalue: Composite

- **Weights** (from config.yaml): graham=1.0, dcf=1.0, relative=1.0, momentum=0.8, quality=1.0, dividend=0.8
- **Blending**: per-ticker weighted average of available sub-scores, optionally scaled by confidence
- **Details shown to user**: individual sub-scores from each strategy

### Sentiment: Analyst Consensus (planned)

- **Required fields**: `{DataField.INFO, DataField.ANALYST_TARGETS}`
- **Method**: Compare current price to mean/median analyst price target. Score based on upside %.
- **Details shown to user**: current price, mean target, median target, high/low targets, # analysts, % upside
- **Graphical**: target price range chart (low—median—high vs current price)

### Sentiment: Recommendation Trends (planned)

- **Required fields**: `{DataField.RECOMMENDATIONS}`
- **Method**: Track buy/hold/sell breakdown and how it's shifting over recent months. Score based on bullishness and trend direction.
- **Details shown to user**: current buy/hold/sell counts, 3-month trend, upgrade/downgrade count
- **Graphical**: recommendation trend sparklines

### Risk: Volatility (planned)

- **Required fields**: `{DataField.PRICE_HISTORY, DataField.INFO}`
- **Method**: Annualised historical volatility from daily returns, beta from INFO, max drawdown from price history
- **Scoring**: 0–100, higher = riskier
- **Details shown to user**: annualised vol %, beta, max drawdown %, drawdown recovery period
- **Graphical**: volatility histogram, drawdown chart

### Risk: Risk-Adjusted Returns (planned)

- **Required fields**: `{DataField.PRICE_HISTORY}`
- **Method**: Sharpe ratio (return / vol), Sortino ratio (return / downside deviation)
- **Scoring**: 0–100, higher = riskier (inverted Sharpe/Sortino)
- **Details shown to user**: annualised return %, Sharpe, Sortino, downside deviation
- **Graphical**: risk-return scatter plot

### Growth: Earnings Trend (planned)

- **Required fields**: `{DataField.INCOME_STMT_Q}`
- **Method**: Quarterly EPS trajectory — QoQ and YoY growth rates, acceleration detection
- **Details shown to user**: last 4-8 quarters of EPS, growth rates, trend direction
- **Graphical**: quarterly EPS sparkline

### Growth: Revenue Trend (planned)

- **Required fields**: `{DataField.INCOME_STMT_Q}`
- **Method**: Revenue growth trajectory, trend line fitting
- **Details shown to user**: quarterly revenue, growth rates, trend slope

### Growth: Margin Analysis (planned)

- **Required fields**: `{DataField.INCOME_STMT_Q}`
- **Method**: Gross/operating/net margin over time, expansion vs compression detection
- **Details shown to user**: margin % per quarter, direction, magnitude

### Correlation: Pairs (planned)

- **Required fields**: `{DataField.PRICE_HISTORY, DataField.CONSTITUENTS}`
- **Output type**: Matrix/pair list (not ranked ticker list)
- **Details shown to user**: correlation coefficients, sector info
- **Graphical**: heatmaps, rolling correlation charts, dual-axis price overlay

### Portfolio: Optimiser (planned)

- **Required fields**: `{DataField.PRICE_HISTORY}` + results from other categories as input
- **Output type**: Allocation weights (not ranked ticker list)
- **Details shown to user**: suggested weights, expected return/vol, Sharpe, sector concentration
- **Graphical**: efficient frontier, sector allocation chart, weight comparison bars

---

## Execution Flow Examples

### Single category: `python cli.py undervalue --method composite --top 20`

```
1. CLI parses:     category=undervalue, method=composite
2. Load:           CompositeStrategy([Graham, DCF, Relative, Momentum, Quality, Dividend])
3. Composite says: required_fields = {CONSTITUENTS, INFO, BALANCE_SHEET, INCOME_STMT,
                                      CASH_FLOW, PRICE_HISTORY, DIVIDENDS}
4. Orchestrator:   Passes requirement set to DataManager
5. DataManager:    Checks SQLite → fetches only stale/missing (ticker, field) pairs
                   from WikipediaProvider and YFinanceProvider, rate-limited
6. Graham:         Runs on non-financial stocks → returns scored results with details
7. DCF:            Runs on non-financial stocks → returns scored results with details
8. Relative:       Runs on ALL stocks → returns scored results with details
9. Momentum:       Runs on ALL stocks → returns scored results with details
10. Quality:       Runs on non-financial stocks → returns scored results with details
11. Dividend:      Runs on ALL stocks → returns scored results with details
12. Composite:     Blends per-ticker, weighted by confidence
13. Output:        Top 20 via rich table: Rank | Ticker | Score | Bar | Confidence
                   + sector distribution chart + score histogram
                   Verbose mode adds: Graham | DCF | Relative | Momentum | Quality | Dividend
```

### Cross-category: `python cli.py screen --undervalue-min 70 --risk-max 30 --top 20`

```
1. CLI parses:     screen mode, filters: undervalue≥70, risk≤30
2. Identify:       Need undervalue composite + risk composite
3. DataManager:    Fetches union of required fields (shared fields hit cache — no duplication)
4. Run:            Undervalue composite → 500 tickers scored
5. Run:            Risk composite → 500 tickers scored
6. Filter:         Keep tickers where undervalue_score ≥ 70 AND risk_score ≤ 30
7. Output:         Table with both scores + key real-world data from each category
                   (P/E, fair value, vol%, beta, etc.)
```

---

## CLI Interface

```bash
# === Undervalue (existing) ===
python cli.py undervalue --top 20                          # composite (default)
python cli.py undervalue --method graham --top 30          # single strategy
python cli.py undervalue --method composite --weights graham=2,dcf=1 --top 20
python cli.py undervalue --verbose                         # show real-world details
python cli.py undervalue --format csv --output results.csv

# === Sentiment (Phase 1) ===
python cli.py sentiment --method analyst --top 20
python cli.py sentiment --method recommendations --top 20

# === Risk (Phase 2) ===
python cli.py risk --method volatility --top 20
python cli.py risk --method sharpe --top 20

# === Growth (Phase 2) ===
python cli.py growth --method earnings-trend --top 20
python cli.py growth --method revenue-trend --top 20
python cli.py growth --method margin --top 20

# === Cross-category screening (Phase 2) ===
python cli.py screen --undervalue-min 70 --risk-max 30 --top 20
python cli.py screen --undervalue-min 60 --growth-min 50 --sentiment-min 60 --top 10

# === Correlation (Phase 3) ===
python cli.py correlation --pair AAPL MSFT
python cli.py correlation --sector-matrix
python cli.py correlation --diversification-pairs --top 20

# === Portfolio (Phase 3) ===
python cli.py portfolio --from-screen "undervalue-min=70,risk-max=30" --top 20
python cli.py portfolio --tickers AAPL,MSFT,GOOGL --optimize

# === Cache (existing) ===
python cli.py cache --status
python cli.py cache --clear
python cli.py cache --clear --older-than 48h

# === General ===
python cli.py --list-strategies
python cli.py undervalue --no-cache
```

## Configuration (config.yaml)

```yaml
cache:
  db_path: ./data/sp500_cache.db
  ttl_hours: 24

rate_limits:
  yfinance:
    delay_seconds: 0.5
    batch_size: 50
    batch_delay: 10

dcf:
  projection_years: 5
  terminal_growth_rate: 0.025
  discount_rate: 0.10
  max_growth_cap: 0.20

momentum:
  rsi_period: 14
  sma_short: 50
  sma_long: 200
  weights:
    rsi: 0.35
    ma_crossover: 0.35
    high_proximity: 0.30

dividend:
  yield_trap_threshold: 0.08
  min_history_years: 1

risk:                             # (Phase 2)
  lookback_days: 252              # 1 year of trading days
  risk_free_rate: 0.045           # fallback if FRED not available

growth:                           # (Phase 2)
  min_quarters: 4                 # minimum quarters for trend analysis

composite:
  default_weights:
    graham: 1.0
    dcf: 1.0
    relative: 1.0
    momentum: 0.8
    quality: 1.0
    dividend: 0.8
  weight_by_confidence: true

defaults:
  top_n: 20
  output_format: table
```

## Extensibility

### Adding a new strategy

1. Create a new file in `sp500/strategies/<category>/your_strategy.py`
2. Subclass `BaseStrategy`
3. Set `required_fields` — this is the ONLY coupling to the data layer
4. Implement `analyze()` (and optionally `analyze_all()` for cross-stock strategies)
5. Optionally override `filter_universe()` to skip irrelevant stocks before data is fetched
6. The strategy is immediately usable standalone AND as a component in composite scoring
7. No changes needed to data layer, orchestrator, or existing strategies

### Adding a new analysis category

1. Create directory `sp500/strategies/<category>/`
2. Add strategies following the same `BaseStrategy` interface
3. Register the category in CLI (add subcommand)
4. Optionally add `--<category>-min` / `--<category>-max` to screen command
5. Add category-specific chart functions to `sp500/output/charts.py`

### Adding a new data source

1. Create a new provider in `sp500/data/providers/your_provider.py`
2. Subclass `BaseProvider`, declare `provides()`, implement `fetch()`
3. Add new `DataField` entries to the enum if the source provides new kinds of data
4. Register the provider — DataManager auto-routes based on `provides()`
5. Existing strategies automatically benefit if they already request those fields

### Adding graphical output

1. Add chart functions to `sp500/output/charts.py`
2. Each chart function takes strategy results and returns a matplotlib figure
3. CLI `--chart` flag triggers chart generation alongside table output
4. Charts saved to `output/` directory as PNG

### Adding a web dashboard

1. `Orchestrator.run()` returns `list[StrategyResult]` — pure data, no terminal coupling
2. A Streamlit/Dash/FastAPI app just calls the orchestrator and renders results however it wants
3. Zero changes to data layer, strategies, or orchestrator
4. The SQLite cache is a regular file — a dashboard can also read it directly for fast loads

## Design Decisions & Trade-offs

- **Scores for ranking, details for decisions** — abstract scores enable cross-category filtering and composite blending; real-world data in `details` ensures users aren't flying blind. Both are always computed and available.

- **Per-ticker `analyze()` with `analyze_all()` escape hatch** — most strategies operate on one stock at a time (simpler, independently testable). Strategies that need cross-stock comparison (relative valuation, risk profiling) override `analyze_all()` to see the full dataset.

- **Score normalisation (0–100)** — all strategies output a comparable score so composites can blend them and the screen command can filter across categories. The normalisation formula is strategy-specific. Risk uses "higher = riskier" to enable natural `--risk-max` filtering.

- **Separate result types for different output shapes** — ranked lists use `StrategyResult`, correlation uses a matrix type, portfolio uses an allocation type. Cleaner than forcing everything through one shape.

- **Confidence field** — not all stocks have complete data. Rather than silently producing unreliable scores, each result carries a confidence value. Composites weight by confidence by default, so well-covered stocks naturally rank higher.

- **Financial sector exclusion in Graham/DCF/Quality** — banks, insurers, and REITs have fundamentally different balance sheet structures. Excluded from fundamental analysis but included in relative, momentum, dividend, sentiment, and risk.

- **Sentiment separate from undervalue** — analyst targets are opinions, not fundamental measurements. Keeping them separate avoids diluting data-grounded scores with consensus bias. Users see both and can judge convergence.

- **SQLite over Parquet/JSON files** — SQLite gives queryability, portability, and debuggability. For ~500 stocks × ~15 fields, performance is not a concern.

- **JSON serialisation for DataFrames** — safer and more inspectable than pickle, with no versioning issues.

- **10% flat discount rate for DCF v1** — proper WACC requires FRED integration (Phase 3). 10% is the standard textbook assumption for equity.

- **Growth rate capped at 20%** — prevents DCF from producing absurdly high fair values for companies with volatile FCF history.

- **matplotlib for charts** — lightweight, no server needed, good terminal/file output. Can be replaced with plotly later if a web dashboard is added.
