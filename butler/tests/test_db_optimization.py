"""Tests for database optimization."""

import pytest
import tempfile
import os
from ..core.db_optimization import (
    CacheStrategy,
    CacheEntry,
    MemoryCache,
    QueryCache,
    DatabaseOptimizer,
    create_optimized_database,
)


class TestCacheStrategy:
    """Tests for CacheStrategy enum."""

    def test_strategies_exist(self):
        """Test all cache strategies exist."""
        assert hasattr(CacheStrategy, "LRU")
        assert hasattr(CacheStrategy, "LFU")
        assert hasattr(CacheStrategy, "FIFO")
        assert hasattr(CacheStrategy, "TTL")


class TestCacheEntry:
    """Tests for CacheEntry."""

    def test_entry_creation(self):
        """Test creating a cache entry."""
        from ..core.utils import utc_ts
        now = utc_ts()

        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_ts=now,
            last_access_ts=now,
            access_count=0,
        )

        assert entry.key == "test_key"
        assert entry.value == "test_value"

    def test_entry_not_expired_without_ttl(self):
        """Test entry without TTL is not expired."""
        from ..core.utils import utc_ts

        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_ts=utc_ts(),
            last_access_ts=utc_ts(),
            access_count=0,
            ttl_sec=None,
        )

        assert entry.is_expired is False

    def test_entry_expired_with_ttl(self):
        """Test entry with TTL is expired."""
        from ..core.utils import utc_ts

        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_ts=utc_ts() - 100,
            last_access_ts=utc_ts() - 100,
            access_count=0,
            ttl_sec=1.0,
        )

        assert entry.is_expired is True

    def test_entry_access(self):
        """Test recording access to entry."""
        from ..core.utils import utc_ts

        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_ts=utc_ts() - 10,
            last_access_ts=utc_ts() - 10,
            access_count=0,
        )

        entry.access()
        assert entry.access_count == 1
        assert entry.last_access_ts > entry.created_ts


class TestMemoryCache:
    """Tests for MemoryCache."""

    @pytest.fixture
    def cache(self):
        return MemoryCache(max_size=3, strategy=CacheStrategy.LRU)

    def test_cache_initialization(self, cache):
        """Test cache initialization."""
        assert cache.max_size == 3
        assert cache.strategy == CacheStrategy.LRU
        assert len(cache._cache) == 0

    def test_cache_set_and_get(self, cache):
        """Test setting and getting values."""
        cache.set("key1", "value1")
        result = cache.get("key1")

        assert result == "value1"
        assert cache._hits == 1
        assert cache._misses == 0

    def test_cache_miss(self, cache):
        """Test cache miss."""
        result = cache.get("nonexistent")

        assert result is None
        assert cache._hits == 0
        assert cache._misses == 1

    def test_cache_eviction_lru(self, cache):
        """Test LRU eviction."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        cache.get("key1")  # Access key1
        cache.set("key4", "value4")  # Should evict key2

        assert cache.get("key1") == "value1"  # Still in cache
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "value3"  # Still in cache
        assert cache.get("key4") == "value4"  # New value

    def test_cache_clear(self, cache):
        """Test clearing cache."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()

        assert len(cache._cache) == 0
        assert cache._hits == 0
        assert cache._misses == 0

    def test_cache_stats(self, cache):
        """Test cache statistics."""
        cache.set("key1", "value1")
        cache.get("key1")
        cache.get("key2")

        stats = cache.get_stats()

        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5


class TestQueryCache:
    """Tests for QueryCache."""

    @pytest.fixture
    def query_cache(self):
        return QueryCache(default_ttl_sec=60.0)

    def test_query_cache_get_set(self, query_cache):
        """Test caching query results."""
        query = "SELECT * FROM test"
        result = {"id": 1, "name": "test"}

        query_cache.set(query, result=result)
        cached = query_cache.get(query)

        assert cached == result

    def test_query_cache_with_params(self, query_cache):
        """Test caching with parameters."""
        query = "SELECT * FROM test WHERE id = ?"
        params = (1,)
        result = {"id": 1}

        query_cache.set(query, params, result)
        cached = query_cache.get(query, params)

        assert cached == result

    def test_query_cache_invalidate_table(self, query_cache):
        """Test invalidating table cache."""
        query = "SELECT * FROM users"
        query_cache.set(query, result=[{"id": 1}])

        query_cache.invalidate_table("users")
        cached = query_cache.get(query)

        assert cached is None

    def test_query_cache_table_change_notification(self, query_cache):
        """Test table change notification."""
        notifications = []

        def callback(table):
            notifications.append(table)

        query_cache.register_table_change_callback("users", callback)
        query_cache.notify_table_change("users")

        assert "users" in notifications


class TestDatabaseOptimizer:
    """Tests for DatabaseOptimizer."""

    @pytest.fixture
    def db_path(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_optimizer_initialization(self, db_path):
        """Test optimizer initialization."""
        optimizer = DatabaseOptimizer(db_path)
        assert optimizer.db_path == db_path
        assert optimizer.query_cache is not None

    def test_optimize_database(self, db_path):
        """Test database optimization."""
        from ..core.db import Database

        db = Database(db_path)
        db.init_schema()

        optimizer = DatabaseOptimizer(db_path)
        optimizer.optimize_database()

        optimizer.get_statistics()

        db.close()

    def test_create_required_indexes(self, db_path):
        """Test creating required indexes."""
        from ..core.db import Database

        db = Database(db_path)
        db.init_schema()

        optimizer = DatabaseOptimizer(db_path)
        optimizer._create_indexes()

        conn = optimizer._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_events_ts'"
        )
        index_exists = cursor.fetchone() is not None

        conn.close()

        assert index_exists

    def test_suggest_indexes(self, db_path):
        """Test index suggestions."""
        from ..core.db import Database

        db = Database(db_path)
        db.init_schema()

        optimizer = DatabaseOptimizer(db_path)
        suggestions = optimizer.suggest_indexes()

        assert isinstance(suggestions, list)

        db.close()

    def test_get_statistics(self, db_path):
        """Test getting database statistics."""
        from ..core.db import Database

        db = Database(db_path)
        db.init_schema()

        optimizer = DatabaseOptimizer(db_path)
        stats = optimizer.get_statistics()

        assert "database_size_bytes" in stats
        assert "table_count" in stats
        assert "cache_stats" in stats

        db.close()


class TestCreateOptimizedDatabase:
    """Tests for create_optimized_database function."""

    @pytest.fixture
    def db_path(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_create_optimized_database(self, db_path):
        """Test creating optimized database."""
        optimizer = create_optimized_database(db_path)

        assert optimizer is not None
        assert isinstance(optimizer, DatabaseOptimizer)

        stats = optimizer.get_statistics()
        assert stats["table_count"] > 0
