"""DataField enum — canonical names for all fetchable data."""

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
