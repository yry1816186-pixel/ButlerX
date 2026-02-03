from __future__ import annotations
import asyncio
import logging
import json
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

from .memory_types import MemoryItem

logger = logging.getLogger(__name__)

class LongTermMemory:
    def __init__(self, storage_path: Optional[str] = None):
        self._items: Dict[str, MemoryItem] = {}
        self._storage_path = storage_path or "./data/memory"
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> bool:
        try:
            os.makedirs(self._storage_path, exist_ok=True)

            metadata_file = os.path.join(self._storage_path, "metadata.json")
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item_data in data.get("items", []):
                        item = self._deserialize_item(item_data)
                        if item:
                            self._items[item.memory_id] = item

            self._initialized = True
            logger.info(f"Long term memory initialized with {len(self._items)} items")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize long term memory: {e}")
            return False

    async def add(self, item: MemoryItem):
        async with self._lock:
            self._items[item.memory_id] = item
            await self._save_metadata()

    async def get(self, memory_id: str) -> Optional[MemoryItem]:
        async with self._lock:
            item = self._items.get(memory_id)
            if item:
                if item.is_expired():
                    del self._items[memory_id]
                    return None
            return item

    async def remove(self, memory_id: str) -> bool:
        async with self._lock:
            if memory_id in self._items:
                del self._items[memory_id]
                await self._save_metadata()
                return True
            return False

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
            await self._save_metadata()

    async def close(self):
        await self._save_metadata()
        self._initialized = False

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_items": len(self._items),
            "storage_path": self._storage_path,
            "initialized": self._initialized
        }

    async def _save_metadata(self):
        try:
            metadata_file = os.path.join(self._storage_path, "metadata.json")
            data = {
                "items": [self._serialize_item(item) for item in self._items.values()],
                "saved_at": datetime.now().isoformat()
            }

            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def _serialize_item(self, item: MemoryItem) -> Dict[str, Any]:
        return {
            "memory_id": item.memory_id,
            "content": item.content,
            "memory_type": item.memory_type.value,
            "access_level": item.access_level.value,
            "created_at": item.created_at.isoformat(),
            "last_accessed": item.last_accessed.isoformat(),
            "access_count": item.access_count,
            "priority": item.priority.value,
            "tags": item.tags,
            "embedding": item.embedding,
            "metadata": item.metadata,
            "expires_at": item.expires_at.isoformat() if item.expires_at else None,
            "ttl": item.ttl
        }

    def _deserialize_item(self, data: Dict[str, Any]) -> Optional[MemoryItem]:
        try:
            from .memory_system import MemoryType, MemoryAccessLevel, MemoryPriority

            return MemoryItem(
                memory_id=data["memory_id"],
                content=data["content"],
                memory_type=MemoryType(data["memory_type"]),
                access_level=MemoryAccessLevel(data["access_level"]),
                created_at=datetime.fromisoformat(data["created_at"]),
                last_accessed=datetime.fromisoformat(data["last_accessed"]),
                access_count=data["access_count"],
                priority=MemoryPriority(data["priority"]),
                tags=data.get("tags", []),
                embedding=data.get("embedding"),
                metadata=data.get("metadata", {}),
                expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
                ttl=data.get("ttl")
            )
        except Exception as e:
            logger.error(f"Failed to deserialize memory item: {e}")
            return None
