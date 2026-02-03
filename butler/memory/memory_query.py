from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from .memory_types import MemoryType, MemoryLevel


@dataclass
class MemoryQuery:
    query_type: str
    keywords: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    memory_type: Optional[MemoryType] = None
    memory_level: Optional[MemoryLevel] = None
    min_importance: Optional[int] = None
    limit: int = 10
    offset: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    search_working: bool = True
    search_short_term: bool = True
    search_long_term: bool = True


@dataclass
class MemoryQueryResult:
    query: MemoryQuery
    results: List[Any] = field(default_factory=list)
    total_found: int = 0
    query_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query.__dict__,
            "results": [r.to_dict() if hasattr(r, 'to_dict') else str(r) for r in self.results],
            "total_found": self.total_found,
            "query_time_ms": self.query_time_ms,
            "metadata": self.metadata
        }
