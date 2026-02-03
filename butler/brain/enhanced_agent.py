from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, AsyncIterator

from ..automation.action import Action
from ..core.models import ActionPlan
from ..core.utils import new_uuid, utc_ts

logger = logging.getLogger(__name__)


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    RUNNING_TOOLS = "running_tools"
    GENERATING_RESPONSE = "generating_response"
    ERROR = "error"


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time_ms: float = 0
    tokens_used: int = 0


@dataclass
class AgentContext:
    conversation_id: str
    user_message: str
    history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    state: AgentState = AgentState.IDLE
    started_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "user_message": self.user_message,
            "history_length": len(self.history),
            "metadata": self.metadata,
            "state": self.state.value,
            "started_at": self.started_at.isoformat(),
        }


@dataclass
class StreamingChunk:
    content: str
    is_final: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolExecutor(ABC):
    @abstractmethod
    async def execute(self, action: Action, context: AgentContext) -> ToolResult:
        pass

    @abstractmethod
    def get_tool_spec(self) -> Dict[str, Any]:
        pass


class EnhancedAgentRunner:
    def __init__(
        self,
        llm_client,
        tool_executors: Dict[str, ToolExecutor],
        max_context_tokens: int = 8192,
        max_tool_iterations: int = 5,
        enable_streaming: bool = True,
        verbose: bool = False,
    ):
        self.llm_client = llm_client
        self.tool_executors = tool_executors
        self.max_context_tokens = max_context_tokens
        self.max_tool_iterations = max_tool_iterations
        self.enable_streaming = enable_streaming
        self.verbose = verbose

        self._active_contexts: Dict[str, AgentContext] = {}
        self._tool_output_listeners: List[Callable] = []
        self._stream_listeners: List[Callable] = []

    def add_tool_output_listener(self, listener: Callable[[ToolResult], None]):
        if listener not in self._tool_output_listeners:
            self._tool_output_listeners.append(listener)

    def add_stream_listener(self, listener: Callable[[StreamingChunk], None]):
        if listener not in self._stream_listeners:
            self._stream_listeners.append(listener)

    def remove_tool_output_listener(self, listener: Callable):
        if listener in self._tool_output_listeners:
            self._tool_output_listeners.remove(listener)

    def remove_stream_listener(self, listener: Callable):
        if listener in self._stream_listeners:
            self._stream_listeners.remove(listener)

    async def run(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        conversation_id = conversation_id or new_uuid()
        history = history or []
        metadata = metadata or {}

        context = AgentContext(
            conversation_id=conversation_id,
            user_message=user_message,
            history=history,
            metadata=metadata,
            state=AgentState.THINKING,
        )

        self._active_contexts[conversation_id] = context

        try:
            result = await self._run_with_tools(context)

            context.state = AgentState.IDLE
            return {
                "conversation_id": conversation_id,
                "response": result["response"],
                "actions": result.get("actions", []),
                "tool_results": result.get("tool_results", []),
                "tokens_used": result.get("tokens_used", 0),
                "execution_time_ms": result.get("execution_time_ms", 0),
            }

        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            context.state = AgentState.ERROR
            return {
                "conversation_id": conversation_id,
                "response": f"抱歉，处理您的请求时出错: {str(e)}",
                "error": str(e),
            }

        finally:
            if conversation_id in self._active_contexts:
                del self._active_contexts[conversation_id]

    async def _run_with_tools(
        self, context: AgentContext
    ) -> Dict[str, Any]:
        start_time = datetime.now()
        total_tokens = 0
        all_tool_results = []
        all_actions = []

        current_history = context.history.copy()
        current_history.append({"role": "user", "content": context.user_message})

        for iteration in range(self.max_tool_iterations):
            context.state = AgentState.THINKING

            messages = self._build_messages(
                current_history, all_tool_results, context.metadata
            )

            if self.verbose:
                logger.debug(f"Iteration {iteration + 1}: {len(messages)} messages")

            if self.enable_streaming:
                response, tokens = await self._stream_llm_response(messages, context)
            else:
                response, tokens = await self._call_llm(messages)

            total_tokens += tokens

            current_history.append({"role": "assistant", "content": response})

            actions = self._extract_actions(response)

            if not actions:
                if self.verbose:
                    logger.debug("No more actions needed")
                break

            context.state = AgentState.RUNNING_TOOLS

            for action in actions:
                if action.action_type not in self.tool_executors:
                    logger.warning(f"Unknown action type: {action.action_type}")
                    continue

                executor = self.tool_executors[action.action_type]
                tool_result = await executor.execute(action, context)

                all_tool_results.append(tool_result)
                all_actions.append(action)

                for listener in self._tool_output_listeners:
                    try:
                        listener(tool_result)
                    except Exception as e:
                        logger.error(f"Tool output listener error: {e}")

                current_history.append(
                    {
                        "role": "tool",
                        "content": str(tool_result.output),
                        "tool_name": action.action_type,
                        "success": tool_result.success,
                    }
                )

                if self.verbose:
                    logger.info(
                        f"Tool {action.action_type}: "
                        f"{'success' if tool_result.success else 'failed'}, "
                        f"{tool_result.execution_time_ms:.0f}ms"
                    )

        final_response = current_history[-1]["content"] if current_history else ""

        execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        return {
            "response": final_response,
            "actions": all_actions,
            "tool_results": all_tool_results,
            "tokens_used": total_tokens,
            "execution_time_ms": execution_time_ms,
        }

    def _build_messages(
        self,
        history: List[Dict[str, Any]],
        tool_results: List[ToolResult],
        metadata: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        messages = []

        system_prompt = self._build_system_prompt(metadata)
        messages.append({"role": "system", "content": system_prompt})

        token_count = len(system_prompt) // 4

        for msg in history:
            if token_count >= self.max_context_tokens:
                break

            messages.append(
                {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                }
            )
            token_count += len(msg.get("content", "")) // 4

        if token_count > self.max_context_tokens:
            logger.warning(
                f"Context exceeds limit: {token_count} > {self.max_context_tokens}"
            )

        return messages

    def _build_system_prompt(self, metadata: Dict[str, Any]) -> str:
        tools_desc = self._build_tools_description()

        base_prompt = """你是一个智能家居管家助手，名字叫"小管家"。

你的职责：
1. 理解用户的自然语言指令
2. 根据需要调用工具完成任务
3. 提供友好、自然的回复
4. 记住对话上下文，支持连续对话

可用工具：
"""

        return base_prompt + tools_desc + """

回复格式：
- 直接对话：自然语言回复
- 调用工具：在回复中包含工具调用，格式为 TOOL: {"action_type": "...", "params": {...}}
- 多个工具调用：可以包含多个 TOOL: 标记

示例：
用户："打开客厅灯"
助手：TOOL: {"action_type": "device_turn_on", "params": {"device_id": "light_living_room"}}

用户："现在几点了？"
助手：现在是 14:30。

请用中文回复，语气亲切自然。"""

    def _build_tools_description(self) -> str:
        descriptions = []

        for tool_name, executor in self.tool_executors.items():
            spec = executor.get_tool_spec()
            desc = f"- {tool_name}: {spec.get('description', '')}\n"
            if "params" in spec:
                desc += f"  参数: {spec['params']}\n"
            descriptions.append(desc)

        return "\n".join(descriptions) if descriptions else "无可用工具"

    async def _call_llm(
        self, messages: List[Dict[str, Any]]
    ) -> Tuple[str, int]:
        try:
            text, raw = self.llm_client.chat(messages=messages)
            tokens = raw.get("usage", {}).get("total_tokens", len(text) // 4)
            return text, tokens

        except Exception as e:
            logger.error(f"LLM call error: {e}")
            raise ValueError(f"Failed to call LLM: {e}") from e

    async def _stream_llm_response(
        self, messages: List[Dict[str, Any]], context: AgentContext
    ) -> Tuple[str, int]:
        context.state = AgentState.GENERATING_RESPONSE

        full_response = ""
        tokens_estimated = 0

        try:
            response, raw = await self._call_llm(messages)
            full_response = response
            tokens_estimated = raw.get("usage", {}).get("total_tokens", len(response) // 4)

            if self.enable_streaming:
                chunk_size = 20
                for i in range(0, len(response), chunk_size):
                    chunk = response[i : i + chunk_size]
                    is_final = i + chunk_size >= len(response)

                    streaming_chunk = StreamingChunk(
                        content=chunk, is_final=is_final
                    )

                    for listener in self._stream_listeners:
                        try:
                            listener(streaming_chunk)
                        except Exception as e:
                            logger.error(f"Stream listener error: {e}")

                    if i % (chunk_size * 3) == 0:
                        await asyncio.sleep(0.01)

            return full_response, tokens_estimated

        except Exception as e:
            logger.error(f"Streaming response error: {e}")
            raise

    def _extract_actions(self, response: str) -> List[Action]:
        import re
        import json

        actions = []

        pattern = r'TOOL:\s*(\{.*?\})'
        matches = re.findall(pattern, response, re.DOTALL)

        for match in matches:
            try:
                action_data = json.loads(match)
                if "action_type" in action_data:
                    actions.append(
                        Action(
                            action_id=new_uuid(),
                            action_type=action_data["action_type"],
                            params=action_data.get("params", {}),
                        )
                    )
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse action: {match}")

        return actions

    async def run_streaming(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[StreamingChunk]:
        conversation_id = conversation_id or new_uuid()
        history = history or []

        context = AgentContext(
            conversation_id=conversation_id,
            user_message=user_message,
            history=history,
            state=AgentState.THINKING,
        )

        self._active_contexts[conversation_id] = context

        try:
            messages = self._build_messages(history, [], {})
            response, _ = await self._call_llm(messages)

            chunk_size = 30
            for i in range(0, len(response), chunk_size):
                chunk = response[i : i + chunk_size]
                is_final = i + chunk_size >= len(response)

                yield StreamingChunk(content=chunk, is_final=is_final)

                if i % (chunk_size * 2) == 0:
                    await asyncio.sleep(0.01)

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield StreamingChunk(
                content=f"\n[错误: {str(e)}]", is_final=True
            )

        finally:
            if conversation_id in self._active_contexts:
                del self._active_contexts[conversation_id]

    def get_active_contexts(self) -> List[AgentContext]:
        return list(self._active_contexts.values())

    def cancel_conversation(self, conversation_id: str) -> bool:
        if conversation_id in self._active_contexts:
            context = self._active_contexts[conversation_id]
            context.state = AgentState.IDLE
            del self._active_contexts[conversation_id]
            return True
        return False

    async def cleanup(self):
        for context_id in list(self._active_contexts.keys()):
            self.cancel_conversation(context_id)

        self._tool_output_listeners.clear()
        self._stream_listeners.clear()
        logger.info("Enhanced agent runner cleaned up")


class ToolExecutorBase(ToolExecutor):
    def __init__(self, tool_name: str, description: str):
        self.tool_name = tool_name
        self.description = description

    def get_tool_spec(self) -> Dict[str, Any]:
        return {
            "name": self.tool_name,
            "description": self.description,
            "params": {},
        }

    async def execute(self, action: Action, context: AgentContext) -> ToolResult:
        import time

        start_time = time.time()

        try:
            output = await self._do_execute(action, context)
            execution_time = (time.time() - start_time) * 1000

            return ToolResult(
                tool_name=self.tool_name,
                success=True,
                output=output,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Tool {self.tool_name} error: {e}")

            return ToolResult(
                tool_name=self.tool_name,
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=execution_time,
            )

    @abstractmethod
    async def _do_execute(self, action: Action, context: AgentContext) -> Any:
        pass
