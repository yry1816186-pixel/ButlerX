from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionMessage:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tokens_used: int = 0
    message_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "tokens_used": self.tokens_used,
            "message_id": self.message_id,
        }


@dataclass
class SessionStats:
    total_messages: int
    total_tokens: int
    total_cost: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        duration = (datetime.now() - self.start_time).total_seconds()
        return {
            "total_messages": self.total_messages,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "duration_seconds": duration,
            "start_time": self.start_time.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }


@dataclass
class Session:
    session_id: str
    user_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    messages: List[SessionMessage] = field(default_factory=list)

    def add_message(self, message: SessionMessage):
        self.messages.append(message)
        self.updated_at = datetime.now()

    def get_messages(
        self, limit: Optional[int] = None, role: Optional[str] = None
    ) -> List[SessionMessage]:
        filtered = self.messages

        if role:
            filtered = [m for m in filtered if m.role == role]

        if limit:
            return filtered[-limit:]

        return filtered

    def get_stats(self) -> SessionStats:
        total_messages = len(self.messages)
        total_tokens = sum(m.tokens_used for m in self.messages)

        return SessionStats(
            total_messages=total_messages,
            total_tokens=total_tokens,
            start_time=self.created_at,
            last_activity=self.updated_at,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "message_count": len(self.messages),
            "stats": self.get_stats().to_dict(),
        }


class SessionManager:
    def __init__(self, db_path: str = "butler/data/sessions.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        self._sessions_cache: Dict[str, Session] = {}

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._initialize_schema()
        return self._conn

    def _initialize_schema(self):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                created_at TEXT,
                updated_at TEXT,
                metadata TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TEXT,
                metadata TEXT,
                tokens_used INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_messages ON messages(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_message_timestamp ON messages(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_user ON sessions(user_id)")

        conn.commit()
        logger.info("Session schema initialized")

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
            self._sessions_cache.clear()
            logger.info("Session manager closed")

    async def create_session(
        self,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Session:
        import uuid

        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO sessions (session_id, user_id, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    user_id,
                    now,
                    now,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )

            conn.commit()

            session = Session(
                session_id=session_id, user_id=user_id, metadata=metadata or {}
            )
            self._sessions_cache[session_id] = session

            logger.info(f"Created session: {session_id}")
            return session

    async def get_session(self, session_id: str, use_cache: bool = True) -> Optional[Session]:
        if use_cache and session_id in self._sessions_cache:
            return self._sessions_cache[session_id]

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            session = self._row_to_session(row)

            cursor.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,),
            )
            message_rows = cursor.fetchall()

            for msg_row in message_rows:
                session.add_message(self._row_to_message(msg_row))

            self._sessions_cache[session_id] = session
            return session

    def _row_to_session(self, row: sqlite3.Row) -> Session:
        return Session(
            session_id=row["session_id"],
            user_id=row["user_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            metadata=json.loads(row["metadata"]),
        )

    def _row_to_message(self, row: sqlite3.Row) -> SessionMessage:
        return SessionMessage(
            role=row["role"],
            content=row["content"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            metadata=json.loads(row["metadata"]),
            tokens_used=row["tokens_used"],
            message_id=row["message_id"],
        )

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens_used: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        import uuid

        message_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO messages (message_id, session_id, role, content, timestamp, metadata, tokens_used)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    session_id,
                    role,
                    content,
                    now,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    tokens_used,
                ),
            )

            cursor.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?", (now, session_id)
            )

            conn.commit()

            if session_id in self._sessions_cache:
                session = self._sessions_cache[session_id]
                session.add_message(
                    SessionMessage(
                        role=role,
                        content=content,
                        metadata=metadata or {},
                        tokens_used=tokens_used,
                        message_id=message_id,
                    )
                )

            logger.debug(f"Added message to session {session_id}: {message_id}")
            return message_id

    async def get_messages(
        self,
        session_id: str,
        limit: Optional[int] = None,
        role: Optional[str] = None,
    ) -> List[SessionMessage]:
        session = await self.get_session(session_id)
        if not session:
            return []

        return session.get_messages(limit=limit, role=role)

    async def get_session_stats(self, session_id: str) -> Optional[SessionStats]:
        session = await self.get_session(session_id)
        if not session:
            return None

        return session.get_stats()

    async def update_session(
        self,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            updates = []
            params = []

            if metadata is not None:
                updates.append("metadata = ?")
                params.append(json.dumps(metadata, ensure_ascii=False))

            if updates:
                set_clause = ", ".join(updates)
                updates.append("updated_at = ?")
                params.append(datetime.now().isoformat())
                params.append(session_id)

                cursor.execute(
                    f"UPDATE sessions SET {set_clause} WHERE session_id = ?",
                    params,
                )
                conn.commit()

                if session_id in self._sessions_cache:
                    if metadata is not None:
                        self._sessions_cache[session_id].metadata = metadata
                    self._sessions_cache[session_id].updated_at = datetime.now()

                return True

            return False

    async def delete_session(self, session_id: str) -> bool:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()

            if session_id in self._sessions_cache:
                del self._sessions_cache[session_id]

            logger.info(f"Deleted session: {session_id}")
            return True

    async def list_sessions(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Session]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = "SELECT * FROM sessions"
            params = []

            if user_id:
                query += " WHERE user_id = ?"
                params.append(user_id)

            query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_session(row) for row in rows]

    async def get_user_sessions(self, user_id: str, limit: int = 50) -> List[Session]:
        return await self.list_sessions(user_id=user_id, limit=limit)

    async def cleanup_old_sessions(self, days: int = 30) -> int:
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT session_id FROM sessions WHERE updated_at < ?", (cutoff_date,)
            )
            old_sessions = [row["session_id"] for row in cursor.fetchall()]

            for session_id in old_sessions:
                await self.delete_session(session_id)

            logger.info(f"Cleaned up {len(old_sessions)} old sessions")
            return len(old_sessions)

    async def search_messages(
        self,
        query: str,
        session_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            if session_id:
                cursor.execute(
                    """
                    SELECT m.*, s.user_id 
                    FROM messages m
                    JOIN sessions s ON m.session_id = s.session_id
                    WHERE m.session_id = ? AND m.content LIKE ?
                    ORDER BY m.timestamp DESC
                    LIMIT ?
                    """,
                    (session_id, f"%{query}%", limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT m.*, s.user_id 
                    FROM messages m
                    JOIN sessions s ON m.session_id = s.session_id
                    WHERE m.content LIKE ?
                    ORDER BY m.timestamp DESC
                    LIMIT ?
                    """,
                    (f"%{query}%", limit),
                )

            rows = cursor.fetchall()
            return [
                {
                    "message": self._row_to_message(row),
                    "session_id": row["session_id"],
                    "user_id": row["user_id"],
                }
                for row in rows
            ]

    async def get_global_stats(self) -> Dict[str, Any]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as total FROM sessions")
            total_sessions = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as total FROM messages")
            total_messages = cursor.fetchone()["total"]

            cursor.execute("SELECT SUM(tokens_used) as total FROM messages")
            total_tokens = cursor.fetchone()["total"] or 0

            cursor.execute(
                "SELECT COUNT(DISTINCT user_id) as total FROM sessions WHERE user_id IS NOT NULL"
            )
            total_users = cursor.fetchone()["total"]

            return {
                "total_sessions": total_sessions,
                "total_messages": total_messages,
                "total_tokens": total_tokens,
                "total_users": total_users,
            }

    def clear_cache(self):
        self._sessions_cache.clear()
        logger.info("Session cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        return {
            "cached_sessions": len(self._sessions_cache),
            "max_cache_size": 1000,
        }


class SessionBuilder:
    @staticmethod
    async def create_conversation(
        session_manager: SessionManager,
        user_id: Optional[str] = None,
        initial_messages: Optional[List[Dict[str, Any]]] = None,
    ) -> Session:
        session = await session_manager.create_session(user_id=user_id)

        if initial_messages:
            for msg in initial_messages:
                await session_manager.add_message(
                    session_id=session.session_id,
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    tokens_used=msg.get("tokens_used", 0),
                    metadata=msg.get("metadata", {}),
                )

        return session

    @staticmethod
    async def continue_conversation(
        session_manager: SessionManager,
        session_id: str,
        user_message: str,
        assistant_response: str,
        user_tokens: int = 0,
        assistant_tokens: int = 0,
    ) -> Tuple[str, str]:
        user_msg_id = await session_manager.add_message(
            session_id=session_id,
            role="user",
            content=user_message,
            tokens_used=user_tokens,
        )

        assistant_msg_id = await session_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=assistant_response,
            tokens_used=assistant_tokens,
        )

        return user_msg_id, assistant_msg_id

    @staticmethod
    async def get_conversation_context(
        session_manager: SessionManager,
        session_id: str,
        max_messages: int = 20,
    ) -> List[Dict[str, Any]]:
        messages = await session_manager.get_messages(session_id, limit=max_messages)
        return [msg.to_dict() for msg in messages]
