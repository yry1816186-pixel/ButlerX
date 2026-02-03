from __future__ import annotations
from typing import Any, Dict, List, Optional
from collections import OrderedDict
from datetime import datetime

from .memory_system import MemoryItem, MemoryPriority

class WorkingMemory:
    def __init__(self, max_size: int = 7):
        self._items: OrderedDict[str, MemoryItem] = OrderedDict()
        self.max_size = max_size
        self._context: Dict[str, Any] = {}
        self._focus_stack: List[str] = []

    def add(self, item: MemoryItem):
        if len(self._items) >= self.max_size:
            self._evict_lru()

        self._items[item.memory_id] = item

    def get(self, memory_id: str) -> Optional[MemoryItem]:
        item = self._items.get(memory_id)
        if item:
            self._items.move_to_end(memory_id)
        return item

    def remove(self, memory_id: str) -> bool:
        if memory_id in self._items:
            del self._items[memory_id]
            return True
        return False

    def _evict_lru(self):
        if self._items:
            oldest_key = next(iter(self._items))
            del self._items[oldest_key]

    def query(self, query: Any) -> List[Any]:
        results = []
        for item in self._items.values():
            if not item.is_expired():
                results.append(item)
        return results

    def get_all(self) -> List[MemoryItem]:
        return list(self._items.values())

    def clear(self):
        self._items.clear()
        self._context.clear()
        self._focus_stack.clear()

    def set_context(self, key: str, value: Any):
        self._context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        return self._context.get(key, default)

    def get_all_context(self) -> Dict[str, Any]:
        return self._context.copy()

    def push_focus(self, memory_id: str):
        if memory_id not in self._focus_stack:
            self._focus_stack.append(memory_id)

    def pop_focus(self) -> Optional[str]:
        if self._focus_stack:
            return self._focus_stack.pop()
        return None

    def get_focused_item(self) -> Optional[MemoryItem]:
        if self._focus_stack:
            return self._items.get(self._focus_stack[-1])
        return None

    def get_focus_stack(self) -> List[str]:
        return self._focus_stack.copy()

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, memory_id: str) -> bool:
        return memory_id in self._items
