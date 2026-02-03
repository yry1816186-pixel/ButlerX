from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
import json

from .agent import Agent, AgentConfig, AgentMessage, MessageType, AgentTask, AgentCapability
from ..conversation.smart_dialogue import SmartDialogueEngine

logger = logging.getLogger(__name__)

class DialogueAgent(Agent):
    def __init__(
        self,
        config: AgentConfig,
        dialogue_engine: SmartDialogueEngine
    ):
        super().__init__(config)
        self._dialogue_engine = dialogue_engine
        self._conversation_history: Dict[str, List[Dict[str, Any]]] = {}
        self._max_history_length = 50

    async def initialize(self) -> bool:
        try:
            self.add_capability(AgentCapability(
                name="dialogue",
                description="Process natural language dialogue and generate responses",
                input_types=["text", "speech"],
                output_types=["text", "speech"],
                parameters={
                    "max_tokens": {"type": "integer", "default": 500},
                    "temperature": {"type": "float", "default": 0.7},
                    "enable_emotion": {"type": "boolean", "default": True}
                }
            ))

            self.add_capability(AgentCapability(
                name="greeting",
                description="Generate time-appropriate greetings",
                input_types=[],
                output_types=["text"]
            ))

            self.add_capability(AgentCapability(
                name="emotion_detection",
                description="Detect emotion from user input",
                input_types=["text", "speech"],
                output_types=["emotion", "confidence"]
            ))

            self.add_capability(AgentCapability(
                name="context_management",
                description="Maintain conversation context and history",
                input_types=["text", "context"],
                output_types=["context"]
            ))

            return True

        except Exception as e:
            self._logger.error(f"Failed to initialize dialogue agent: {e}")
            return False

    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        try:
            if message.message_type == MessageType.REQUEST:
                return await self._handle_request(message)

            elif message.message_type == MessageType.NOTIFICATION:
                await self._handle_notification(message)

        except Exception as e:
            self._logger.error(f"Error processing message: {e}")

        return None

    async def _handle_request(self, message: AgentMessage) -> Optional[AgentMessage]:
        content = message.content if isinstance(message.content, dict) else {"input": message.content}

        action = content.get("action", "respond")

        if action == "respond":
            response = await self._respond(
                user_input=content.get("input", ""),
                user_id=content.get("user_id", "default"),
                context=content.get("context", {})
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=response
            )

        elif action == "greeting":
            greeting = await self._generate_greeting(
                user_id=content.get("user_id", "default")
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content={"greeting": greeting}
            )

        elif action == "detect_emotion":
            emotion = await self._detect_emotion(
                text=content.get("text", "")
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=emotion
            )

        return None

    async def _handle_notification(self, message: AgentMessage):
        content = message.content if isinstance(message.content, dict) else {}

        if content.get("type") == "context_update":
            await self._update_context(
                user_id=content.get("user_id", "default"),
                context=content.get("context", {})
            )

    async def respond(
        self,
        user_input: str,
        user_id: str = "default",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        response = await self._dialogue_engine.respond(
            user_input=user_input,
            user_id=user_id,
            context=context or {}
        )

        await self._save_to_history(user_id, user_input, response)

        return response

    async def _respond(
        self,
        user_input: str,
        user_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self.respond(user_input, user_id, context)

    async def _generate_greeting(self, user_id: str) -> str:
        return await self._dialogue_engine.greet(user_id=user_id)

    async def _detect_emotion(self, text: str) -> Dict[str, Any]:
        from ..conversation.smart_dialogue import Emotion
        emotion = await self._dialogue_engine.detect_emotion(text)
        return {
            "emotion": emotion.value if isinstance(emotion, Emotion) else str(emotion),
            "text": text,
            "confidence": 0.8
        }

    async def _update_context(self, user_id: str, context: Dict[str, Any]):
        await self._dialogue_engine.update_context(user_id=user_id, context=context)

    async def _save_to_history(
        self,
        user_id: str,
        user_input: str,
        response: Dict[str, Any]
    ):
        if user_id not in self._conversation_history:
            self._conversation_history[user_id] = []

        self._conversation_history[user_id].append({
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "response": response
        })

        if len(self._conversation_history[user_id]) > self._max_history_length:
            self._conversation_history[user_id] = self._conversation_history[user_id][-self._max_history_length:]

    async def execute_task(self, task: AgentTask) -> Any:
        task_type = task.task_type
        payload = task.payload

        if task_type == "respond":
            return await self.respond(
                user_input=payload.get("input", ""),
                user_id=payload.get("user_id", "default"),
                context=payload.get("context", {})
            )

        elif task_type == "greeting":
            return await self._generate_greeting(
                user_id=payload.get("user_id", "default")
            )

        elif task_type == "detect_emotion":
            return await self._detect_emotion(
                text=payload.get("text", "")
            )

        elif task_type == "batch_respond":
            inputs = payload.get("inputs", [])
            user_id = payload.get("user_id", "default")
            results = []
            for inp in inputs:
                result = await self.respond(
                    user_input=inp,
                    user_id=user_id,
                    context=payload.get("context", {})
                )
                results.append(result)
            return results

        raise ValueError(f"Unknown task type: {task_type}")

    async def shutdown(self):
        self._logger.info("Dialogue agent shutting down")

    def get_conversation_history(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        history = self._conversation_history.get(user_id, [])
        return history[-limit:]

    def clear_conversation_history(self, user_id: str):
        if user_id in self._conversation_history:
            del self._conversation_history[user_id]

    def get_all_conversations(self) -> Dict[str, List[Dict[str, Any]]]:
        return self._conversation_history.copy()

    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update({
            "dialogue_capabilities": list(self.capabilities.keys()),
            "conversation_count": len(self._conversation_history),
            "max_history_length": self._max_history_length
        })
        return base_dict
