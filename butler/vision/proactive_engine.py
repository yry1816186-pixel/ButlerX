import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

from .smart_vision import ActivityType, VisionEvent

logger = logging.getLogger(__name__)


class InteractionPriority(Enum):
    HIGH = 3
    MEDIUM = 2
    LOW = 1


@dataclass
class InteractionRule:
    rule_id: str
    trigger_activity: ActivityType
    trigger_object: Optional[str] = None
    messages: List[str] = field(default_factory=list)
    priority: InteractionPriority = InteractionPriority.MEDIUM
    cooldown: int = 60
    time_conditions: Dict[str, Any] = field(default_factory=dict)
    condition_check: Optional[Callable[[Dict[str, Any]], bool]] = None
    last_triggered: float = 0
    
    def can_trigger(self, current_time: float, context: Dict[str, Any]) -> bool:
        if current_time - self.last_triggered < self.cooldown:
            return False
        
        if self.time_conditions:
            current_hour = time.localtime().tm_hour
            
            if "hour_start" in self.time_conditions:
                if current_hour < self.time_conditions["hour_start"]:
                    return False
            
            if "hour_end" in self.time_conditions:
                if current_hour >= self.time_conditions["hour_end"]:
                    return False
        
        if self.condition_check:
            return self.condition_check(context)
        
        return True
    
    def get_message(self) -> str:
        import random
        return random.choice(self.messages) if self.messages else ""
    
    def trigger(self):
        self.last_triggered = time.time()


class ProactiveEngine:
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.rules: List[InteractionRule] = []
        self.interaction_callbacks: List[Callable[[str], None]] = []
        self.event_history: List[VisionEvent] = []
        self.user_states: Dict[str, Any] = {}
        
        self._init_default_rules()
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        if config_path:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")
        
        return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "min_confidence": 0.7,
            "max_interactions_per_minute": 5,
            "global_cooldown": 30,
            "respect_user_mood": True
        }
    
    def _init_default_rules(self):
        self.rules = [
            InteractionRule(
                rule_id="welcome_home",
                trigger_activity=ActivityType.WALKING,
                messages=[
                    "欢迎回家！需要我帮您做点什么吗？",
                    "你回来啦！今天过得怎么样？",
                    "欢迎回家！要休息一下吗？"
                ],
                priority=InteractionPriority.HIGH,
                cooldown=300,
                condition_check=lambda ctx: self._is_user_returning(ctx)
            ),
            
            InteractionRule(
                rule_id="morning_greeting",
                trigger_activity=ActivityType.IDLE,
                messages=[
                    "早上好！新的一天开始了，需要我播放晨间新闻吗？",
                    "早安！今天有什么计划吗？",
                    "早上好！要来杯咖啡吗？"
                ],
                priority=InteractionPriority.HIGH,
                cooldown=600,
                time_conditions={"hour_start": 6, "hour_end": 11}
            ),
            
            InteractionRule(
                rule_id="evening_greeting",
                trigger_activity=ActivityType.IDLE,
                messages=[
                    "晚上好！今天过得怎么样？",
                    "一天辛苦了，要休息一下吗？",
                    "晚上好！要开启夜间模式吗？"
                ],
                priority=InteractionPriority.HIGH,
                cooldown=600,
                time_conditions={"hour_start": 18, "hour_end": 23}
            ),
            
            InteractionRule(
                rule_id="working_assist",
                trigger_activity=ActivityType.WORKING,
                trigger_object="laptop",
                messages=[
                    "你在工作吗？需要我帮您调亮灯光吗？",
                    "工作时间要注意休息哦！",
                    "需要我帮您播放专注音乐吗？",
                    "工作辛苦了，需要我帮您倒杯水吗？"
                ],
                priority=InteractionPriority.MEDIUM,
                cooldown=1800
            ),
            
            InteractionRule(
                rule_id="reading_assist",
                trigger_activity=ActivityType.READING,
                messages=[
                    "您在看书呢，保持专注！",
                    "需要我帮您调节阅读灯光吗？",
                    "这本书好看吗？"
                ],
                priority=InteractionPriority.MEDIUM,
                cooldown=1200
            ),
            
            InteractionRule(
                rule_id="watching_tv",
                trigger_activity=ActivityType.WATCHING_TV,
                messages=[
                    "您要开始看电视了吗？需要我帮您调暗灯光吗？",
                    "要开启观影模式吗？",
                    "需要我帮您调节音量吗？"
                ],
                priority=InteractionPriority.MEDIUM,
                cooldown=600
            ),
            
            InteractionRule(
                rule_id="cooking_assist",
                trigger_activity=ActivityType.COOKING,
                messages=[
                    "您在做饭，需要我帮您计时吗？",
                    "做饭要注意安全哦！",
                    "需要我帮您播放烹饪音乐吗？"
                ],
                priority=InteractionPriority.MEDIUM,
                cooldown=600
            ),
            
            InteractionRule(
                rule_id="exercise_encourage",
                trigger_activity=ActivityType.EXERCISING,
                messages=[
                    "加油！运动对身体好！",
                    "需要我帮您播放运动音乐吗？",
                    "运动真棒！要注意补水哦！"
                ],
                priority=InteractionPriority.MEDIUM,
                cooldown=900
            ),
            
            InteractionRule(
                rule_id="bedtime_prompt",
                trigger_activity=ActivityType.SLEEPING,
                messages=[
                    "要休息了吗？需要我帮您准备睡眠环境吗？",
                    "这么晚了，要注意休息哦！",
                    "晚安，需要我帮您关灯吗？"
                ],
                priority=InteractionPriority.HIGH,
                cooldown=3600,
                time_conditions={"hour_start": 21, "hour_end": 6}
            ),
            
            InteractionRule(
                rule_id="using_phone",
                trigger_activity=ActivityType.USING_PHONE,
                messages=[
                    "您在玩手机吗？要注意保护眼睛哦",
                    "看手机时间太长对眼睛不好，休息一下吧！",
                    "需要我帮您播放一些音乐吗？"
                ],
                priority=InteractionPriority.LOW,
                cooldown=1800
            ),
            
            InteractionRule(
                rule_id="idle_long",
                trigger_activity=ActivityType.IDLE,
                messages=[
                    "您看起来在发呆，需要我放点音乐吗？",
                    "需要我帮您做点什么吗？",
                    "您在想什么呢？"
                ],
                priority=InteractionPriority.LOW,
                cooldown=1200,
                condition_check=lambda ctx: self._is_idle_long(ctx)
            ),
            
            InteractionRule(
                rule_id="sitting_long",
                trigger_activity=ActivityType.SITTING,
                messages=[
                    "您坐了很久了，起来活动一下吧！",
                    "长时间坐着对身体不好，要起来走动走动哦",
                    "需要我帮您播放一些轻快的音乐吗？"
                ],
                priority=InteractionPriority.MEDIUM,
                cooldown=1800,
                condition_check=lambda ctx: self._is_sitting_long(ctx)
            ),
            
            InteractionRule(
                rule_id="rainy_day",
                trigger_activity=ActivityType.WATCHING_TV,
                messages=[
                    "今天下雨呢，外面挺冷的吧？",
                    "下雨天适合在家里待着，要来杯热饮吗？"
                ],
                priority=InteractionPriority.LOW,
                cooldown=3600,
                condition_check=lambda ctx: self._is_rainy_day(ctx)
            ),
        ]
    
    def _is_user_returning(self, context: Dict[str, Any]) -> bool:
        if not self.event_history:
            return False
        
        recent_events = [
            e for e in self.event_history
            if time.time() - e.timestamp < 600
        ]
        
        if not recent_events:
            return True
        
        return False
    
    def _is_idle_long(self, context: Dict[str, Any]) -> bool:
        idle_events = [
            e for e in self.event_history
            if e.activity == ActivityType.IDLE
            and time.time() - e.timestamp < 600
        ]
        
        return len(idle_events) >= 5
    
    def _is_sitting_long(self, context: Dict[str, Any]) -> bool:
        sitting_events = [
            e for e in self.event_history
            if e.activity == ActivityType.SITTING
            and time.time() - e.timestamp < 3600
        ]
        
        return len(sitting_events) >= 10
    
    def _is_rainy_day(self, context: Dict[str, Any]) -> bool:
        return False
    
    def add_rule(self, rule: InteractionRule):
        self.rules.append(rule)
        logger.info(f"Added interaction rule: {rule.rule_id}")
    
    def remove_rule(self, rule_id: str):
        self.rules = [r for r in self.rules if r.rule_id != rule_id]
        logger.info(f"Removed interaction rule: {rule_id}")
    
    def get_rule(self, rule_id: str) -> Optional[InteractionRule]:
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None
    
    def process_event(self, event: VisionEvent) -> Optional[str]:
        if not self.config["enabled"]:
            return None
        
        if event.confidence < self.config["min_confidence"]:
            return None
        
        self.event_history.append(event)
        
        if len(self.event_history) > 1000:
            self.event_history = self.event_history[-1000:]
        
        context = self._build_context(event)
        
        applicable_rules = [
            rule for rule in self.rules
            if self._is_rule_applicable(rule, event, context)
        ]
        
        if not applicable_rules:
            return None
        
        applicable_rules.sort(
            key=lambda r: r.priority.value,
            reverse=True
        )
        
        best_rule = applicable_rules[0]
        
        if best_rule.can_trigger(time.time(), context):
            message = best_rule.get_message()
            best_rule.trigger()
            
            logger.info(f"Triggered interaction: {best_rule.rule_id} - {message}")
            
            for callback in self.interaction_callbacks:
                try:
                    callback(message)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
            
            return message
        
        return None
    
    def _is_rule_applicable(
        self,
        rule: InteractionRule,
        event: VisionEvent,
        context: Dict[str, Any]
    ) -> bool:
        if rule.trigger_activity != event.activity:
            return False
        
        if rule.trigger_object:
            nearby_objects = context.get("nearby_objects", [])
            if rule.trigger_object not in nearby_objects:
                return False
        
        return True
    
    def _build_context(self, event: VisionEvent) -> Dict[str, Any]:
        now = time.time()
        recent_events = [
            e for e in self.event_history
            if now - e.timestamp < 3600
        ]
        
        activity_counts = {}
        for e in recent_events:
            activity = e.activity.value if e.activity else "unknown"
            activity_counts[activity] = activity_counts.get(activity, 0) + 1
        
        nearby_objects = event.data.get("nearby_objects", [])
        
        return {
            "event": event,
            "recent_events": recent_events,
            "activity_counts": activity_counts,
            "nearby_objects": nearby_objects,
            "user_states": self.user_states.copy()
        }
    
    def register_interaction_callback(self, callback: Callable[[str], None]):
        self.interaction_callbacks.append(callback)
        logger.info("Registered interaction callback")
    
    def unregister_interaction_callback(self, callback: Callable[[str], None]):
        if callback in self.interaction_callbacks:
            self.interaction_callbacks.remove(callback)
            logger.info("Unregistered interaction callback")
    
    def set_user_state(self, key: str, value: Any):
        self.user_states[key] = value
    
    def get_user_state(self, key: str, default: Any = None) -> Any:
        return self.user_states.get(key, default)
    
    def clear_event_history(self):
        self.event_history.clear()
        logger.info("Event history cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        now = time.time()
        recent_events = [
            e for e in self.event_history
            if now - e.timestamp < 3600
        ]
        
        triggered_rules = [
            rule for rule in self.rules
            if rule.last_triggered > 0 and now - rule.last_triggered < 3600
        ]
        
        return {
            "total_events": len(self.event_history),
            "recent_events": len(recent_events),
            "active_rules": len(self.rules),
            "triggered_rules_last_hour": len(triggered_rules),
            "callbacks_registered": len(self.interaction_callbacks)
        }


if __name__ == "__main__":
    def on_interaction(message: str):
        print(f"🤖 Interaction: {message}")
    
    engine = ProactiveEngine()
    engine.register_interaction_callback(on_interaction)
    
    test_event = VisionEvent(
        event_type="person_activity",
        timestamp=time.time(),
        person_id=1,
        activity=ActivityType.WORKING,
        bbox=[100, 100, 300, 400],
        confidence=0.9,
        data={"nearby_objects": ["laptop", "keyboard"]}
    )
    
    message = engine.process_event(test_event)
    if message:
        print(f"Generated message: {message}")
    
    print(f"\nStatistics: {json.dumps(engine.get_statistics(), indent=2, default=str)}")
