from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


class MemoryPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class MemoryType(Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    WORKING = "working"


class MemoryAccessLevel(Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    ENCRYPTED = "encrypted"


class MemoryLevel(Enum):
    WORKING = "working"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"


class ConsolidationStrategy(Enum):
    IMPORTANCE_BASED = "importance_based"
    FREQUENCY_BASED = "frequency_based"
    RECENCY_BASED = "recency_based"
    MANUAL = "manual"
    AUTOMATIC = "automatic"


@dataclass
class MemoryItem:
    memory_id: str
    content: Any
    memory_type: str
    access_level: str
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    priority: MemoryPriority = MemoryPriority.NORMAL
    tags: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    expires_at: Optional[datetime] = None
    ttl: Optional[float] = None

    def is_expired(self) -> bool:
        if self.expires_at:
            return datetime.now() > self.expires_at
        if self.ttl:
            return (datetime.now() - self.created_at).total_seconds() > self.ttl
        return False

    def access(self):
        self.last_accessed = datetime.now()
        self.access_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content": self.content if not isinstance(self.content, (bytes, bytearray)) else "<binary>",
            "memory_type": self.memory_type,
            "access_level": self.access_level,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "priority": self.priority.value,
            "tags": self.tags,
            "embedding_available": self.embedding is not None,
            "metadata": self.metadata,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "ttl": self.ttl
        }
