from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..core.db_pool import get_connection_pool

logger = logging.getLogger(__name__)


@dataclass
class MemoryChunk:
    chunk_id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)
    source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "embedding_available": self.embedding is not None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
            "source": self.source,
        }


@dataclass
class SearchResult:
    chunk: MemoryChunk
    score: float
    vector_score: Optional[float] = None
    fts_score: Optional[float] = None
    rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk": self.chunk.to_dict(),
            "score": self.score,
            "vector_score": self.vector_score,
            "fts_score": self.fts_score,
            "rank": self.rank,
        }


class VectorSearchManager:
    def __init__(
        self,
        db_path: str = "butler/data/memory_vectors.db",
        embedding_dims: int = 1024,
        enable_fts: bool = True,
        pool_size: int = 3,
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedding_dims = embedding_dims
        self.enable_fts = enable_fts
        self._pool = get_connection_pool(str(db_path), pool_size=pool_size)
        self._lock = threading.Lock()
        self._initialized = False
        self._init_lock = threading.Lock()

    def _initialize_schema(self):
        if self._initialized:
            return
        
        with self._init_lock:
            if self._initialized:
                return
            
            with self._pool.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chunks (
                        chunk_id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        embedding BLOB,
                        metadata TEXT,
                        created_at TEXT,
                        updated_at TEXT,
                        tags TEXT,
                        source TEXT
                    )
                """)

                if self.enable_fts:
                    cursor.execute("""
                        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts 
                        USING fts5(content, metadata, tags, content='chunks', content_rowid='rowid')
                    """)

                    cursor.execute("""
                        CREATE TRIGGER IF NOT EXISTS chunks_fts_insert
                        AFTER INSERT ON chunks
                        BEGIN
                            INSERT INTO chunks_fts(rowid, content, metadata, tags)
                            VALUES (new.rowid, new.content, new.metadata, new.tags);
                        END
                    """)

                    cursor.execute("""
                        CREATE TRIGGER IF NOT EXISTS chunks_fts_update
                        AFTER UPDATE ON chunks
                        BEGIN
                            UPDATE chunks_fts
                            SET content = new.content, metadata = new.metadata, tags = new.tags
                            WHERE rowid = new.rowid;
                        END
                    """)

                    cursor.execute("""
                        CREATE TRIGGER IF NOT EXISTS chunks_fts_delete
                        AFTER DELETE ON chunks
                        BEGIN
                            DELETE FROM chunks_fts WHERE rowid = old.rowid;
                        END
                    """)

                cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON chunks(created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON chunks(source)")

                conn.commit()
                self._initialized = True
                logger.info("Vector search schema initialized")

    def close(self):
        pass

    def _embedding_to_blob(self, embedding: List[float]) -> bytes:
        arr = np.array(embedding, dtype=np.float32)
        return arr.tobytes()

    def _blob_to_embedding(self, blob: bytes) -> List[float]:
        arr = np.frombuffer(blob, dtype=np.float32)
        return arr.tolist()

    def _generate_chunk_id(self, content: str, metadata: Dict[str, Any]) -> str:
        payload = json.dumps({"content": content, "metadata": metadata}, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def add_chunk(
        self,
        content: str,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
    ) -> str:
        self._initialize_schema()
        with self._lock:
            with self._pool.get_connection() as conn:
                cursor = conn.cursor()

                metadata = metadata or {}
                tags = tags or []

                chunk_id = self._generate_chunk_id(content, metadata)

                embedding_blob = None
                if embedding:
                    embedding_blob = self._embedding_to_blob(embedding)

                now = datetime.now().isoformat()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO chunks 
                    (chunk_id, content, embedding, metadata, created_at, updated_at, tags, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        content,
                        embedding_blob,
                        json.dumps(metadata, ensure_ascii=False),
                        now,
                        now,
                        json.dumps(tags, ensure_ascii=False),
                        source,
                    ),
                )

                conn.commit()
                logger.debug(f"Added chunk: {chunk_id}")

                return chunk_id

    def get_chunk(self, chunk_id: str) -> Optional[MemoryChunk]:
        self._initialize_schema()
        with self._lock:
            with self._pool.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,))
                row = cursor.fetchone()

                if row is None:
                    return None

                return self._row_to_chunk(row)

    def _row_to_chunk(self, row: sqlite3.Row) -> MemoryChunk:
        embedding = None
        if row["embedding"]:
            embedding = self._blob_to_embedding(row["embedding"])

        return MemoryChunk(
            chunk_id=row["chunk_id"],
            content=row["content"],
            embedding=embedding,
            metadata=json.loads(row["metadata"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            tags=json.loads(row["tags"]),
            source=row["source"],
        )

    def search_vector(
        self, query_embedding: List[float], limit: int = 10, min_score: float = 0.5
    ) -> List[Tuple[MemoryChunk, float]]:
        if not self.enable_fts:
            return []

        self._initialize_schema()
        with self._lock:
            with self._pool.get_connection() as conn:
                cursor = conn.cursor()

                query_blob = self._embedding_to_blob(query_embedding)

                results = cursor.execute(
                    """
                    SELECT chunk_id, content, embedding, metadata, created_at, updated_at, tags, source,
                           1.0 - (embedding <=> ?) as similarity
                    FROM chunks
                    WHERE embedding IS NOT NULL
                    ORDER BY similarity DESC
                    LIMIT ?
                    """,
                    (query_blob, limit),
                ).fetchall()

                scored_results = []
                for row in results:
                    if row["similarity"] >= min_score:
                        chunk = self._row_to_chunk(row)
                        scored_results.append((chunk, float(row["similarity"])))

                return scored_results

    def search_fts(
        self, query: str, limit: int = 10, min_score: float = 0.0
    ) -> List[Tuple[MemoryChunk, float]]:
        if not self.enable_fts:
            return []

        self._initialize_schema()
        with self._lock:
            with self._pool.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT c.chunk_id, c.content, c.embedding, c.metadata, c.created_at, c.updated_at, c.tags, c.source
                    FROM chunks c
                    WHERE c.chunk_id IN (
                        SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ?
                        LIMIT ?
                    )
                    """,
                    (query, limit),
                )

                results = cursor.fetchall()

                scored_results = []
                for row in results:
                    chunk = self._row_to_chunk(row)
                    scored_results.append((chunk, 1.0))

                return scored_results

    def search_hybrid(
        self,
        query_embedding: Optional[List[float]] = None,
        query_text: Optional[str] = None,
        limit: int = 10,
        vector_weight: float = 0.7,
        fts_weight: float = 0.3,
        min_score: float = 0.3,
    ) -> List[SearchResult]:
        vector_results: Dict[str, Tuple[MemoryChunk, float]] = {}
        fts_results: Dict[str, Tuple[MemoryChunk, float]] = {}

        if query_embedding:
            vector_results = {c.chunk_id: (c, s) for c, s in self.search_vector(query_embedding, limit * 2)}

        if query_text:
            fts_results = {c.chunk_id: (c, s) for c, s in self.search_fts(query_text, limit * 2)}

        all_chunk_ids = set(vector_results.keys()) | set(fts_results.keys())

        merged_results = []
        for chunk_id in all_chunk_ids:
            vector_score = vector_results.get(chunk_id, (None, 0.0))[1]
            fts_score = fts_results.get(chunk_id, (None, 0.0))[1]

            if query_embedding and query_text:
                hybrid_score = vector_weight * vector_score + fts_weight * fts_score
            elif query_embedding:
                hybrid_score = vector_score
            else:
                hybrid_score = fts_score

            if hybrid_score >= min_score:
                chunk = vector_results.get(chunk_id, fts_results.get(chunk_id))[0]
                result = SearchResult(
                    chunk=chunk,
                    score=hybrid_score,
                    vector_score=vector_score if query_embedding else None,
                    fts_score=fts_score if query_text else None,
                )
                merged_results.append(result)

        merged_results.sort(key=lambda r: r.score, reverse=True)
        merged_results = merged_results[:limit]

        for idx, result in enumerate(merged_results):
            result.rank = idx + 1

        return merged_results

    def delete_chunk(self, chunk_id: str) -> bool:
        self._initialize_schema()
        with self._lock:
            with self._pool.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("DELETE FROM chunks WHERE chunk_id = ?", (chunk_id,))
                affected = cursor.rowcount
                conn.commit()

                return affected > 0

    def update_chunk(
        self,
        chunk_id: str,
        content: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        self._initialize_schema()
        with self._lock:
            with self._pool.get_connection() as conn:
                cursor = conn.cursor()

                updates = []
                params = []

                if content is not None:
                    updates.append("content = ?")
                    params.append(content)

                if embedding is not None:
                    updates.append("embedding = ?")
                    params.append(self._embedding_to_blob(embedding))

                if metadata is not None:
                    updates.append("metadata = ?")
                    params.append(json.dumps(metadata, ensure_ascii=False))

                if tags is not None:
                    updates.append("tags = ?")
                    params.append(json.dumps(tags, ensure_ascii=False))

                updates.append("updated_at = ?")
                params.append(datetime.now().isoformat())
                params.append(chunk_id)

                if updates:
                    cursor.execute(
                        f"UPDATE chunks SET {', '.join(updates)} WHERE chunk_id = ?",
                        params,
                    )
                    affected = cursor.rowcount
                    conn.commit()
                    return affected > 0

                return False

    def get_statistics(self) -> Dict[str, Any]:
        self._initialize_schema()
        with self._lock:
            with self._pool.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) as total FROM chunks")
                total = cursor.fetchone()["total"]

                cursor.execute("SELECT COUNT(*) as with_embedding FROM chunks WHERE embedding IS NOT NULL")
                with_embedding = cursor.fetchone()["with_embedding"]

                cursor.execute("SELECT COUNT(*) as chunks FROM chunks")
                chunk_count = cursor.fetchone()["chunks"]

                cursor.execute("SELECT source, COUNT(*) as count FROM chunks GROUP BY source")
                source_stats = {row["source"]: row["count"] for row in cursor.fetchall()}

                return {
                    "total_chunks": total,
                    "chunks_with_embeddings": with_embedding,
                    "coverage": (with_embedding / total * 100) if total > 0 else 0,
                    "source_distribution": source_stats,
                }

    def cleanup_old_chunks(self, days: int = 30) -> int:
        self._initialize_schema()
        with self._lock:
            with self._pool.get_connection() as conn:
                cursor = conn.cursor()

                cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

                cursor.execute("DELETE FROM chunks WHERE created_at < ? AND embedding IS NULL", (cutoff_date,))
                deleted = cursor.rowcount
                conn.commit()

                logger.info(f"Cleaned up {deleted} old chunks")
                return deleted

    def clear_all(self):
        self._initialize_schema()
        with self._lock:
            with self._pool.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("DELETE FROM chunks")
                conn.commit()

                logger.info("Cleared all chunks")
