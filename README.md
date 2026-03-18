# S&P 500 Analysis Engine

A modular, extensible Python framework for analysing S&P 500 companies. Fetches only the data each analysis requires, caches it in SQLite, and provides a clean interface for plugging in new analysis strategies.

## Quick Start

```bash
pip install -r requirements.txt
python cli.py undervalue --top 20
```

## Documentation

- [Project Overview](PROJECT_OVERVIEW.md) — goals, data sources, tech stack
- [Architecture](ARCHITECTURE.md) — design, components, extensibility
