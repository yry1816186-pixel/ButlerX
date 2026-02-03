from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, time
from enum import Enum
import re

class TriggerType(Enum):
    STATE = "state"
    TIME = "time"
    EVENT = "event"
    NUMERIC_STATE = "numeric_state"
    TEMPLATE = "template"
    SUN = "sun"
    HOME_ASSISTANT = "home_assistant"
    MQTT = "mqtt"

@dataclass
class TriggerData:
    trigger_id: str
    trigger_type: str
    timestamp: str
    trigger_count: int
    context: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type,
            "timestamp": self.timestamp,
            "trigger_count": self.trigger_count,
            "context": self.context
        }

@dataclass
class TriggerConfig:
    trigger_id: str
    trigger_type: TriggerType
    enabled: bool = True
    cooldown: Optional[float] = None
    for_duration: Optional[float] = None
    variables: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type.value,
            "enabled": self.enabled,
            "cooldown": self.cooldown,
            "for_duration": self.for_duration,
            "variables": self.variables
        }

class Trigger(ABC):
    def __init__(self, config: TriggerConfig):
        self.config = config
        self._last_triggered: Optional[datetime] = None
        self._trigger_count = 0
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []

    @abstractmethod
    async def check(self, context: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass

    def add_callback(self, callback: Callable[[Dict[str, Any]], None]):
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[Dict[str, Any]], None]):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def trigger(self, context: Dict[str, Any]):
        if not self.config.enabled:
            return False

        if self.config.cooldown and self._last_triggered:
            elapsed = (datetime.now() - self._last_triggered).total_seconds()
            if elapsed < self.config.cooldown:
                return False

        if await self.check(context):
            self._last_triggered = datetime.now()
            self._trigger_count += 1

            trigger_data = {
                "trigger_id": self.config.trigger_id,
                "trigger_type": self.config.trigger_type.value,
                "timestamp": self._last_triggered.isoformat(),
                "trigger_count": self._trigger_count,
                "context": context
            }

            for callback in self._callbacks:
                try:
                    await callback(trigger_data)
                except Exception as e:
                    pass

            return True

        return False

    @property
    def last_triggered(self) -> Optional[datetime]:
        return self._last_triggered

    @property
    def trigger_count(self) -> int:
        return self._trigger_count

class StateTrigger(Trigger):
    def __init__(
        self,
        config: TriggerConfig,
        entity_id: str,
        from_state: Optional[str] = None,
        to_state: Optional[str] = None,
        for_duration: Optional[float] = None,
        attribute: Optional[str] = None
    ):
        super().__init__(config)
        self.entity_id = entity_id
        self.from_state = from_state
        self.to_state = to_state
        self.for_duration = for_duration
        self.attribute = attribute
        self._state_change_time: Optional[datetime] = None

    async def check(self, context: Dict[str, Any]) -> bool:
        entity = context.get("entities", {}).get(self.entity_id)
        if not entity:
            return False

        old_state = context.get("old_state", {}).get(self.entity_id, {}).get("state")
        new_state = entity.get("state") if isinstance(entity, dict) else entity.state

        if self.attribute:
            new_value = entity.get("attributes", {}).get(self.attribute) if isinstance(entity, dict) else entity.attributes.get(self.attribute)
            old_value = context.get("old_state", {}).get(self.entity_id, {}).get("attributes", {}).get(self.attribute)
        else:
            new_value = new_state
            old_value = old_state

        if self.from_state and str(old_value) != self.from_state:
            return False

        if self.to_state and str(new_value) != self.to_state:
            return False

        if self.from_state or self.to_state:
            if old_value == new_value:
                return False

        if self.for_duration or self.config.for_duration:
            duration = self.for_duration or self.config.for_duration
            if self._state_change_time is None:
                self._state_change_time = datetime.now()
                return False

            elapsed = (datetime.now() - self._state_change_time).total_seconds()
            if elapsed < duration:
                return False

            self._state_change_time = None
            return True

        return True

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "entity_id": self.entity_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "for_duration": self.for_duration,
            "attribute": self.attribute
        })
        return data

class TimeTrigger(Trigger):
    def __init__(
        self,
        config: TriggerConfig,
        at: Optional[time] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        weekday: Optional[List[str]] = None,
        interval: Optional[str] = None
    ):
        super().__init__(config)
        self.at = at
        self.after = after
        self.before = before
        self.weekday = weekday
        self.interval = interval
        self._last_interval_trigger: Optional[datetime] = None

    async def check(self, context: Dict[str, Any]) -> bool:
        now = datetime.now()
        current_time = now.time()
        current_weekday = now.strftime("%A").lower()

        if self.weekday and current_weekday not in [w.lower() for w in self.weekday]:
            return False

        if self.at:
            target_time = datetime.combine(now.date(), self.at)
            if abs((now - target_time).total_seconds()) <= 1:
                return True

        if self.after and self.before:
            try:
                after_time = datetime.strptime(self.after, "%H:%M:%S").time()
                before_time = datetime.strptime(self.before, "%H:%M:%S").time()
                if after_time <= current_time <= before_time:
                    return True
            except ValueError:
                pass

        if self.interval:
            if self._last_interval_trigger is None:
                self._last_interval_trigger = now
                return True

            interval_seconds = self._parse_interval(self.interval)
            if interval_seconds and (now - self._last_interval_trigger).total_seconds() >= interval_seconds:
                self._last_interval_trigger = now
                return True

        return False

    def _parse_interval(self, interval: str) -> Optional[float]:
        pattern = r'(?:(\d+)\s*(hours?|hrs?|h))\s*(?:(\d+)\s*(minutes?|mins?|m))?\s*(?:(\d+)\s*(seconds?|secs?|s))?'
        match = re.match(pattern, interval.lower())
        if not match:
            try:
                return float(interval)
            except ValueError:
                return None

        hours = int(match.group(1)) if match.group(1) else 0
        minutes = int(match.group(3)) if match.group(3) else 0
        seconds = int(match.group(5)) if match.group(5) else 0

        return hours * 3600 + minutes * 60 + seconds

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "at": self.at.isoformat() if self.at else None,
            "after": self.after,
            "before": self.before,
            "weekday": self.weekday,
            "interval": self.interval
        })
        return data

class EventTrigger(Trigger):
    def __init__(
        self,
        config: TriggerConfig,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(config)
        self.event_type = event_type
        self.event_data = event_data or {}

    async def check(self, context: Dict[str, Any]) -> bool:
        event = context.get("event")
        if not event:
            return False

        if event.get("event_type") != self.event_type:
            return False

        if self.event_data:
            event_data = event.get("data", {})
            for key, expected_value in self.event_data.items():
                if event_data.get(key) != expected_value:
                    return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "event_type": self.event_type,
            "event_data": self.event_data
        })
        return data

class NumericStateTrigger(Trigger):
    def __init__(
        self,
        config: TriggerConfig,
        entity_id: str,
        above: Optional[float] = None,
        below: Optional[float] = None,
        attribute: Optional[str] = None,
        for_duration: Optional[float] = None
    ):
        super().__init__(config)
        self.entity_id = entity_id
        self.above = above
        self.below = below
        self.attribute = attribute
        self.for_duration = for_duration
        self._condition_met_time: Optional[datetime] = None

    async def check(self, context: Dict[str, Any]) -> bool:
        entity = context.get("entities", {}).get(self.entity_id)
        if not entity:
            return False

        if isinstance(entity, dict):
            value_str = entity.get("attributes", {}).get(self.attribute) if self.attribute else entity.get("state")
        else:
            value_str = entity.attributes.get(self.attribute) if self.attribute else entity.state

        try:
            value = float(value_str)
        except (ValueError, TypeError):
            return False

        condition_met = True

        if self.above is not None and value <= self.above:
            condition_met = False

        if self.below is not None and value >= self.below:
            condition_met = False

        if not condition_met:
            self._condition_met_time = None
            return False

        if self.for_duration:
            if self._condition_met_time is None:
                self._condition_met_time = datetime.now()
                return False

            elapsed = (datetime.now() - self._condition_met_time).total_seconds()
            if elapsed < self.for_duration:
                return False

            self._condition_met_time = None

        return True

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "entity_id": self.entity_id,
            "above": self.above,
            "below": self.below,
            "attribute": self.attribute,
            "for_duration": self.for_duration
        })
        return data

class TemplateTrigger(Trigger):
    def __init__(
        self,
        config: TriggerConfig,
        value_template: str,
        for_duration: Optional[float] = None
    ):
        super().__init__(config)
        self.value_template = value_template
        self.for_duration = for_duration
        self._template_true_time: Optional[datetime] = None

    async def check(self, context: Dict[str, Any]) -> bool:
        try:
            from jinja2 import Template
            template = Template(self.value_template)
            result = template.render(**context)

            is_true = result.lower() in ["true", "1", "yes", "on"]

            if not is_true:
                self._template_true_time = None
                return False

            if self.for_duration:
                if self._template_true_time is None:
                    self._template_true_time = datetime.now()
                    return False

                elapsed = (datetime.now() - self._template_true_time).total_seconds()
                if elapsed < self.for_duration:
                    return False

                self._template_true_time = None

            return True

        except Exception as e:
            return False

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "value_template": self.value_template,
            "for_duration": self.for_duration
        })
        return data

class SunTrigger(Trigger):
    def __init__(
        self,
        config: TriggerConfig,
        event: str,
        offset: Optional[float] = None
    ):
        super().__init__(config)
        self.event = event  # "sunset" or "sunrise"
        self.offset = offset  # Offset in seconds

    async def check(self, context: Dict[str, Any]) -> bool:
        sun_events = context.get("sun_events", {})
        if self.event not in sun_events:
            return False

        event_time = sun_events[self.event]
        now = datetime.now()

        if self.offset:
            event_time = datetime.fromtimestamp(event_time.timestamp() + self.offset)

        return abs((now - event_time).total_seconds()) <= 1

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "event": self.event,
            "offset": self.offset
        })
        return data

class MQTTTrigger(Trigger):
    def __init__(
        self,
        config: TriggerConfig,
        topic: str,
        payload: Optional[str] = None,
        encoding: str = "utf-8"
    ):
        super().__init__(config)
        self.topic = topic
        self.payload = payload
        self.encoding = encoding

    async def check(self, context: Dict[str, Any]) -> bool:
        mqtt_message = context.get("mqtt_message")
        if not mqtt_message:
            return False

        if mqtt_message.get("topic") != self.topic:
            return False

        if self.payload is not None:
            message_payload = mqtt_message.get("payload", "")
            if message_payload != self.payload:
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "topic": self.topic,
            "payload": self.payload,
            "encoding": self.encoding
        })
        return data
