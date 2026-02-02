from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class IntentType(Enum):
    CONTROL = "control"
    QUERY = "query"
    SCENE = "scene"
    REMINDER = "reminder"
    SCHEDULE = "schedule"
    AUTOMATION = "automation"
    CONVERSATION = "conversation"
    GOAL = "goal"
    UNKNOWN = "unknown"


@dataclass
class Intent:
    intent_type: IntentType
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    action: Optional[str] = None
    target: Optional[str] = None
    location: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_type": self.intent_type.value,
            "confidence": self.confidence,
            "entities": self.entities,
            "raw_text": self.raw_text,
            "action": self.action,
            "target": self.target,
            "location": self.location,
            "parameters": self.parameters,
        }


class IntentClassifier:
    def __init__(self) -> None:
        self._control_keywords = [
            "打开", "关闭", "开启", "关掉", "调", "设置", "控制", "开启",
            "turn on", "turn off", "open", "close", "set", "adjust", "control"
        ]
        self._query_keywords = [
            "查询", "查看", "状态", "多少", "温度", "湿度", "亮不亮",
            "what", "how", "status", "check", "query", "temperature", "humidity"
        ]
        self._scene_keywords = [
            "场景", "模式", "回家", "离家", "睡眠", "观影", "起床",
            "scene", "mode", "home", "away", "sleep", "movie", "wake up"
        ]
        self._reminder_keywords = [
            "提醒", "记住", "别忘了", "闹钟", "定时",
            "remind", "remember", "don't forget", "alarm", "timer"
        ]
        self._schedule_keywords = [
            "日程", "安排", "计划", "预约", "时间",
            "schedule", "appointment", "plan", "book", "time"
        ]
        self._automation_keywords = [
            "自动化", "自动", "规则", "条件", "触发",
            "automation", "auto", "rule", "condition", "trigger"
        ]
        self._goal_keywords = [
            "我要", "我想", "帮我", "准备", "开始",
            "I want", "I need", "help me", "prepare", "start"
        ]

    def classify(self, text: str, context: Optional[Dict[str, Any]] = None) -> Intent:
        context = context or {}
        text_lower = text.lower()
        
        intent_type = IntentType.UNKNOWN
        confidence = 0.0
        entities = {}
        action = None
        target = None
        location = None
        parameters = {}

        score_control = self._score_keywords(text_lower, self._control_keywords)
        score_query = self._score_keywords(text_lower, self._query_keywords)
        score_scene = self._score_keywords(text_lower, self._scene_keywords)
        score_reminder = self._score_keywords(text_lower, self._reminder_keywords)
        score_schedule = self._score_keywords(text_lower, self._schedule_keywords)
        score_automation = self._score_keywords(text_lower, self._automation_keywords)
        score_goal = self._score_keywords(text_lower, self._goal_keywords)

        max_score = max(score_control, score_query, score_scene, score_reminder, 
                       score_schedule, score_automation, score_goal)
        
        if max_score > 0:
            if max_score == score_control:
                intent_type = IntentType.CONTROL
                confidence = min(score_control, 1.0)
            elif max_score == score_query:
                intent_type = IntentType.QUERY
                confidence = min(score_query, 1.0)
            elif max_score == score_scene:
                intent_type = IntentType.SCENE
                confidence = min(score_scene, 1.0)
            elif max_score == score_reminder:
                intent_type = IntentType.REMINDER
                confidence = min(score_reminder, 1.0)
            elif max_score == score_schedule:
                intent_type = IntentType.SCHEDULE
                confidence = min(score_schedule, 1.0)
            elif max_score == score_automation:
                intent_type = IntentType.AUTOMATION
                confidence = min(score_automation, 1.0)
            elif max_score == score_goal:
                intent_type = IntentType.GOAL
                confidence = min(score_goal, 1.0)
        else:
            intent_type = IntentType.CONVERSATION
            confidence = 0.5

        action, target, location = self._extract_entities(text)
        
        entities = {
            "action": action,
            "target": target,
            "location": location,
        }
        
        if "时间" in text_lower or "几点" in text_lower:
            entities["time"] = self._extract_time(text)
        if "温度" in text_lower:
            entities["temperature"] = self._extract_temperature(text)
        if "亮度" in text_lower:
            entities["brightness"] = self._extract_brightness(text)

        parameters = context.get("parameters", {})
        
        return Intent(
            intent_type=intent_type,
            confidence=confidence,
            entities=entities,
            raw_text=text,
            action=action,
            target=target,
            location=location,
            parameters=parameters,
        )

    def _score_keywords(self, text: str, keywords: List[str]) -> float:
        score = 0.0
        for keyword in keywords:
            if keyword in text:
                score += 1.0
        return score

    def _extract_entities(self, text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        text_lower = text.lower()
        
        action = None
        action_map = {
            "打开": "turn_on", "关闭": "turn_off", "开启": "turn_on",
            "turn on": "turn_on", "turn off": "turn_off",
            "调高": "increase", "调低": "decrease",
            "调亮": "increase_brightness", "调暗": "decrease_brightness",
        }
        for key, value in action_map.items():
            if key in text_lower:
                action = value
                break
        
        target = None
        target_map = {
            "灯": "light", "灯光": "light", "照明": "light",
            "空调": "air_conditioner", "温度": "temperature",
            "窗帘": "curtain", "电视": "tv", "音响": "speaker",
            "light": "light", "air conditioner": "air_conditioner",
            "curtain": "curtain", "tv": "tv", "speaker": "speaker",
        }
        for key, value in target_map.items():
            if key in text_lower:
                target = value
                break
        
        location = None
        location_map = {
            "客厅": "living_room", "卧室": "bedroom", "厨房": "kitchen",
            "卫生间": "bathroom", "书房": "study", "阳台": "balcony",
            "living room": "living_room", "bedroom": "bedroom",
            "kitchen": "kitchen", "bathroom": "bathroom",
            "study": "study", "balcony": "balcony",
        }
        for key, value in location_map.items():
            if key in text_lower:
                location = value
                break
        
        return action, target, location

    def _extract_time(self, text: str) -> Optional[str]:
        import re
        time_pattern = r'\d{1,2}[:：]\d{2}'
        match = re.search(time_pattern, text)
        if match:
            return match.group().replace("：", ":")
        return None

    def _extract_temperature(self, text: str) -> Optional[float]:
        import re
        temp_pattern = r'(\d+\.?\d*)\s*[度℃℃]'
        match = re.search(temp_pattern, text)
        if match:
            return float(match.group(1))
        return None

    def _extract_brightness(self, text: str) -> Optional[int]:
        import re
        brightness_pattern = r'(\d+)%'
        match = re.search(brightness_pattern, text)
        if match:
            return int(match.group(1))
        return None
