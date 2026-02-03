from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, time
from enum import Enum
import re

class ConditionType(Enum):
    STATE = "state"
    NUMERIC_STATE = "numeric_state"
    TIME = "time"
    TEMPLATE = "template"
    DEVICE = "device"
    ZONE = "zone"
    SUN = "sun"
    OR = "or"
    AND = "and"
    NOT = "not"

@dataclass
class ConditionConfig:
    condition_id: str
    condition_type: ConditionType
    enabled: bool = True
    variables: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "condition_id": self.condition_id,
            "condition_type": self.condition_type.value,
            "enabled": self.enabled,
            "variables": self.variables
        }

class Condition(ABC):
    def __init__(self, config: ConditionConfig):
        self.config = config

    @abstractmethod
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass

class StateCondition(Condition):
    def __init__(
        self,
        config: ConditionConfig,
        entity_id: str,
        state: Optional[str] = None,
        state_not: Optional[str] = None,
        for_duration: Optional[float] = None,
        attribute: Optional[str] = None,
        match: Optional[str] = None
    ):
        super().__init__(config)
        self.entity_id = entity_id
        self.state = state
        self.state_not = state_not
        self.for_duration = for_duration
        self.attribute = attribute
        self.match = match

    async def evaluate(self, context: Dict[str, Any]) -> bool:
        if not self.config.enabled:
            return True

        entity = context.get("entities", {}).get(self.entity_id)
        if not entity:
            return False

        if isinstance(entity, dict):
            current_state = entity.get("attributes", {}).get(self.attribute) if self.attribute else entity.get("state")
        else:
            current_state = entity.attributes.get(self.attribute) if self.attribute else entity.state

        current_state = str(current_state)

        if self.state:
            if self.match:
                pattern = self.state
                if pattern.startswith("regex:"):
                    pattern = pattern[6:]
                    if not re.match(pattern, current_state):
                        return False
                elif pattern.startswith("glob:"):
                    pattern = pattern[5:]
                    pattern = pattern.replace("*", ".*").replace("?", ".")
                    if not re.match(pattern, current_state):
                        return False
                else:
                    if current_state != self.state:
                        return False
            else:
                if current_state != self.state:
                    return False

        if self.state_not and current_state == self.state_not:
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "entity_id": self.entity_id,
            "state": self.state,
            "state_not": self.state_not,
            "for_duration": self.for_duration,
            "attribute": self.attribute,
            "match": self.match
        })
        return data

class NumericStateCondition(Condition):
    def __init__(
        self,
        config: ConditionConfig,
        entity_id: str,
        above: Optional[float] = None,
        below: Optional[float] = None,
        attribute: Optional[str] = None
    ):
        super().__init__(config)
        self.entity_id = entity_id
        self.above = above
        self.below = below
        self.attribute = attribute

    async def evaluate(self, context: Dict[str, Any]) -> bool:
        if not self.config.enabled:
            return True

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

        if self.above is not None and value <= self.above:
            return False

        if self.below is not None and value >= self.below:
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "entity_id": self.entity_id,
            "above": self.above,
            "below": self.below,
            "attribute": self.attribute
        })
        return data

class TimeCondition(Condition):
    def __init__(
        self,
        config: ConditionConfig,
        after: Optional[str] = None,
        before: Optional[str] = None,
        weekday: Optional[List[str]] = None
    ):
        super().__init__(config)
        self.after = after
        self.before = before
        self.weekday = weekday

    async def evaluate(self, context: Dict[str, Any]) -> bool:
        if not self.config.enabled:
            return True

        now = datetime.now()
        current_time = now.time()
        current_weekday = now.strftime("%A").lower()

        if self.weekday and current_weekday not in [w.lower() for w in self.weekday]:
            return False

        if self.after and self.before:
            try:
                after_time = datetime.strptime(self.after, "%H:%M:%S").time()
                before_time = datetime.strptime(self.before, "%H:%M:%S").time()
                if not (after_time <= current_time <= before_time):
                    return False
            except ValueError:
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "after": self.after,
            "before": self.before,
            "weekday": self.weekday
        })
        return data

class TemplateCondition(Condition):
    def __init__(
        self,
        config: ConditionConfig,
        value_template: str
    ):
        super().__init__(config)
        self.value_template = value_template

    async def evaluate(self, context: Dict[str, Any]) -> bool:
        if not self.config.enabled:
            return True

        try:
            from jinja2 import Template
            template = Template(self.value_template)
            result = template.render(**context)
            return result.lower() in ["true", "1", "yes", "on"]
        except Exception as e:
            return False

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "value_template": self.value_template
        })
        return data

class DeviceCondition(Condition):
    def __init__(
        self,
        config: ConditionConfig,
        device_id: str,
        entity_id: Optional[str] = None,
        domain: Optional[str] = None,
        type: Optional[str] = None,
        state: Optional[str] = None
    ):
        super().__init__(config)
        self.device_id = device_id
        self.entity_id = entity_id
        self.domain = domain
        self.type = type
        self.state = state

    async def evaluate(self, context: Dict[str, Any]) -> bool:
        if not self.config.enabled:
            return True

        devices = context.get("devices", {})
        device = devices.get(self.device_id)

        if not device:
            return False

        if self.entity_id:
            entities = device.get("entities", [])
            if self.entity_id not in entities:
                return False

        if self.domain:
            if device.get("domain") != self.domain:
                return False

        if self.type:
            if device.get("type") != self.type:
                return False

        if self.state:
            device_state = device.get("state", "unknown")
            if device_state != self.state:
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "device_id": self.device_id,
            "entity_id": self.entity_id,
            "domain": self.domain,
            "type": self.type,
            "state": self.state
        })
        return data

class ZoneCondition(Condition):
    def __init__(
        self,
        config: ConditionConfig,
        entity_id: str,
        zone: str
    ):
        super().__init__(config)
        self.entity_id = entity_id
        self.zone = zone

    async def evaluate(self, context: Dict[str, Any]) -> bool:
        if not self.config.enabled:
            return True

        entity = context.get("entities", {}).get(self.entity_id)
        if not entity:
            return False

        if isinstance(entity, dict):
            entity_state = entity.get("state")
            entity_zone = entity.get("attributes", {}).get("zone")
        else:
            entity_state = entity.state
            entity_zone = entity.attributes.get("zone")

        if entity_zone == self.zone:
            return True

        return False

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "entity_id": self.entity_id,
            "zone": self.zone
        })
        return data

class SunCondition(Condition):
    def __init__(
        self,
        config: ConditionConfig,
        before: Optional[str] = None,
        after: Optional[str] = None,
        before_offset: Optional[float] = None,
        after_offset: Optional[float] = None
    ):
        super().__init__(config)
        self.before = before  # "sunset" or "sunrise"
        self.after = after
        self.before_offset = before_offset
        self.after_offset = after_offset

    async def evaluate(self, context: Dict[str, Any]) -> bool:
        if not self.config.enabled:
            return True

        now = datetime.now()
        sun_events = context.get("sun_events", {})

        if self.before:
            event_time = sun_events.get(self.before)
            if event_time:
                if self.before_offset:
                    event_time = datetime.fromtimestamp(event_time.timestamp() + self.before_offset)
                if now > event_time:
                    return False

        if self.after:
            event_time = sun_events.get(self.after)
            if event_time:
                if self.after_offset:
                    event_time = datetime.fromtimestamp(event_time.timestamp() + self.after_offset)
                if now < event_time:
                    return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "before": self.before,
            "after": self.after,
            "before_offset": self.before_offset,
            "after_offset": self.after_offset
        })
        return data

class OrCondition(Condition):
    def __init__(
        self,
        config: ConditionConfig,
        conditions: List[Condition]
    ):
        super().__init__(config)
        self.conditions = conditions

    async def evaluate(self, context: Dict[str, Any]) -> bool:
        if not self.config.enabled:
            return True

        for condition in self.conditions:
            if await condition.evaluate(context):
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "conditions": [c.to_dict() for c in self.conditions]
        })
        return data

class AndCondition(Condition):
    def __init__(
        self,
        config: ConditionConfig,
        conditions: List[Condition]
    ):
        super().__init__(config)
        self.conditions = conditions

    async def evaluate(self, context: Dict[str, Any]) -> bool:
        if not self.config.enabled:
            return True

        for condition in self.conditions:
            if not await condition.evaluate(context):
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "conditions": [c.to_dict() for c in self.conditions]
        })
        return data

class NotCondition(Condition):
    def __init__(
        self,
        config: ConditionConfig,
        condition: Condition
    ):
        super().__init__(config)
        self.condition = condition

    async def evaluate(self, context: Dict[str, Any]) -> bool:
        if not self.config.enabled:
            return True

        return not await self.condition.evaluate(context)

    def to_dict(self) -> Dict[str, Any]:
        data = self.config.to_dict()
        data.update({
            "condition": self.condition.to_dict()
        })
        return data
