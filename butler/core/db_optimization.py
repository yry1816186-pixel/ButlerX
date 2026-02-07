"""Database optimization utilities for Smart Butler system."""

import hashlib
import json
import logging
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from collections import OrderedDict

from .exceptions import DatabaseError
from .utils import utc_ts

logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """Cache eviction strategies."""

    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"
    TTL = "ttl"


@dataclass
class CacheEntry:
    """Entry in the cache.

    Attributes:
        key: Cache key
        value: Cached value
        created_ts: Creation timestamp
        last_access_ts: Last access timestamp
        access_count: Number of times accessed
        ttl_sec: Time to live in seconds
        expires_at: Expiration timestamp
    """

    key: str
    value: Any
    created_ts: float
    last_access_ts: float
    access_count: int
    ttl_sec: Optional[float] = None
    expires_at: Optional[float] = None

    @property
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.expires_at is None:
            return False
        return utc_ts() > self.expires_at

    def access(self) -> None:
        """Record an access to this entry."""
        self.last_access_ts = utc_ts()
        self.access_count += 1


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""

    @abstractmethod
    def set(self, key: str, value: Any, ttl_sec: Optional[float] = None) -> None:
        """Set value in cache."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete value from cache."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries."""

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""


class MemoryCache(CacheBackend):
    """In-memory cache with configurable eviction strategy."""

    def __init__(
        self,
        max_size: int = 1000,
        strategy: CacheStrategy = CacheStrategy.LRU,
        default_ttl_sec: Optional[float] = None,
    ) -> None:
        """Initialize memory cache.

        Args:
            max_size: Maximum number of entries
            strategy: Eviction strategy
            default_ttl_sec: Default time-to-live for entries
        """
        self.max_size = max_size
        self.strategy = strategy
        self.default_ttl_sec = default_ttl_sec

        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired:
            self.delete(key)
            self._misses += 1
            return None

        entry.access()
        self._hits += 1

        if self.strategy == CacheStrategy.LRU:
            self._cache.move_to_end(key)

        return entry.value

    def set(self, key: str, value: Any, ttl_sec: Optional[float] = None) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_sec: Time-to-live in seconds
        """
        now = utc_ts()
        ttl = ttl_sec or self.default_ttl_sec
        expires_at = now + ttl if ttl else None

        entry = CacheEntry(
            key=key,
            value=value,
            created_ts=now,
            last_access_ts=now,
            access_count=0,
            ttl_sec=ttl,
            expires_at=expires_at,
        )

        if key in self._cache:
            del self._cache[key]

        self._cache[key] = entry

        if self.strategy == CacheStrategy.LRU:
            self._cache.move_to_end(key)

        self._evict_if_needed()

    def delete(self, key: str) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "evictions": self._evictions,
            "strategy": self.strategy.value,
        }

    def _evict_if_needed(self) -> None:
        """Evict entries if cache is full."""
        while len(self._cache) > self.max_size:
            self._evict_one()

    def _evict_one(self) -> None:
        """Evict one entry based on strategy."""
        if not self._cache:
            return

        if self.strategy == CacheStrategy.LRU:
            key, _ = self._cache.popitem(last=False)

        elif self.strategy == CacheStrategy.FIFO:
            key, _ = self._cache.popitem(last=False)

        elif self.strategy == CacheStrategy.LFU:
            key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].access_count,
            )
            del self._cache[key]

        elif self.strategy == CacheStrategy.TTL:
            now = utc_ts()
            expired_keys = [
                k for k, v in self._cache.items()
                if v.is_expired
            ]
            if expired_keys:
                key = expired_keys[0]
            else:
                key, _ = self._cache.popitem(last=False)
        else:
            key, _ = self._cache.popitem(last=False)

        self._evictions += 1
        logger.debug("Evicted cache entry: %s", key)


class QueryCache:
    """Cache for database query results.

    Automatically invalidates cache based on table changes.
    """

    def __init__(
        self,
        cache_backend: Optional[CacheBackend] = None,
        default_ttl_sec: float = 60.0,
    ) -> None:
        """Initialize query cache.

        Args:
            cache_backend: Cache backend to use
            default_ttl_sec: Default TTL for cached queries
        """
        self.cache = cache_backend or MemoryCache(
            max_size=500,
            strategy=CacheStrategy.LRU,
            default_ttl_sec=default_ttl_sec,
        )
        self._table_versions: Dict[str, str] = {}
        self._table_listeners: Dict[str, List[Callable]] = {}

    def get(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None,
        table: Optional[str] = None,
    ) -> Optional[Any]:
        """Get cached query result.

        Args:
            query: SQL query
            params: Query parameters
            table: Primary table being queried

        Returns:
            Cached result or None if not found or stale
        """
        if table and self._is_table_stale(table):
            self.invalidate_table(table)
            return None

        cache_key = self._build_key(query, params)
        return self.cache.get(cache_key)

    def set(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None,
        result: Any = None,
        table: Optional[str] = None,
        ttl_sec: Optional[float] = None,
    ) -> None:
        """Cache query result.

        Args:
            query: SQL query
            params: Query parameters
            result: Query result to cache
            table: Primary table being queried
            ttl_sec: Time-to-live in seconds
        """
        cache_key = self._build_key(query, params)
        self.cache.set(cache_key, result, ttl_sec)

    def invalidate_table(self, table: str) -> None:
        """Invalidate all cached queries for a table.

        Args:
            table: Table name
        """
        self._table_versions[table] = hashlib.sha256(str(utc_ts()).encode()).hexdigest()
        logger.debug("Invalidated cache for table: %s", table)

    def register_table_change_callback(
        self,
        table: str,
        callback: Callable,
    ) -> None:
        """Register callback for table changes.

        Args:
            table: Table name
            callback: Function to call when table changes
        """
        if table not in self._table_listeners:
            self._table_listeners[table] = []
        self._table_listeners[table].append(callback)

    def notify_table_change(self, table: str) -> None:
        """Notify listeners that table has changed.

        Args:
            table: Table name
        """
        self.invalidate_table(table)

        listeners = self._table_listeners.get(table, [])
        for listener in listeners:
            try:
                listener(table)
            except Exception as exc:
                logger.error("Error in table change callback: %s", exc)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            **self.cache.get_stats(),
            "table_versions": len(self._table_versions),
            "table_listeners": sum(len(v) for v in self._table_listeners.values()),
        }

    def _is_table_stale(self, table: str) -> bool:
        """Check if table cache is stale.

        Args:
            table: Table name

        Returns:
            True if cache is stale, False otherwise
        """
        return table not in self._table_versions

    def _build_key(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None,
    ) -> str:
        """Build cache key from query and parameters.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Hash string for cache key
        """
        normalized = query.strip().lower()
        if params:
            normalized += str(params)
        return hashlib.sha256(normalized.encode()).hexdigest()


class DatabaseOptimizer:
    """Database optimization utilities.

    Provides indexing, query optimization, and caching.
    """

    REQUIRED_INDEXES = [
        ("events", ["ts"]),
        ("plans", ["created_ts", "triggered_by_event_id"]),
        ("results", ["plan_id", "created_ts"]),
        ("schedules", ["run_at", "created_ts"]),
        ("voiceprints", ["label"]),
        ("faceprints", ["label"]),
        ("memories", ["kind", "ts"]),
        ("triggers", ["enabled", "last_fired_ts"]),
        ("scenes", ["name", "enabled"]),
        ("goals", ["status", "created_ts"]),
    ]

    def __init__(self, db_path: str, query_cache: Optional[QueryCache] = None) -> None:
        """Initialize database optimizer.

        Args:
            db_path: Path to SQLite database
            query_cache: Optional query cache instance
        """
        self.db_path = db_path
        self.query_cache = query_cache or QueryCache()

    def optimize_database(self) -> None:
        """Perform database optimization tasks.

        Includes:
        - Creating required indexes
        - Running ANALYZE
        - Running VACUUM
        """
        try:
            self._create_indexes()
            self._analyze_tables()
            self._vacuum_database()
            logger.info("Database optimization completed")
        except Exception as exc:
            logger.error("Database optimization failed: %s", exc)
            raise DatabaseError(str(exc))

    def _create_indexes(self) -> None:
        """Create indexes on frequently queried columns."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            for table, columns in self.REQUIRED_INDEXES:
                for column in columns:
                    index_name = f"idx_{table}_{column}"

                    cursor.execute(
                        f"SELECT name FROM sqlite_master "
                        f"WHERE type='index' AND name='{index_name}'"
                    )
                    if cursor.fetchone():
                        continue

                    try:
                        cursor.execute(
                            f"CREATE INDEX IF NOT EXISTS {index_name} "
                            f"ON {table}({column})"
                        )
                        logger.debug("Created index: %s", index_name)
                    except sqlite3.OperationalError as exc:
                        logger.warning(
                            "Failed to create index %s: %s", index_name, exc
                        )

            conn.commit()
            conn.close()

        except Exception as exc:
            logger.error("Failed to create indexes: %s", exc)
            raise

    def _analyze_tables(self) -> None:
        """Run ANALYZE on all tables."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                cursor.execute(f"ANALYZE {table}")
                logger.debug("Analyzed table: %s", table)

            conn.commit()
            conn.close()

        except Exception as exc:
            logger.error("Failed to analyze tables: %s", exc)
            raise

    def _vacuum_database(self) -> None:
        """Run VACUUM to reclaim space."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("VACUUM")
            conn.commit()
            conn.close()
            logger.debug("Database vacuum completed")
        except Exception as exc:
            logger.warning("Failed to vacuum database: %s", exc)

    def get_query_plan(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Get the query execution plan.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of query plan steps
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            explain_query = f"EXPLAIN QUERY PLAN {query}"
            cursor.execute(explain_query, params or ())

            columns = [desc[0] for desc in cursor.description]
            result = [dict(zip(columns, row)) for row in cursor.fetchall()]

            conn.close()
            return result

        except Exception as exc:
            logger.error("Failed to get query plan: %s", exc)
            return []

    def suggest_indexes(self, min_usage: int = 10) -> List[Dict[str, Any]]:
        """Suggest indexes based on query patterns.

        Args:
            min_usage: Minimum usage count to suggest index

        Returns:
            List of index suggestions
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            )
            existing_indexes = [row[0] for row in cursor.fetchall()]

            cursor.execute(
                "SELECT tbl_name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in cursor.fetchall()]

            suggestions = []

            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]

                for column in columns:
                    index_name = f"idx_{table}_{column}"

                    if index_name in existing_indexes:
                        continue

                    suggestions.append({
                        "table": table,
                        "column": column,
                        "index_name": index_name,
                        "reason": "Potential performance improvement",
                    })

            conn.close()
            return suggestions

        except Exception as exc:
            logger.error("Failed to suggest indexes: %s", exc)
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics.

        Returns:
            Dictionary with database statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT page_count * page_size as size "
                "FROM pragma_page_count(), pragma_page_size()"
            )
            db_size = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
            index_count = cursor.fetchone()[0]

            conn.close()

            return {
                "database_size_bytes": db_size,
                "database_size_mb": db_size / (1024 * 1024),
                "table_count": table_count,
                "index_count": index_count,
                "cache_stats": self.query_cache.get_stats(),
            }

        except Exception as exc:
            logger.error("Failed to get statistics: %s", exc)
            return {}


def create_optimized_database(db_path: str) -> DatabaseOptimizer:
    """Create an optimized database instance.

    Args:
        db_path: Path to SQLite database

    Returns:
        DatabaseOptimizer instance
    """
    optimizer = DatabaseOptimizer(db_path)
    optimizer.optimize_database()
    return optimizer
