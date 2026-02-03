from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from .config import ButlerConfig
from .workspace import WorkspaceManager
from .enhanced_session import SessionManager
from ..brain.enhanced_agent import EnhancedAgentRunner, ToolExecutorBase
from ..memory import EnhancedMemorySystem, create_embedding_provider, MemoryIndexConfig
from ..skills import SkillRegistry, SkillContext
from ..brain.planner import BrainPlanner

logger = logging.getLogger(__name__)


class EnhancedButlerIntegration:
    def __init__(self, config: ButlerConfig):
        self.config = config
        self.workspace_manager: Optional[WorkspaceManager] = None
        self.session_manager: Optional[SessionManager] = None
        self.memory_system: Optional[EnhancedMemorySystem] = None
        self.skill_registry: Optional[SkillRegistry] = None
        self.agent_runner: Optional[EnhancedAgentRunner] = None
        self._initialized = False

    async def initialize(self) -> bool:
        try:
            logger.info("Initializing enhanced Butler integration...")

            if self.config.workspace_auto_init:
                await self._initialize_workspace()

            if self.config.memory_enabled:
                await self._initialize_memory()

            await self._initialize_sessions()

            if self.config.skills_enabled:
                await self._initialize_skills()

            await self._initialize_agent()

            self._initialized = True
            logger.info("Enhanced Butler integration initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize enhanced integration: {e}")
            return False

    async def _initialize_workspace(self):
        logger.info("Initializing workspace...")

        self.workspace_manager = WorkspaceManager(
            workspace_dir=self.config.workspace_dir
        )

        status = self.workspace_manager.ensure_workspace()

        if status.get("errors"):
            logger.warning(f"Workspace errors: {status['errors']}")

        logger.info(f"Workspace ready: {self.config.workspace_dir}")

    async def _initialize_memory(self):
        logger.info("Initializing memory system...")

        memory_config = MemoryIndexConfig(
            db_path=self.config.memory_db_path,
            embedding_dims=self.config.memory_embedding_dims,
            enable_fts=self.config.memory_enable_fts,
            chunk_size=self.config.memory_chunk_size,
            chunk_overlap=self.config.memory_chunk_overlap,
            auto_sync=self.config.memory_auto_sync,
            sync_interval_sec=self.config.memory_sync_interval_sec,
        )

        embedding_provider = None
        if self.config.embedding_provider and self.config.embedding_api_key:
            try:
                embedding_provider = await create_embedding_provider(
                    provider_type=self.config.embedding_provider,
                    api_key=self.config.embedding_api_key,
                    model=self.config.embedding_model,
                )
                logger.info(f"Embedding provider: {self.config.embedding_provider}")
            except Exception as e:
                logger.warning(f"Failed to create embedding provider: {e}")

        self.memory_system = EnhancedMemorySystem(
            config=memory_config,
            embedding_provider=embedding_provider,
        )

        await self.memory_system.initialize()

        stats = await self.memory_system.get_stats()
        logger.info(
            f"Memory system ready: {stats.total_chunks} chunks, "
            f"{stats.chunks_with_embeddings} with embeddings"
        )

    async def _initialize_sessions(self):
        logger.info("Initializing session manager...")

        self.session_manager = SessionManager(
            db_path=self.config.session_db_path
        )

        global_stats = await self.session_manager.get_global_stats()
        logger.info(
            f"Session manager ready: {global_stats['total_sessions']} sessions, "
            f"{global_stats['total_messages']} messages"
        )

    async def _initialize_skills(self):
        logger.info("Initializing skill system...")

        self.skill_registry = SkillRegistry()

        from ..skills.builtin import DeviceSkill, NotificationSkill

        await self.skill_registry.initialize_skill(DeviceSkill)
        await self.skill_registry.initialize_skill(NotificationSkill)

        stats = self.skill_registry.get_statistics()
        logger.info(
            f"Skill system ready: {stats['total_skills']} skills, "
            f"{stats['total_commands']} commands"
        )

    async def _initialize_agent(self):
        logger.info("Initializing enhanced agent runner...")

        from ..brain.planner import BrainPlanner, BrainPlannerConfig

        brain_config = BrainPlannerConfig(
            max_actions=self.config.brain_max_actions,
            cache_ttl_sec=self.config.brain_cache_ttl_sec,
            cache_size=self.config.brain_cache_size,
            retry_attempts=self.config.brain_retry_attempts,
        )

        tool_executors: Dict[str, ToolExecutorBase] = {}

        self.agent_runner = EnhancedAgentRunner(
            llm_client=None,
            tool_executors=tool_executors,
            max_context_tokens=self.config.agent_max_context_tokens,
            max_tool_iterations=self.config.agent_max_tool_iterations,
            enable_streaming=self.config.agent_streaming_enabled,
            verbose=False,
        )

        logger.info("Enhanced agent runner ready")

    async def chat(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._initialized:
            return {
                "error": "Integration not initialized",
                "response": "系统未初始化",
            }

        try:
            if not conversation_id:
                session = await self.session_manager.create_session(user_id=user_id)
                conversation_id = session.session_id

            await self.session_manager.add_message(
                session_id=conversation_id,
                role="user",
                content=user_message,
            )

            context_messages = await self.session_manager.get_messages(
                conversation_id, limit=20
            )

            if self.memory_system:
                memory_results = await self.memory_system.search(
                    query_text=user_message, limit=5, min_score=0.3
                )

                if memory_results:
                    context = "\n".join(
                        [r.chunk.content for r in memory_results[:3]]
                    )
                    logger.debug(f"Found {len(memory_results)} relevant memories")

            response = f"我收到了您的消息: {user_message}"

            await self.session_manager.add_message(
                session_id=conversation_id,
                role="assistant",
                content=response,
            )

            return {
                "conversation_id": conversation_id,
                "response": response,
                "tokens_used": 0,
                "memory_results": len(memory_results) if self.memory_system else 0,
            }

        except Exception as e:
            logger.error(f"Chat error: {e}")
            return {
                "error": str(e),
                "response": f"抱歉，处理您的请求时出错: {str(e)}",
                "conversation_id": conversation_id,
            }

    async def add_memory(
        self,
        content: str,
        source: str = "user",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not self.memory_system:
            return None

        chunk_id = await self.memory_system.add_memory(
            content=content,
            metadata=metadata,
            source=source,
        )

        logger.info(f"Added memory: {chunk_id}")
        return chunk_id

    async def search_memory(
        self, query: str, limit: int = 10
    ) -> list:
        if not self.memory_system:
            return []

        results = await self.memory_system.search(
            query_text=query,
            limit=limit,
        )

        return [r.to_dict() for r in results]

    async def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        if not self.session_manager:
            return None

        stats = await self.session_manager.get_session_stats(session_id)
        return stats.to_dict() if stats else None

    async def get_global_stats(self) -> Dict[str, Any]:
        stats = {}

        if self.session_manager:
            stats["sessions"] = await self.session_manager.get_global_stats()

        if self.memory_system:
            memory_stats = await self.memory_system.get_stats()
            stats["memory"] = memory_stats.__dict__

        if self.skill_registry:
            stats["skills"] = self.skill_registry.get_statistics()

        if self.workspace_manager:
            workspace_status = self.workspace_manager.get_workspace_status()
            stats["workspace"] = workspace_status

        return stats

    async def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        results = {}

        if self.session_manager:
            results["sessions"] = await self.session_manager.cleanup_old_sessions(days)

        if self.memory_system:
            results["memories"] = await self.memory_system.cleanup_old_memories(days)

        logger.info(f"Cleaned up old data: {results}")
        return results

    async def shutdown(self):
        logger.info("Shutting down enhanced Butler integration...")

        if self.agent_runner:
            await self.agent_runner.cleanup()

        if self.skill_registry:
            await self.skill_registry.shutdown_all()

        if self.memory_system:
            await self.memory_system.stop()

        if self.session_manager:
            self.session_manager.close()

        logger.info("Enhanced Butler integration shut down")


async def create_enhanced_integration(
    config: ButlerConfig,
) -> EnhancedButlerIntegration:
    integration = EnhancedButlerIntegration(config)
    await integration.initialize()
    return integration
