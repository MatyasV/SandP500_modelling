"""SQLiteCache — caches fetched data as JSON blobs keyed by (ticker, field)."""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from sp500.core.models import CacheResult
from sp500.data.fields import DataField


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
        # TODO: Implement cache lookup with TTL checking
        raise NotImplementedError

    def put(self, ticker: str, data: dict[DataField, Any]) -> None:
        """Upsert data for a ticker. Serialises DataFrames to JSON."""
        # TODO: Implement cache upsert with JSON serialisation
        raise NotImplementedError

    def invalidate(self, ticker: str | None = None,
                   field: DataField | None = None,
                   older_than: datetime | None = None) -> int:
        """Flexible cache clearing. Returns number of rows deleted."""
        # TODO: Implement selective cache invalidation
        raise NotImplementedError

    def get_constituents(self) -> pd.DataFrame | None:
        """Get cached constituents if fresh, else None."""
        # TODO: Implement constituents cache lookup
        raise NotImplementedError

    def put_constituents(self, df: pd.DataFrame) -> None:
        """Cache the constituents DataFrame."""
        # TODO: Implement constituents cache storage
        raise NotImplementedError
