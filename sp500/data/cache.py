"""SQLiteCache — caches fetched data as JSON blobs keyed by (ticker, field)."""

import json
import sqlite3
from datetime import datetime, timedelta
from io import StringIO
from typing import Any

import pandas as pd

from sp500.core.models import CacheResult
from sp500.data.fields import DataField

# Fields where the stored data is a DataFrame (use pd.read_json to deserialise)
_DATAFRAME_FIELDS = {
    DataField.INCOME_STMT, DataField.INCOME_STMT_Q,
    DataField.BALANCE_SHEET, DataField.BALANCE_SHEET_Q,
    DataField.CASH_FLOW, DataField.CASH_FLOW_Q,
    DataField.PRICE_HISTORY, DataField.DIVIDENDS,
    DataField.ANALYST_TARGETS, DataField.RECOMMENDATIONS,
    DataField.INSTITUTIONAL_HOLDERS,
}


def _serialise(value: Any) -> str:
    """Serialise a value to JSON string."""
    if isinstance(value, pd.DataFrame):
        return value.to_json(date_format='iso')
    elif isinstance(value, pd.Series):
        return value.to_json(date_format='iso')
    else:
        return json.dumps(value)


def _deserialise(field: DataField, raw: str) -> Any:
    """Deserialise a JSON string back to the appropriate type."""
    if field in _DATAFRAME_FIELDS:
        try:
            return pd.read_json(StringIO(raw))
        except Exception:
            return json.loads(raw)
    else:
        return json.loads(raw)


class SQLiteCache:
    def __init__(self, db_path: str, ttl_hours: int = 24):
        self.db_path = db_path
        self.ttl_hours = ttl_hours
        self.conn = sqlite3.connect(db_path)
        self._init_tables()

    def _init_tables(self) -> None:
        """Create cache tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS cache (
                ticker     TEXT NOT NULL,
                field      TEXT NOT NULL,
                data       TEXT NOT NULL,
                fetched_at TIMESTAMP NOT NULL,
                PRIMARY KEY (ticker, field)
            );

            CREATE TABLE IF NOT EXISTS constituents (
                data       TEXT NOT NULL,
                fetched_at TIMESTAMP NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cache_fetched ON cache(fetched_at);
        """)
        self.conn.commit()

    def get(self, ticker: str, fields: set[DataField]) -> CacheResult:
        """Check cache for each requested field. Returns what's fresh + what's missing."""
        cutoff = (datetime.utcnow() - timedelta(hours=self.ttl_hours)).isoformat()
        found: dict[DataField, Any] = {}
        missing: set[DataField] = set()

        for field in fields:
            row = self.conn.execute(
                "SELECT data, fetched_at FROM cache "
                "WHERE ticker = ? AND field = ? AND fetched_at > ?",
                (ticker, field.name, cutoff),
            ).fetchone()
            if row:
                found[field] = _deserialise(field, row[0])
            else:
                missing.add(field)

        return CacheResult(found=found, missing=missing)

    def put(self, ticker: str, data: dict[DataField, Any]) -> None:
        """Upsert data for a ticker. Serialises DataFrames to JSON."""
        now = datetime.utcnow().isoformat()
        for field, value in data.items():
            self.conn.execute(
                "INSERT OR REPLACE INTO cache (ticker, field, data, fetched_at) "
                "VALUES (?, ?, ?, ?)",
                (ticker, field.name, _serialise(value), now),
            )
        self.conn.commit()

    def invalidate(self, ticker: str | None = None,
                   field: DataField | None = None,
                   older_than: datetime | None = None) -> int:
        """Flexible cache clearing. Returns number of rows deleted."""
        conditions: list[str] = []
        params: list[str] = []

        if ticker is not None:
            conditions.append("ticker = ?")
            params.append(ticker)
        if field is not None:
            conditions.append("field = ?")
            params.append(field.name)
        if older_than is not None:
            conditions.append("fetched_at < ?")
            params.append(older_than.isoformat())

        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = self.conn.execute(f"DELETE FROM cache WHERE {where}", params)
        self.conn.commit()
        return cursor.rowcount

    def get_constituents(self) -> pd.DataFrame | None:
        """Get cached constituents if fresh, else None."""
        row = self.conn.execute(
            "SELECT data, fetched_at FROM constituents ORDER BY fetched_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        fetched_at = datetime.fromisoformat(row[1])
        if datetime.utcnow() - fetched_at > timedelta(hours=self.ttl_hours):
            return None
        return pd.read_json(StringIO(row[0]))

    def put_constituents(self, df: pd.DataFrame) -> None:
        """Cache the constituents DataFrame."""
        self.conn.execute("DELETE FROM constituents")
        self.conn.execute(
            "INSERT INTO constituents (data, fetched_at) VALUES (?, ?)",
            (df.to_json(date_format='iso'), datetime.utcnow().isoformat()),
        )
        self.conn.commit()
