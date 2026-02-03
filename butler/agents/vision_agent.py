from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
import base64

from .agent import Agent, AgentConfig, AgentMessage, MessageType, AgentTask, AgentCapability

logger = logging.getLogger(__name__)

class VisionAgent(Agent):
    def __init__(
        self,
        config: AgentConfig,
        vision_client: Any = None
    ):
        super().__init__(config)
        self._vision_client = vision_client
        self._detection_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 5.0

    async def initialize(self) -> bool:
        try:
            self.add_capability(AgentCapability(
                name="object_detection",
                description="Detect objects in images or video frames",
                input_types=["image", "video_frame"],
                output_types=["objects", "bounding_boxes", "labels"],
                parameters={
                    "confidence_threshold": {"type": "float", "default": 0.5},
                    "max_objects": {"type": "integer", "default": 100},
                    "include_labels": {"type": "list", "default": None}
                }
            ))

            self.add_capability(AgentCapability(
                name="face_detection",
                description="Detect faces in images",
                input_types=["image", "video_frame"],
                output_types=["faces", "bounding_boxes", "landmarks"]
            ))

            self.add_capability(AgentCapability(
                name="face_recognition",
                description="Recognize faces and match to known identities",
                input_types=["image", "face_image"],
                output_types=["identity", "confidence", "face_id"]
            ))

            self.add_capability(AgentCapability(
                name="scene_understanding",
                description="Analyze and understand scene content",
                input_types=["image", "video_frame"],
                output_types=["scene_description", "objects", "context"]
            ))

            self.add_capability(AgentCapability(
                name="activity_recognition",
                description="Recognize human activities",
                input_types=["image_sequence", "video_frame"],
                output_types=["activity", "confidence", "duration"]
            ))

            self.add_capability(AgentCapability(
                name="person_tracking",
                description="Track persons across video frames",
                input_types=["video_frame"],
                output_types=["person_id", "position", "velocity"]
            ))

            return True

        except Exception as e:
            self._logger.error(f"Failed to initialize vision agent: {e}")
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
        content = message.content if isinstance(message.content, dict) else {"image_data": message.content}

        action = content.get("action", "detect")

        if action == "detect_objects":
            result = await self._detect_objects(
                image_data=content.get("image_data"),
                confidence_threshold=content.get("confidence_threshold", 0.5),
                max_objects=content.get("max_objects", 100)
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        elif action == "detect_faces":
            result = await self._detect_faces(
                image_data=content.get("image_data")
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        elif action == "recognize_face":
            result = await self._recognize_face(
                face_data=content.get("face_data"),
                face_library=content.get("face_library", [])
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        elif action == "understand_scene":
            result = await self._understand_scene(
                image_data=content.get("image_data")
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        elif action == "recognize_activity":
            result = await self._recognize_activity(
                frames=content.get("frames", [])
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        return None

    async def _handle_notification(self, message: AgentMessage):
        content = message.content if isinstance(message.content, dict) else {}

        if content.get("type") == "clear_cache":
            self._detection_cache.clear()

    async def _detect_objects(
        self,
        image_data: str,
        confidence_threshold: float = 0.5,
        max_objects: int = 100
    ) -> Dict[str, Any]:
        cache_key = f"objects_{hash(image_data)}_{confidence_threshold}"

        if cache_key in self._detection_cache:
            return self._detection_cache[cache_key]

        if self._vision_client and hasattr(self._vision_client, "detect_objects"):
            result = await self._vision_client.detect_objects(
                image_data=image_data,
                confidence_threshold=confidence_threshold,
                max_objects=max_objects
            )
        else:
            result = {
                "objects": [],
                "timestamp": datetime.now().isoformat(),
                "status": "no_vision_client"
            }

        self._detection_cache[cache_key] = result

        asyncio.create_task(self._expire_cache_entry(cache_key))

        return result

    async def _detect_faces(self, image_data: str) -> Dict[str, Any]:
        if self._vision_client and hasattr(self._vision_client, "detect_faces"):
            result = await self._vision_client.detect_faces(image_data=image_data)
        else:
            result = {
                "faces": [],
                "timestamp": datetime.now().isoformat(),
                "status": "no_vision_client"
            }

        return result

    async def _recognize_face(
        self,
        face_data: str,
        face_library: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if self._vision_client and hasattr(self._vision_client, "recognize_face"):
            result = await self._vision_client.recognize_face(
                face_data=face_data,
                face_library=face_library
            )
        else:
            result = {
                "identity": None,
                "confidence": 0.0,
                "face_id": None,
                "timestamp": datetime.now().isoformat(),
                "status": "no_vision_client"
            }

        return result

    async def _understand_scene(self, image_data: str) -> Dict[str, Any]:
        if self._vision_client and hasattr(self._vision_client, "understand_scene"):
            result = await self._vision_client.understand_scene(image_data=image_data)
        else:
            result = {
                "scene_description": "",
                "objects": [],
                "context": {},
                "timestamp": datetime.now().isoformat(),
                "status": "no_vision_client"
            }

        return result

    async def _recognize_activity(self, frames: List[str]) -> Dict[str, Any]:
        if self._vision_client and hasattr(self._vision_client, "recognize_activity"):
            result = await self._vision_client.recognize_activity(frames=frames)
        else:
            result = {
                "activity": "unknown",
                "confidence": 0.0,
                "duration": 0.0,
                "timestamp": datetime.now().isoformat(),
                "status": "no_vision_client"
            }

        return result

    async def _expire_cache_entry(self, cache_key: str):
        await asyncio.sleep(self._cache_ttl)
        self._detection_cache.pop(cache_key, None)

    async def execute_task(self, task: AgentTask) -> Any:
        task_type = task.task_type
        payload = task.payload

        if task_type == "detect_objects":
            return await self._detect_objects(
                image_data=payload.get("image_data"),
                confidence_threshold=payload.get("confidence_threshold", 0.5),
                max_objects=payload.get("max_objects", 100)
            )

        elif task_type == "detect_faces":
            return await self._detect_faces(
                image_data=payload.get("image_data")
            )

        elif task_type == "recognize_face":
            return await self._recognize_face(
                face_data=payload.get("face_data"),
                face_library=payload.get("face_library", [])
            )

        elif task_type == "understand_scene":
            return await self._understand_scene(
                image_data=payload.get("image_data")
            )

        elif task_type == "recognize_activity":
            return await self._recognize_activity(
                frames=payload.get("frames", [])
            )

        raise ValueError(f"Unknown task type: {task_type}")

    async def shutdown(self):
        self._detection_cache.clear()
        self._logger.info("Vision agent shutting down")

    def clear_cache(self):
        self._detection_cache.clear()

    def get_cache_size(self) -> int:
        return len(self._detection_cache)

    def set_cache_ttl(self, ttl: float):
        self._cache_ttl = ttl

    def set_vision_client(self, vision_client: Any):
        self._vision_client = vision_client

    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update({
            "vision_capabilities": list(self.capabilities.keys()),
            "cache_size": len(self._detection_cache),
            "cache_ttl": self._cache_ttl,
            "vision_client_available": self._vision_client is not None
        })
        return base_dict
