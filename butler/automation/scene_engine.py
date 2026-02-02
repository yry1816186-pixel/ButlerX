from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Scene:
    scene_id: str
    name: str
    description: str
    actions: List[Dict[str, Any]] = field(default_factory=list)
    icon: Optional[str] = None
    category: str = "custom"
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "name": self.name,
            "description": self.description,
            "actions": self.actions,
            "icon": self.icon,
            "category": self.category,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SceneEngine:
    def __init__(self) -> None:
        self.scenes: Dict[str, Scene] = {}
        self._init_default_scenes()

    def _init_default_scenes(self) -> None:
        default_scenes = [
            Scene(
                scene_id="scene_home",
                name="回家",
                description="回家模式 - 开灯、调温、欢迎音乐",
                actions=[
                    {"action_type": "turn_on", "params": {"target": "living_room_light", "brightness": 100}},
                    {"action_type": "set_temperature", "params": {"value": 25}},
                    {"action_type": "play_music", "params": {"volume": 40}},
                    {"action_type": "notify", "params": {"message": "欢迎回家！"}},
                ],
                icon="🏠",
                category="preset",
            ),
            Scene(
                scene_id="scene_away",
                name="离家",
                description="离家模式 - 关灯、安防、锁门",
                actions=[
                    {"action_type": "turn_off", "params": {"target": "all_lights"}},
                    {"action_type": "set_temperature", "params": {"value": 26}},
                    {"action_type": "lock_all", "params": {}},
                    {"action_type": "arm_security", "params": {}},
                    {"action_type": "notify", "params": {"message": "离家模式已开启"}},
                ],
                icon="🚪",
                category="preset",
            ),
            Scene(
                scene_id="scene_sleep",
                name="睡眠",
                description="睡眠模式 - 关灯、拉窗帘、调温",
                actions=[
                    {"action_type": "turn_off", "params": {"target": "all_lights"}},
                    {"action_type": "close_cover", "params": {"target": "all_curtains"}},
                    {"action_type": "set_temperature", "params": {"value": 22}},
                    {"action_type": "turn_off", "params": {"target": "tv"}},
                    {"action_type": "turn_off", "params": {"target": "speaker"}},
                ],
                icon="🌙",
                category="preset",
            ),
            Scene(
                scene_id="scene_movie",
                name="观影",
                description="观影模式 - 调暗灯光、拉窗帘、开电视",
                actions=[
                    {"action_type": "set_brightness", "params": {"target": "living_room_light", "value": 20}},
                    {"action_type": "close_cover", "params": {"target": "living_room_curtain"}},
                    {"action_type": "turn_on", "params": {"target": "tv"}},
                    {"action_type": "set_temperature", "params": {"value": 23}},
                ],
                icon="🎬",
                category="preset",
            ),
            Scene(
                scene_id="scene_wake",
                name="起床",
                description="起床模式 - 开窗帘、调亮灯光、轻音乐",
                actions=[
                    {"action_type": "open_cover", "params": {"target": "all_curtains"}},
                    {"action_type": "turn_on", "params": {"target": "bedroom_light", "brightness": 80}},
                    {"action_type": "play_music", "params": {"volume": 30, "type": "light"}},
                    {"action_type": "notify", "params": {"message": "早上好！新的一天开始了"}},
                ],
                icon="☀️",
                category="preset",
            ),
            Scene(
                scene_id="scene_cozy",
                name="温馨",
                description="温馨模式 - 暖光、柔和音乐",
                actions=[
                    {"action_type": "set_brightness", "params": {"target": "living_room_light", "value": 70}},
                    {"action_type": "set_color_temp", "params": {"target": "living_room_light", "value": 3000}},
                    {"action_type": "play_music", "params": {"volume": 35, "type": "relaxing"}},
                ],
                icon="✨",
                category="mood",
            ),
        ]

        for scene in default_scenes:
            self.add_scene(scene)

        logger.info(f"Initialized {len(default_scenes)} default scenes")

    def add_scene(self, scene: Scene) -> None:
        self.scenes[scene.scene_id] = scene
        logger.info(f"Added scene: {scene.name}")

    def remove_scene(self, scene_id: str) -> bool:
        if scene_id not in self.scenes:
            return False
        scene = self.scenes.pop(scene_id)
        logger.info(f"Removed scene: {scene.name}")
        return True

    def get_scene(self, scene_id: str) -> Optional[Scene]:
        return self.scenes.get(scene_id)

    def list_scenes(
        self,
        category: Optional[str] = None,
        enabled_only: bool = False
    ) -> List[Scene]:
        scenes = list(self.scenes.values())
        
        if category:
            scenes = [s for s in scenes if s.category == category]
        
        if enabled_only:
            scenes = [s for s in scenes if s.enabled]
        
        return scenes

    def activate_scene(
        self,
        scene_id: str,
        action_executor: Optional[callable] = None
    ) -> Dict[str, Any]:
        result = {
            "scene_id": scene_id,
            "success": False,
            "message": "",
            "executed_actions": [],
            "failed_actions": [],
        }

        scene = self.scenes.get(scene_id)
        if not scene:
            result["message"] = f"场景不存在: {scene_id}"
            return result

        if not scene.enabled:
            result["message"] = f"场景已禁用: {scene.name}"
            return result

        try:
            logger.info(f"Activating scene: {scene.name}")

            if action_executor:
                for action in scene.actions:
                    try:
                        action_result = action_executor(action)
                        result["executed_actions"].append(action)
                    except Exception as e:
                        logger.error(f"Action execution failed: {e}")
                        result["failed_actions"].append(action)
            else:
                result["executed_actions"] = scene.actions

            if not result["failed_actions"]:
                result["success"] = True
                result["message"] = f"成功激活场景: {scene.name}"
            else:
                result["success"] = False
                result["message"] = f"场景部分失败: {scene.name}"

        except Exception as e:
            logger.error(f"Scene activation failed: {e}")
            result["success"] = False
            result["message"] = f"场景激活失败: {str(e)}"

        return result

    def enable_scene(self, scene_id: str) -> bool:
        scene = self.scenes.get(scene_id)
        if not scene:
            return False
        scene.enabled = True
        scene.updated_at = time.time()
        logger.info(f"Enabled scene: {scene.name}")
        return True

    def disable_scene(self, scene_id: str) -> bool:
        scene = self.scenes.get(scene_id)
        if not scene:
            return False
        scene.enabled = False
        scene.updated_at = time.time()
        logger.info(f"Disabled scene: {scene.name}")
        return True

    def search_scenes(self, query: str) -> List[Scene]:
        query_lower = query.lower()
        return [
            scene for scene in self.scenes.values()
            if (query_lower in scene.name.lower() or 
                query_lower in scene.description.lower())
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenes": [scene.to_dict() for scene in self.scenes.values()],
            "scene_count": len(self.scenes),
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Scenes saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "SceneEngine":
        engine = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for scene_data in data.get("scenes", []):
            scene = Scene(
                scene_id=scene_data["scene_id"],
                name=scene_data["name"],
                description=scene_data["description"],
                actions=scene_data.get("actions", []),
                icon=scene_data.get("icon"),
                category=scene_data.get("category", "custom"),
                enabled=scene_data.get("enabled", True),
                created_at=scene_data.get("created_at", time.time()),
                updated_at=scene_data.get("updated_at", time.time()),
            )
            engine.scenes[scene.scene_id] = scene
        
        logger.info(f"Scenes loaded from {filepath}")
        return engine
