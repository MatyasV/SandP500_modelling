# CLAUDE.md

## Overview
See `PROJECT_OVERVIEW.md` for full product spec and `ARCHITECTURE.md` for system design.

## Stack
- Python 3.10+
- Data fetching: `yfinance`, `pandas`, `beautifulsoup4`
- Storage: SQLite via `sqlite3`
- Analysis: `numpy`, `scipy`
- Output: `rich` (terminal tables)
- Config: `pyyaml`

## Commands
- `pip install -r requirements.txt` — install dependencies
- `python cli.py undervalue --top 20` — run composite undervalue screen
- `python cli.py undervalue --method graham` — run a single strategy
- `python cli.py cache --status` — check cache state
- `python -m unittest discover tests -v` — run all tests

## Project Structure
- `sp500/data/fields.py` — `DataField` enum, the central data contract
- `sp500/data/providers/base.py` — `BaseProvider` ABC for data sources
- `sp500/strategies/base.py` — `BaseStrategy` ABC for analysis strategies
- `sp500/core/models.py` — `StrategyResult` and `CacheResult` dataclasses
- `sp500/core/orchestrator.py` — ties strategies to data, runs analysis
- `config.yaml` — cache TTLs, rate limits, DCF defaults, composite weights

## Conventions
- Strategies declare data needs via `required_fields` — never fetch data directly
- All strategy scores are normalised 0–100 (higher = more undervalued)
- Every `StrategyResult` carries a `confidence` value (0–1)
- Cross-stock strategies (e.g. relative valuation) override `analyze_all()` instead of `analyze()`
- Financial-sector stocks are excluded from Graham and DCF (not from relative valuation)
- DataFrames are serialised as JSON in SQLite (not pickle)

## Important Constraints
- Do not bypass the cache layer — all data fetching goes through `DataManager`
- Do not add new data fields without adding them to the `DataField` enum first
- yfinance is rate-limited — respect `config.yaml` rate limit settings
- Do not modify `ARCHITECTURE.md` or `PROJECT_OVERVIEW.md` without explicit approval
- Keep strategies independent — no strategy should import another strategy directly (composite uses injection)
