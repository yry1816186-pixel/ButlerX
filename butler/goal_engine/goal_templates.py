from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GoalTemplate:
    template_id: str
    name: str
    description: str
    trigger_phrases: List[str]
    required_actions: List[Dict[str, Any]] = field(default_factory=list)
    optional_actions: List[Dict[str, Any]] = field(default_factory=list)
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    priority: int = 0
    enabled: bool = True

    def matches(self, text: str) -> bool:
        text_lower = text.lower()
        return any(phrase.lower() in text_lower for phrase in self.trigger_phrases)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "trigger_phrases": self.trigger_phrases,
            "required_actions": self.required_actions,
            "optional_actions": self.optional_actions,
            "conditions": self.conditions,
            "priority": self.priority,
            "enabled": self.enabled,
        }


class GoalTemplateRegistry:
    def __init__(self) -> None:
        self.templates: Dict[str, GoalTemplate] = {}
        self._init_default_templates()

    def _init_default_templates(self) -> None:
        self.register_template(GoalTemplate(
            template_id="sleep",
            name="睡眠模式",
            description="进入睡眠模式，关闭所有灯光、拉上窗帘、调低温度",
            trigger_phrases=[
                "我要睡了", "我要睡觉", "准备睡觉", "睡觉时间到了", "晚安",
                "I want to sleep", "I'm going to sleep", "Good night", "Time to sleep"
            ],
            required_actions=[
                {"action_type": "turn_off", "params": {"target": "all_lights"}},
                {"action_type": "close_cover", "params": {"target": "all_curtains"}},
                {"action_type": "set_temperature", "params": {"value": 22, "target": "all_climate"}},
            ],
            optional_actions=[
                {"action_type": "turn_off", "params": {"target": "tv"}},
                {"action_type": "turn_off", "params": {"target": "speaker"}},
                {"action_type": "set_mode", "params": {"mode": "sleep"}},
            ],
            priority=10,
            enabled=True,
        ))

        self.register_template(GoalTemplate(
            template_id="wake_up",
            name="起床模式",
            description="起床，打开窗帘、调亮灯光、播放轻音乐",
            trigger_phrases=[
                "我要起床", "我醒了", "起床了", "早上好", "醒来了",
                "I'm waking up", "I'm awake", "Good morning", "Wake up"
            ],
            required_actions=[
                {"action_type": "open_cover", "params": {"target": "all_curtains"}},
                {"action_type": "turn_on", "params": {"target": "bedroom_light", "brightness": 80}},
            ],
            optional_actions=[
                {"action_type": "set_temperature", "params": {"value": 24}},
                {"action_type": "play_music", "params": {"volume": 30, "type": "light"}},
                {"action_type": "notify", "params": {"message": "早上好！新的一天开始了"}},
            ],
            priority=10,
            enabled=True,
        ))

        self.register_template(GoalTemplate(
            template_id="leave_home",
            name="离家模式",
            description="离家，关闭所有设备、开启安防",
            trigger_phrases=[
                "我要出门", "我要走了", "离家了", "我出去了", "拜拜",
                "I'm leaving", "I'm going out", "Leaving home", "Bye"
            ],
            required_actions=[
                {"action_type": "turn_off", "params": {"target": "all_lights"}},
                {"action_type": "set_mode", "params": {"mode": "away"}},
                {"action_type": "lock_all", "params": {}},
            ],
            optional_actions=[
                {"action_type": "turn_off", "params": {"target": "all_climate"}},
                {"action_type": "arm_security", "params": {}},
                {"action_type": "notify", "params": {"message": "离家模式已开启"}},
            ],
            priority=10,
            enabled=True,
        ))

        self.register_template(GoalTemplate(
            template_id="return_home",
            name="回家模式",
            description="回家，打开灯光、调节温度、播放音乐",
            trigger_phrases=[
                "我回来了", "我要回家", "到家了", "回家了",
                "I'm home", "I'm back", "Returning home", "Home sweet home"
            ],
            required_actions=[
                {"action_type": "set_mode", "params": {"mode": "home"}},
                {"action_type": "turn_on", "params": {"target": "living_room_light", "brightness": 100}},
            ],
            optional_actions=[
                {"action_type": "set_temperature", "params": {"value": 25}},
                {"action_type": "play_music", "params": {"volume": 40}},
                {"action_type": "notify", "params": {"message": "欢迎回家"}},
            ],
            priority=10,
            enabled=True,
        ))

        self.register_template(GoalTemplate(
            template_id="watch_movie",
            name="观影模式",
            description="观影，调暗灯光、关闭窗帘、打开电视",
            trigger_phrases=[
                "我要看电影", "看电影了", "准备看电影", "观影时间",
                "I want to watch a movie", "Movie time", "Watching movie"
            ],
            required_actions=[
                {"action_type": "set_brightness", "params": {"target": "living_room_light", "value": 20}},
                {"action_type": "close_cover", "params": {"target": "living_room_curtain"}},
            ],
            optional_actions=[
                {"action_type": "turn_on", "params": {"target": "tv"}},
                {"action_type": "turn_off", "params": {"target": "other_lights"}},
                {"action_type": "set_temperature", "params": {"value": 23}},
            ],
            priority=8,
            enabled=True,
        ))

        self.register_template(GoalTemplate(
            template_id="cooking",
            name="烹饪模式",
            description="烹饪，打开厨房灯光、开启抽油烟机",
            trigger_phrases=[
                "我要做饭", "我要炒菜", "做饭了", "烹饪时间",
                "I'm cooking", "Time to cook", "Cooking"
            ],
            required_actions=[
                {"action_type": "turn_on", "params": {"target": "kitchen_light", "brightness": 100}},
            ],
            optional_actions=[
                {"action_type": "turn_on", "params": {"target": "range_hood"}},
                {"action_type": "set_temperature", "params": {"value": 24}},
                {"action_type": "play_music", "params": {"volume": 25}},
            ],
            priority=7,
            enabled=True,
        ))

        self.register_template(GoalTemplate(
            template_id="relax",
            name="放松模式",
            description="放松，调暗灯光、播放舒缓音乐",
            trigger_phrases=[
                "我要放松", "放松一下", "休息一下", "该放松了",
                "I want to relax", "Relaxing", "Time to relax"
            ],
            required_actions=[
                {"action_type": "set_brightness", "params": {"target": "living_room_light", "value": 30}},
            ],
            optional_actions=[
                {"action_type": "play_music", "params": {"volume": 35, "type": "relaxing"}},
                {"action_type": "set_temperature", "params": {"value": 24}},
                {"action_type": "turn_off", "params": {"target": "tv"}},
            ],
            priority=6,
            enabled=True,
        ))

        logger.info(f"Initialized {len(self.templates)} goal templates")

    def register_template(self, template: GoalTemplate) -> None:
        self.templates[template.template_id] = template
        logger.info(f"Registered goal template: {template.name}")

    def get_template(self, template_id: str) -> Optional[GoalTemplate]:
        return self.templates.get(template_id)

    def find_matching_template(self, text: str) -> Optional[GoalTemplate]:
        matches = []
        for template in self.templates.values():
            if not template.enabled:
                continue
            if template.matches(text):
                matches.append(template)

        if not matches:
            return None

        matches.sort(key=lambda t: t.priority, reverse=True)
        return matches[0]

    def list_templates(self, enabled_only: bool = True) -> List[GoalTemplate]:
        templates = list(self.templates.values())
        if enabled_only:
            templates = [t for t in templates if t.enabled]
        return templates

    def enable_template(self, template_id: str) -> bool:
        template = self.templates.get(template_id)
        if not template:
            return False
        template.enabled = True
        logger.info(f"Enabled goal template: {template_id}")
        return True

    def disable_template(self, template_id: str) -> bool:
        template = self.templates.get(template_id)
        if not template:
            return False
        template.enabled = False
        logger.info(f"Disabled goal template: {template_id}")
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "templates": [template.to_dict() for template in self.templates.values()],
            "template_count": len(self.templates),
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Goal templates saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "GoalTemplateRegistry":
        registry = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for template_data in data.get("templates", []):
            template = GoalTemplate(
                template_id=template_data["template_id"],
                name=template_data["name"],
                description=template_data["description"],
                trigger_phrases=template_data["trigger_phrases"],
                required_actions=template_data.get("required_actions", []),
                optional_actions=template_data.get("optional_actions", []),
                conditions=template_data.get("conditions", []),
                priority=template_data.get("priority", 0),
                enabled=template_data.get("enabled", True),
            )
            registry.register_template(template)

        logger.info(f"Goal templates loaded from {filepath}")
        return registry
