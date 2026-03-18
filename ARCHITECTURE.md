# S&P 500 Analysis Engine — Architecture

## Design Philosophy

The central problem: different analyses need different data, and we don't want to fetch everything for every run. The architecture solves this with a **declare-then-fetch** pattern — each strategy declares its data requirements upfront, and the data layer fetches only what's needed, checking the cache first.

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
   returns scores                   (rich tables to              │   Data Providers  │
                                     terminal)                   │  ┌─────────────┐  │
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
├── requirements.txt
├── config.yaml                  # cache TTLs, rate limits, default params
│
├── data/                        # SQLite DB + snapshots (gitignored)
│   ├── sp500_cache.db           # main SQLite cache database
│   └── snapshots/               # timestamped full-run exports
│
├── sp500/
│   ├── __init__.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── orchestrator.py      # ties strategies to data, runs analysis
│   │   ├── registry.py          # strategy + provider auto-discovery
│   │   └── models.py            # StrategyResult dataclass, CacheResult, etc.
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── manager.py           # DataManager: resolves requirements → fetches
│   │   ├── cache.py             # SQLiteCache implementation
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # BaseProvider ABC
│   │   │   ├── wiki.py          # WikipediaProvider — S&P 500 constituents
│   │   │   ├── yfinance_.py     # YFinanceProvider — prices, financials, stats
│   │   │   ├── edgar.py         # (future) SEC EDGAR provider
│   │   │   └── fred.py          # (future) FRED macro data provider
│   │   └── fields.py            # DataField enum — canonical field names
│   │
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseStrategy ABC
│   │   ├── undervalue/
│   │   │   ├── __init__.py
│   │   │   ├── graham.py        # Graham Number strategy
│   │   │   ├── dcf.py           # Discounted Cash Flow strategy
│   │   │   ├── relative.py      # Peer-relative valuation (P/E, P/B, etc.)
│   │   │   └── composite.py     # Weighted composite of multiple methods
│   │   └── (future dirs)/       # momentum/, dividend/, etc.
│   │
│   └── output/
│       ├── __init__.py
│       ├── formatters.py        # table, CSV, JSON output formatters
│       └── report.py            # rich terminal report generation
│
├── cli.py                       # CLI entry point
└── tests/
    ├── test_providers.py
    ├── test_strategies.py
    └── test_cache.py
```

---

## Key Components

### 1. DataField Enum — The Data Contract

Every piece of fetchable data has a canonical name. Strategies reference these to declare what they need. Providers reference these to declare what they supply. The DataManager uses these to route requests.

```python
from enum import Enum, auto

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
    ANALYST_TARGETS = auto()     # analyst price targets
    RECOMMENDATIONS = auto()     # analyst recommendations
    INSTITUTIONAL_HOLDERS = auto()

    # --- From FRED (future) ---
    RISK_FREE_RATE = auto()      # 10-year Treasury yield
    INFLATION_RATE = auto()
    GDP_GROWTH = auto()
```

### 2. BaseProvider — Data Source Interface

```python
from abc import ABC, abstractmethod
from typing import Any

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
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
import pandas as pd

@dataclass
class StrategyResult:
    ticker: str
    score: float              # normalised 0–100 (higher = more undervalued)
    details: dict[str, Any]   # strategy-specific breakdown (shown in verbose output)
    confidence: float         # 0–1, how complete the input data was for this ticker

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

### 4. SQLite Cache

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

### 5. DataManager — Smart Fetching Layer

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

### 6. Orchestrator

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

### 7. Composite Strategy

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
        4. Financial-sector stocks will only have relative valuation scores,
           so their composite confidence will naturally be lower
        """
        ...
```

---

## Strategy Implementation Details

### Graham Number

- **Formula**: `Graham Number = sqrt(22.5 × EPS × Book Value Per Share)`
- **Required fields**: `{DataField.INFO}` — yfinance `.info` contains `trailingEps` and `bookValue`
- **Scoring**: `score = ((graham_number - price) / graham_number) * 100`, clamped to 0–100. A score of 50 means the stock trades at 50% below its Graham Number.
- **Confidence**: 1.0 if both EPS and book value are available, 0.0 otherwise (returns None)
- **Universe filter**: excludes `GICS Sector == "Financials"` (banks/insurers have non-standard balance sheets)
- **Edge cases**: skip stocks with negative EPS or negative book value (Graham Number undefined)

### Discounted Cash Flow (DCF)

- **Required fields**: `{DataField.INFO, DataField.CASH_FLOW}`
- **Method**:
  1. Extract Free Cash Flow (FCF) from the last 5 years of annual cash flow statements. FCF = Operating Cash Flow − Capital Expenditure.
  2. Compute 5-year FCF CAGR as the growth rate. Cap at 20% to prevent runaway projections.
  3. Project FCF forward 5 years at the growth rate.
  4. Compute terminal value using Gordon Growth Model: `TV = FCF_year5 × (1 + 2.5%) / (10% − 2.5%)` where 2.5% is long-run growth and 10% is the discount rate.
  5. Discount all projected FCFs and terminal value back to present at 10%.
  6. Divide by shares outstanding to get per-share fair value.
- **Scoring**: `score = ((fair_value - price) / fair_value) * 100`, clamped to 0–100.
- **Confidence**: based on how many years of FCF history are available (5 years = 1.0, 3 years = 0.6, fewer = 0.3 or None)
- **Universe filter**: excludes `GICS Sector == "Financials"`
- **Edge cases**: skip stocks with negative average FCF (DCF doesn't work for cash-burning companies)

### Relative Valuation

- **Required fields**: `{DataField.CONSTITUENTS, DataField.INFO}`
- **Method**:
  1. Group all S&P 500 stocks by GICS Sector (from constituents table)
  2. For each stock, compute its percentile rank within its sector for: P/E (`trailingPE`), P/B (`priceToBook`), EV/EBITDA (`enterpriseToEbitda`)
  3. Invert the percentile: a stock at the 10th percentile (cheaper than 90% of peers) gets score 90
  4. Average the inverted percentiles across the three ratios
- **Scoring**: the averaged inverted percentile IS the score (already 0–100)
- **Confidence**: 1.0 if all three ratios available, 0.67 for two, 0.33 for one, None for zero
- **Universe filter**: none — includes all sectors including financials
- **`analyze_all()` override**: this strategy MUST override `analyze_all()` because it needs to see all stocks in a sector to compute percentile ranks. It cannot work per-ticker.
- **Edge cases**: sectors with fewer than 5 stocks get a confidence penalty (small sample). Negative P/E stocks are excluded from the P/E percentile calculation (but still scored on P/B and EV/EBITDA).

---

## Execution Flow (Composite Undervalue Screen)

```
1. User runs:      python cli.py undervalue --method composite --top 20
2. CLI loads:      CompositeStrategy([GrahamStrategy, DCFStrategy, RelativeStrategy])
3. Composite says: required_fields = {CONSTITUENTS, INFO, BALANCE_SHEET, CASH_FLOW}
                   (union of all sub-strategy requirements)
4. Orchestrator:   Passes requirement set to DataManager
5. DataManager:    Checks SQLite → fetches only stale/missing (ticker, field) pairs
                   from WikipediaProvider and YFinanceProvider, rate-limited
6. Graham:         Runs on non-financial stocks → returns scored results
7. DCF:            Runs on non-financial stocks → returns scored results
8. Relative:       Runs on ALL stocks (incl. financials) → returns scored results
9. Composite:      Blends per-ticker, weighted by confidence
10. Output:        Top 20 printed to terminal via rich table:
                   Ticker | Score | Graham | DCF | Relative | Confidence | Key Metrics
```

## CLI Interface

```bash
# Run composite (default) — top 20 most undervalued
python cli.py undervalue --top 20

# Run a specific strategy only
python cli.py undervalue --method graham --top 30
python cli.py undervalue --method dcf --top 20
python cli.py undervalue --method relative --top 20

# Composite with custom weights
python cli.py undervalue --method composite --weights graham=2,dcf=1,relative=1 --top 20

# Output as CSV instead of terminal table
python cli.py undervalue --format csv --output results.csv

# Force fresh data (ignore cache)
python cli.py undervalue --no-cache

# Show verbose per-stock breakdown
python cli.py undervalue --verbose

# List available strategies
python cli.py --list-strategies

# Cache management
python cli.py cache --status          # show cache size, oldest entry, etc.
python cli.py cache --clear           # wipe entire cache
python cli.py cache --clear --older-than 48h  # clear entries older than 48 hours
```

## Configuration (config.yaml)

```yaml
cache:
  db_path: ./data/sp500_cache.db
  ttl_hours: 24              # cached data considered fresh for this long

rate_limits:
  yfinance:
    delay_seconds: 0.5       # delay between individual ticker fetches
    batch_size: 50            # tickers per batch
    batch_delay: 10           # seconds between batches

dcf:
  projection_years: 5
  terminal_growth_rate: 0.025   # 2.5% — roughly long-run inflation
  discount_rate: 0.10           # 10% flat for v1
  max_growth_cap: 0.20          # cap historical growth rate at 20%

composite:
  default_weights:
    graham: 1.0
    dcf: 1.0
    relative: 1.0
  weight_by_confidence: true    # scale weights by data completeness

defaults:
  top_n: 20
  output_format: table          # table | csv | json
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

### Adding a new data source

1. Create a new provider in `sp500/data/providers/your_provider.py`
2. Subclass `BaseProvider`, declare `provides()`, implement `fetch()`
3. Add new `DataField` entries to the enum if the source provides new kinds of data
4. Register the provider — DataManager auto-routes based on `provides()`
5. Existing strategies automatically benefit if they already request those fields

### Adding a web dashboard

1. `Orchestrator.run()` returns `list[StrategyResult]` — pure data, no terminal coupling
2. A Streamlit/Dash/FastAPI app just calls the orchestrator and renders results however it wants
3. Zero changes to data layer, strategies, or orchestrator
4. The SQLite cache is a regular file — a dashboard can also read it directly for fast loads

## Design Decisions & Trade-offs

- **Per-ticker `analyze()` with `analyze_all()` escape hatch** — most strategies operate on one stock at a time (simpler, independently testable). Strategies that need cross-stock comparison (relative valuation) override `analyze_all()` to see the full dataset.

- **Score normalisation (0–100)** — all strategies output a comparable score so the composite can blend them meaningfully. The normalisation formula is strategy-specific and documented above.

- **Confidence field** — not all stocks have complete data. Rather than silently producing unreliable scores, each result carries a confidence value. The composite weights by confidence by default, so well-covered stocks naturally rank higher.

- **Financial sector exclusion in Graham/DCF** — banks, insurers, and REITs have fundamentally different balance sheet structures (no meaningful "free cash flow" or "book value" in the conventional sense). Excluding them from Graham and DCF is standard practice. They are still scored by relative valuation.

- **SQLite over Parquet/JSON** — SQLite gives queryability (inspect cache state via SQL, selective invalidation, TTL checks), portability (single file, no server), and debuggability (open in DB Browser for SQLite). For ~500 stocks × ~15 fields, performance is not a concern.

- **JSON serialisation for DataFrames** — yfinance returns pandas DataFrames for financial statements. Stored as JSON for safety and inspectability. Slightly slower than pickle but avoids pickle's versioning and security issues.

- **10% flat discount rate for DCF v1** — a proper WACC calculation per company requires beta, risk-free rate, debt ratios, and cost of debt — adding complexity without proportional accuracy gain for a screening tool. 10% is the standard textbook assumption for equity. Can be improved later.

- **Growth rate capped at 20%** — historical FCF CAGR can be wildly high for companies with a low base. Capping prevents the DCF from producing absurdly high fair values for fast-growing but volatile companies.
