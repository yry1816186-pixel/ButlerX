from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import queue
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConnectionPoolConfig:
    db_path: str
    pool_size: int = 5
    max_overflow: int = 10
    timeout: float = 30.0


class SQLiteConnectionPool:
    def __init__(self, config: ConnectionPoolConfig):
        self.config = config
        self._pool: queue.Queue[sqlite3.Connection] = queue.Queue(maxsize=config.pool_size)
        self._overflow: List[sqlite3.Connection] = []
        self._lock = threading.Lock()
        self._created_count = 0
        self._closed = False
        
        Path(config.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        for _ in range(config.pool_size):
            conn = self._create_connection()
            self._pool.put(conn)
    
    def _create_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.config.db_path,
            check_same_thread=False,
            isolation_level=None
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")
        conn.execute("PRAGMA temp_store=MEMORY")
        
        with self._lock:
            self._created_count += 1
        
        return conn
    
    @contextmanager
    def get_connection(self):
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        conn = None
        try:
            try:
                conn = self._pool.get(timeout=self.config.timeout)
            except queue.Empty:
                with self._lock:
                    if len(self._overflow) < self.config.max_overflow:
                        conn = self._create_connection()
                        self._overflow.append(conn)
                    else:
                        conn = self._pool.get(timeout=self.config.timeout)
            
            yield conn
            
        except (sqlite3.Error, queue.Empty, RuntimeError) as e:
            logger.error(f"Error in connection pool: {e}")
            if conn:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
            raise
        finally:
            if conn:
                self._return_connection(conn)
    
    def _return_connection(self, conn: sqlite3.Connection):
        try:
            if conn in self._overflow:
                self._overflow.remove(conn)
                conn.close()
                with self._lock:
                    self._created_count -= 1
            else:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                self._pool.put_nowait(conn)
        except queue.Full:
            conn.close()
            with self._lock:
                self._created_count -= 1
    
    def close_all(self):
        with self._lock:
            self._closed = True
            
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    conn.close()
                except Exception:
                    pass
            
            for conn in self._overflow:
                try:
                    conn.close()
                except Exception:
                    pass
            
            self._overflow.clear()
            self._created_count = 0
        
        logger.info("Connection pool closed")
    
    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "pool_size": self.config.pool_size,
                "max_overflow": self.config.max_overflow,
                "created_connections": self._created_count,
                "available_connections": self._pool.qsize(),
                "overflow_connections": len(self._overflow),
                "closed": self._closed
            }


_global_pool: Optional[SQLiteConnectionPool] = None
_pool_lock = threading.Lock()


def get_connection_pool(db_path: str, pool_size: int = 5) -> SQLiteConnectionPool:
    global _global_pool
    
    with _pool_lock:
        if _global_pool is None or _global_pool.config.db_path != db_path:
            if _global_pool is not None:
                _global_pool.close_all()
            
            config = ConnectionPoolConfig(db_path=db_path, pool_size=pool_size)
            _global_pool = SQLiteConnectionPool(config)
            logger.info(f"Created connection pool for {db_path}")
        
        return _global_pool


def close_global_pool():
    global _global_pool
    
    with _pool_lock:
        if _global_pool is not None:
            _global_pool.close_all()
            _global_pool = None


def with_connection(db_path: str):
    def decorator(func):
        def wrapper(*args, **kwargs):
            pool = get_connection_pool(db_path)
            with pool.get_connection() as conn:
                return func(conn, *args, **kwargs)
        return wrapper
    return decorator
