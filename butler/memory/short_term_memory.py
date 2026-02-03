from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict, List, Optional
from collections import OrderedDict
from datetime import datetime, timedelta

from .memory_system import MemoryItem

logger = logging.getLogger(__name__)

class ShortTermMemory:
    def __init__(self, max_capacity: int = 1000, ttl: float = 86400.0):
        self._items: OrderedDict[str, MemoryItem] = OrderedDict()
        self.max_capacity = max_capacity
        self.ttl = ttl
        self._lock = asyncio.Lock()

    async def add(self, item: MemoryItem):
        async with self._lock:
            if item.ttl is None:
                item.ttl = self.ttl

            if len(self._items) >= self.max_capacity:
                await self._evict_expired()
                if len(self._items) >= self.max_capacity:
                    await self._evict_lru()

            self._items[item.memory_id] = item

    async def get(self, memory_id: str) -> Optional[MemoryItem]:
        async with self._lock:
            item = self._items.get(memory_id)
            if item:
                if item.is_expired():
                    del self._items[memory_id]
                    return None
                self._items.move_to_end(memory_id)
            return item

    async def remove(self, memory_id: str) -> bool:
        async with self._lock:
            if memory_id in self._items:
                del self._items[memory_id]
                return True
            return False

    async def _evict_expired(self):
        now = datetime.now()
        expired_keys = [
            key for key, item in self._items.items()
            if item.is_expired()
        ]
        for key in expired_keys:
            del self._items[key]

    async def _evict_lru(self):
        if self._items:
            oldest_key = next(iter(self._items))
            del self._items[oldest_key]

    async def query(self, query: Any) -> List[Any]:
        async with self._lock:
            results = []
            for item in self._items.values():
                if not item.is_expired():
                    results.append(item)
            return results

    async def get_all(self) -> List[MemoryItem]:
        async with self._lock:
            return list(self._items.values())

    async def clear(self):
        async with self._lock:
            self._items.clear()

    async def cleanup(self):
        async with self._lock:
            await self._evict_expired()

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, memory_id: str) -> bool:
        return memory_id in self._items
