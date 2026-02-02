from __future__ import annotations

import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DialogueMessage:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ConversationContext:
    conversation_id: str
    user_id: Optional[str] = None
    messages: deque[DialogueMessage] = field(default_factory=lambda: deque(maxlen=20))
    current_room: Optional[str] = None
    last_device: Optional[str] = None
    last_action: Optional[Dict[str, Any]] = None
    active_intent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        message = DialogueMessage(
            role=role,
            content=content,
            timestamp=time.time(),
            metadata=metadata or {}
        )
        self.messages.append(message)
        self.last_activity = time.time()
        logger.debug(f"Added {role} message to conversation {self.conversation_id}")

    def get_recent_messages(self, count: int = 5) -> List[DialogueMessage]:
        return list(self.messages)[-count:]

    def get_context_summary(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "message_count": len(self.messages),
            "current_room": self.current_room,
            "last_device": self.last_device,
            "last_action": self.last_action,
            "active_intent": self.active_intent,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "age_seconds": time.time() - self.created_at,
            "idle_seconds": time.time() - self.last_activity,
        }

    def update_context(self, updates: Dict[str, Any]) -> None:
        if "current_room" in updates:
            self.current_room = updates["current_room"]
        if "last_device" in updates:
            self.last_device = updates["last_device"]
        if "last_action" in updates:
            self.last_action = updates["last_action"]
        if "active_intent" in updates:
            self.active_intent = updates["active_intent"]
        if "metadata" in updates:
            self.metadata.update(updates["metadata"])
        self.last_activity = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "current_room": self.current_room,
            "last_device": self.last_device,
            "last_action": self.last_action,
            "active_intent": self.active_intent,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
        }

    def is_stale(self, max_idle_seconds: int = 3600) -> bool:
        return (time.time() - self.last_activity) > max_idle_seconds


class ContextManager:
    def __init__(self, max_contexts: int = 100) -> None:
        self.contexts: Dict[str, ConversationContext] = {}
        self.user_contexts: Dict[str, str] = {}
        self.max_contexts = max_contexts

    def create_context(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> ConversationContext:
        import uuid
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        context = ConversationContext(conversation_id=conversation_id, user_id=user_id)
        self.contexts[conversation_id] = context
        
        if user_id:
            self.user_contexts[user_id] = conversation_id
        
        logger.info(f"Created context {conversation_id} for user {user_id}")
        return context

    def get_context(self, conversation_id: str) -> Optional[ConversationContext]:
        return self.contexts.get(conversation_id)

    def get_user_context(self, user_id: str) -> Optional[ConversationContext]:
        conversation_id = self.user_contexts.get(user_id)
        if conversation_id:
            return self.get_context(conversation_id)
        return None

    def get_or_create_context(
        self,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> ConversationContext:
        if user_id:
            context = self.get_user_context(user_id)
            if context and not context.is_stale():
                return context
        
        if conversation_id:
            context = self.get_context(conversation_id)
            if context:
                return context
        
        return self.create_context(conversation_id, user_id)

    def update_context(
        self,
        conversation_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        context = self.contexts.get(conversation_id)
        if not context:
            return False
        context.update_context(updates)
        return True

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        context = self.contexts.get(conversation_id)
        if not context:
            return False
        context.add_message(role, content, metadata)
        return True

    def cleanup_stale_contexts(self, max_idle_seconds: int = 3600) -> int:
        stale_ids = [
            ctx_id for ctx_id, ctx in self.contexts.items()
            if ctx.is_stale(max_idle_seconds)
        ]
        for ctx_id in stale_ids:
            context = self.contexts.pop(ctx_id)
            if context.user_id and self.user_contexts.get(context.user_id) == ctx_id:
                del self.user_contexts[context.user_id]
        logger.info(f"Cleaned up {len(stale_ids)} stale contexts")
        return len(stale_ids)

    def get_context_for_llm(
        self,
        conversation_id: str,
        max_messages: int = 10
    ) -> List[Dict[str, Any]]:
        context = self.contexts.get(conversation_id)
        if not context:
            return []
        
        messages = context.get_recent_messages(max_messages)
        return [msg.to_dict() for msg in messages]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_count": len(self.contexts),
            "user_context_count": len(self.user_contexts),
            "contexts": [ctx.to_dict() for ctx in self.contexts.values()],
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Context manager saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "ContextManager":
        manager = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for ctx_data in data.get("contexts", []):
            messages = deque(
                [
                    DialogueMessage(
                        role=msg["role"],
                        content=msg["content"],
                        timestamp=msg.get("timestamp", time.time()),
                        metadata=msg.get("metadata", {})
                    )
                    for msg in ctx_data.get("messages", [])
                ],
                maxlen=20
            )
            
            context = ConversationContext(
                conversation_id=ctx_data["conversation_id"],
                user_id=ctx_data.get("user_id"),
                messages=messages,
                current_room=ctx_data.get("current_room"),
                last_device=ctx_data.get("last_device"),
                last_action=ctx_data.get("last_action"),
                active_intent=ctx_data.get("active_intent"),
                metadata=ctx_data.get("metadata", {}),
                created_at=ctx_data.get("created_at", time.time()),
                last_activity=ctx_data.get("last_activity", time.time()),
            )
            manager.contexts[context.conversation_id] = context
            
            if context.user_id:
                manager.user_contexts[context.user_id] = context.conversation_id
        
        logger.info(f"Context manager loaded from {filepath}")
        return manager
