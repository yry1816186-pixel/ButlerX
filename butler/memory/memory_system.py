from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable, Tuple, TYPE_CHECKING
from datetime import datetime, timedelta
import json
from collections import OrderedDict

from .memory_types import MemoryItem, MemoryType, MemoryLevel, MemoryAccessLevel, MemoryPriority, ConsolidationStrategy
from .working_memory import WorkingMemory
from .short_term_memory import ShortTermMemory
from .long_term_memory import LongTermMemory
from .episodic_memory import EpisodicMemory
from .semantic_memory import SemanticMemory
from .procedural_memory import ProceduralMemory
from .memory_query import MemoryQuery, MemoryQueryResult

logger = logging.getLogger(__name__)

class MemorySystem:
    def __init__(
        self,
        working_memory_size: int = 7,
        short_term_capacity: int = 1000,
        short_term_ttl: float = 86400.0,
        storage_path: Optional[str] = None
    ):
        self.working_memory = WorkingMemory(max_size=working_memory_size)
        self.short_term_memory = ShortTermMemory(
            max_capacity=short_term_capacity,
            ttl=short_term_ttl
        )
        self.long_term_memory = LongTermMemory(storage_path=storage_path)
        self.episodic_memory = EpisodicMemory(storage_path=storage_path)
        self.semantic_memory = SemanticMemory(storage_path=storage_path)
        self.procedural_memory = ProceduralMemory(storage_path=storage_path)

        self._memory_listeners: List[Callable] = []
        self._consolidation_interval = 300.0
        self._consolidation_running = False
        self._initialized = False

    async def initialize(self) -> bool:
        try:
            await self.long_term_memory.initialize()
            await self.episodic_memory.initialize()
            await self.semantic_memory.initialize()
            await self.procedural_memory.initialize()

            self._initialized = True
            self._start_consolidation()

            logger.info("Memory system initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize memory system: {e}")
            return False

    async def store(
        self,
        content: Any,
        memory_type: MemoryType,
        access_level: MemoryAccessLevel = MemoryAccessLevel.PRIVATE,
        priority: MemoryPriority = MemoryPriority.NORMAL,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        level: MemoryLevel = MemoryLevel.SHORT_TERM
    ) -> str:
        import uuid

        memory_id = str(uuid.uuid4())
        memory_item = MemoryItem(
            memory_id=memory_id,
            content=content,
            memory_type=memory_type,
            access_level=access_level,
            priority=priority,
            tags=tags or [],
            metadata=metadata or {}
        )

        if level == MemoryLevel.WORKING:
            self.working_memory.add(memory_item)
        elif level == MemoryLevel.SHORT_TERM:
            await self.short_term_memory.add(memory_item)
        elif level == MemoryLevel.LONG_TERM:
            if memory_type == MemoryType.EPISODIC:
                await self.episodic_memory.add(memory_item)
            elif memory_type == MemoryType.SEMANTIC:
                await self.semantic_memory.add(memory_item)
            elif memory_type == MemoryType.PROCEDURAL:
                await self.procedural_memory.add(memory_item)

        self._notify_listeners("store", memory_item)
        return memory_id

    async def retrieve(
        self,
        memory_id: str,
        level: MemoryLevel = None
    ) -> Optional[MemoryItem]:
        if level is None or level == MemoryLevel.WORKING:
            item = self.working_memory.get(memory_id)
            if item:
                item.access()
                return item

        if level is None or level == MemoryLevel.SHORT_TERM:
            item = await self.short_term_memory.get(memory_id)
            if item:
                item.access()
                return item

        if level is None or level == MemoryLevel.LONG_TERM:
            item = await self.long_term_memory.get(memory_id)
            if item:
                item.access()
                return item

        return None

    async def query(
        self,
        query: MemoryQuery,
        max_results: int = 10
    ) -> MemoryQueryResult:
        results = []

        if query.search_working:
            results.extend(self.working_memory.query(query))

        if query.search_short_term:
            results.extend(await self.short_term_memory.query(query))

        if query.search_long_term:
            if query.memory_type is None or query.memory_type == MemoryType.EPISODIC:
                results.extend(await self.episodic_memory.query(query))
            if query.memory_type is None or query.memory_type == MemoryType.SEMANTIC:
                results.extend(await self.semantic_memory.query(query))
            if query.memory_type is None or query.memory_type == MemoryType.PROCEDURAL:
                results.extend(await self.procedural_memory.query(query))

        results.sort(key=lambda r: (r.relevance_score, r.item.priority.value), reverse=True)

        results = results[:max_results]

        for result in results:
            result.item.access()

        return MemoryQueryResult(
            query=query,
            results=results,
            total_found=len(results),
            query_time_ms=0
        )

    async def update(
        self,
        memory_id: str,
        content: Any = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        item = await self.retrieve(memory_id)
        if not item:
            return False

        if content is not None:
            item.content = content
        if tags is not None:
            item.tags = tags
        if metadata is not None:
            item.metadata.update(metadata)

        self._notify_listeners("update", item)
        return True

    async def delete(self, memory_id: str) -> bool:
        success = False

        success = self.working_memory.remove(memory_id) or success
        success = await self.short_term_memory.remove(memory_id) or success
        success = await self.long_term_memory.remove(memory_id) or success
        success = await self.episodic_memory.remove(memory_id) or success
        success = await self.semantic_memory.remove(memory_id) or success
        success = await self.procedural_memory.remove(memory_id) or success

        if success:
            self._notify_listeners("delete", {"memory_id": memory_id})

        return success

    async def consolidate(self):
        logger.info("Starting memory consolidation")

        working_items = self.working_memory.get_all()
        for item in working_items:
            if item.access_count > 3 or item.priority == MemoryPriority.HIGH:
                await self.short_term_memory.add(item)
                self.working_memory.remove(item.memory_id)

        short_term_items = await self.short_term_memory.get_all()
        for item in short_term_items:
            if (datetime.now() - item.created_at).total_seconds() > 3600:
                if item.memory_type == MemoryType.EPISODIC:
                    await self.episodic_memory.add(item)
                elif item.memory_type == MemoryType.SEMANTIC:
                    await self.semantic_memory.add(item)
                elif item.memory_type == MemoryType.PROCEDURAL:
                    await self.procedural_memory.add(item)

                await self.short_term_memory.remove(item.memory_id)

        logger.info("Memory consolidation completed")

    async def clear_level(self, level: MemoryLevel):
        if level == MemoryLevel.WORKING:
            self.working_memory.clear()
        elif level == MemoryLevel.SHORT_TERM:
            await self.short_term_memory.clear()
        elif level == MemoryLevel.LONG_TERM:
            await self.long_term_memory.clear()

    def add_listener(self, listener: Callable):
        if listener not in self._memory_listeners:
            self._memory_listeners.append(listener)

    def remove_listener(self, listener: Callable):
        if listener in self._memory_listeners:
            self._memory_listeners.remove(listener)

    def _notify_listeners(self, event_type: str, data: Any):
        for listener in self._memory_listeners:
            try:
                listener(event_type, data)
            except Exception as e:
                logger.error(f"Memory listener error: {e}")

    def _start_consolidation(self):
        async def consolidation_loop():
            while self._initialized:
                try:
                    await asyncio.sleep(self._consolidation_interval)
                    await self.consolidate()
                except Exception as e:
                    logger.error(f"Memory consolidation error: {e}")

        asyncio.create_task(consolidation_loop())

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "working_memory": {
                "size": len(self.working_memory),
                "max_size": self.working_memory.max_size
            },
            "short_term_memory": {
                "size": len(self.short_term_memory),
                "max_capacity": self.short_term_memory.max_capacity
            },
            "long_term_memory": self.long_term_memory.get_statistics(),
            "episodic_memory": self.episodic_memory.get_statistics(),
            "semantic_memory": self.semantic_memory.get_statistics(),
            "procedural_memory": self.procedural_memory.get_statistics()
        }

    async def shutdown(self):
        self._initialized = False

        await self.long_term_memory.close()
        await self.episodic_memory.close()
        await self.semantic_memory.close()
        await self.procedural_memory.close()

        logger.info("Memory system shutdown")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statistics": self.get_statistics(),
            "initialized": self._initialized,
            "consolidation_interval": self._consolidation_interval
        }
