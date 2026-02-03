from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .embeddings import (
    EmbeddingProvider,
    EmbeddingResult,
    create_embedding_provider,
)
from .vector_search import MemoryChunk, SearchResult, VectorSearchManager

logger = logging.getLogger(__name__)


@dataclass
class MemoryIndexConfig:
    db_path: str = "butler/data/memory_vectors.db"
    embedding_dims: int = 1024
    enable_fts: bool = True
    chunk_size: int = 500
    chunk_overlap: int = 50
    auto_sync: bool = True
    sync_interval_sec: int = 60


@dataclass
class MemoryIndexStats:
    total_chunks: int
    chunks_with_embeddings: int
    coverage: float
    last_sync: Optional[datetime] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None


class EnhancedMemorySystem:
    def __init__(
        self,
        config: Optional[MemoryIndexConfig] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ):
        self.config = config or MemoryIndexConfig()
        self.vector_search = VectorSearchManager(
            db_path=self.config.db_path,
            embedding_dims=self.config.embedding_dims,
            enable_fts=self.config.enable_fts,
        )
        self.embedding_provider = embedding_provider

        self._sync_running = False
        self._last_sync: Optional[datetime] = None
        self._pending_sync = set()

    async def initialize(self) -> bool:
        try:
            logger.info("Initializing enhanced memory system...")

            if self.embedding_provider is None:
                logger.warning("No embedding provider configured, vector search disabled")
            else:
                model_info = self.embedding_provider.get_model_info()
                logger.info(
                    f"Embedding provider: {self.embedding_provider.__class__.__name__}, "
                    f"dims: {model_info.get('dims')}"
                )

            if self.config.auto_sync:
                self._start_sync_loop()

            logger.info("Enhanced memory system initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize enhanced memory: {e}")
            return False

    def _start_sync_loop(self):
        async def sync_loop():
            while self._sync_running:
                try:
                    await self.sync_embeddings()
                    await asyncio.sleep(self.config.sync_interval_sec)
                except Exception as e:
                    logger.error(f"Sync loop error: {e}")
                    await asyncio.sleep(10)

        self._sync_running = True
        asyncio.create_task(sync_loop())

    async def stop(self):
        self._sync_running = False
        self.vector_search.close()

        if self.embedding_provider:
            await self.embedding_provider.close()

        logger.info("Enhanced memory system stopped")

    async def add_memory(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
        embed: bool = True,
    ) -> str:
        chunks = await self._chunk_content(content)

        chunk_ids = []
        for i, chunk_content in enumerate(chunks):
            chunk_metadata = metadata.copy() if metadata else {}
            chunk_metadata.update(
                {
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }
            )

            embedding = None
            if embed and self.embedding_provider:
                try:
                    result = await self.embedding_provider.embed([chunk_content])
                    if result:
                        embedding = result[0].embedding
                except Exception as e:
                    logger.warning(f"Failed to embed chunk {i}: {e}")

            chunk_id = self.vector_search.add_chunk(
                content=chunk_content,
                embedding=embedding,
                metadata=chunk_metadata,
                tags=tags,
                source=source,
            )
            chunk_ids.append(chunk_id)

        return chunk_ids[0] if chunk_ids else None

    async def _chunk_content(self, content: str) -> List[str]:
        chunks = []
        start = 0
        content_length = len(content)

        while start < content_length:
            end = start + self.config.chunk_size

            if end >= content_length:
                chunks.append(content[start:])
                break

            last_space = content.rfind(" ", start, end)
            last_newline = content.rfind("\n", start, end)
            break_point = max(last_space, last_newline)

            if break_point > start:
                end = break_point + 1

            chunks.append(content[start:end])
            start = end - self.config.chunk_overlap

        return [c.strip() for c in chunks if c.strip()]

    async def search(
        self,
        query_text: Optional[str] = None,
        query_embedding: Optional[List[float]] = None,
        limit: int = 10,
        min_score: float = 0.3,
        vector_weight: float = 0.7,
        fts_weight: float = 0.3,
    ) -> List[SearchResult]:
        if not query_text and not query_embedding:
            logger.warning("Search requires either query_text or query_embedding")
            return []

        if query_embedding is None and self.embedding_provider and query_text:
            try:
                result = await self.embedding_provider.embed([query_text])
                if result:
                    query_embedding = result[0].embedding
            except Exception as e:
                logger.warning(f"Failed to embed query: {e}")

        results = self.vector_search.search_hybrid(
            query_embedding=query_embedding,
            query_text=query_text,
            limit=limit,
            vector_weight=vector_weight,
            fts_weight=fts_weight,
            min_score=min_score,
        )

        logger.debug(f"Found {len(results)} results for query: {query_text[:50] if query_text else ''}")
        return results

    async def get_memory(self, chunk_id: str) -> Optional[MemoryChunk]:
        return self.vector_search.get_chunk(chunk_id)

    async def update_memory(
        self,
        chunk_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        reembed: bool = False,
    ) -> bool:
        embedding = None
        if reembed and content and self.embedding_provider:
            try:
                result = await self.embedding_provider.embed([content])
                if result:
                    embedding = result[0].embedding
            except Exception as e:
                logger.warning(f"Failed to re-embed: {e}")

        return self.vector_search.update_chunk(
            chunk_id=chunk_id,
            content=content,
            embedding=embedding,
            metadata=metadata,
            tags=tags,
        )

    async def delete_memory(self, chunk_id: str) -> bool:
        return self.vector_search.delete_chunk(chunk_id)

    async def sync_embeddings(
        self, chunk_ids: Optional[List[str]] = None, force: bool = False
    ) -> int:
        if not self.embedding_provider:
            return 0

        if chunk_ids:
            chunks_to_sync = chunk_ids
        else:
            stats = self.vector_search.get_statistics()
            without_embeddings = stats["total_chunks"] - stats["chunks_with_embeddings"]
            if without_embeddings == 0 and not force:
                return 0

            with self.vector_search._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT chunk_id, content FROM chunks WHERE embedding IS NULL LIMIT 100"
                )
                rows = cursor.fetchall()
                chunks_to_sync = [(row["chunk_id"], row["content"]) for row in rows]

        if not chunks_to_sync:
            return 0

        logger.info(f"Syncing embeddings for {len(chunks_to_sync)} chunks")

        texts = [content for _, content in chunks_to_sync]
        results = await self.embedding_provider.embed_batch(texts, batch_size=32)

        synced = 0
        for (chunk_id, _), result in zip(chunks_to_sync, results):
            if result.embedding:
                self.vector_search.update_chunk(chunk_id, embedding=result.embedding)
                synced += 1

        self._last_sync = datetime.now()
        logger.info(f"Synced {synced} embeddings")
        return synced

    async def get_stats(self) -> MemoryIndexStats:
        stats = self.vector_search.get_statistics()

        return MemoryIndexStats(
            total_chunks=stats["total_chunks"],
            chunks_with_embeddings=stats["chunks_with_embeddings"],
            coverage=stats["coverage"],
            last_sync=self._last_sync,
            embedding_provider=self.embedding_provider.__class__.__name__
            if self.embedding_provider
            else None,
            embedding_model=self.embedding_provider.get_model_info()
            if self.embedding_provider
            else None,
        )

    async def cleanup_old_memories(self, days: int = 30) -> int:
        return self.vector_search.cleanup_old_chunks(days=days)

    async def import_from_text(
        self,
        text: str,
        source: str = "import",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        lines = text.split("\n")
        paragraphs = []

        current_paragraph = []
        for line in lines:
            line = line.strip()
            if line:
                current_paragraph.append(line)
            elif current_paragraph:
                paragraphs.append(" ".join(current_paragraph))
                current_paragraph = []

        if current_paragraph:
            paragraphs.append(" ".join(current_paragraph))

        chunk_ids = []
        for paragraph in paragraphs:
            if len(paragraph) > 50:
                chunk_id = await self.add_memory(
                    content=paragraph, source=source, metadata=metadata
                )
                if chunk_id:
                    chunk_ids.append(chunk_id)

        logger.info(f"Imported {len(chunk_ids)} paragraphs from {source}")
        return chunk_ids

    async def export_to_text(self, source: Optional[str] = None) -> str:
        with self.vector_search._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT content, metadata FROM chunks"
            params = []
            if source:
                query += " WHERE source = ?"
                params.append(source)

            query += " ORDER BY created_at ASC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            lines = []
            for row in rows:
                content = row["content"]
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                lines.append(f"# {metadata.get('source', 'memory')}\n{content}\n")

            return "\n".join(lines)

    async def find_similar_memories(
        self, chunk_id: str, limit: int = 5
    ) -> List[SearchResult]:
        chunk = await self.get_memory(chunk_id)
        if not chunk or not chunk.embedding:
            return []

        results = self.vector_search.search_vector(
            query_embedding=chunk.embedding, limit=limit + 1, min_score=0.5
        )

        filtered_results = [
            SearchResult(chunk=c, score=s)
            for c, s in results
            if c.chunk_id != chunk_id
        ][:limit]

        return filtered_results
