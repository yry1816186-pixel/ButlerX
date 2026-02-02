from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    TIME = "time"
    EVENT = "event"
    STATE = "state"
    LOCATION = "location"
    WEATHER = "weather"
    CUSTOM = "custom"


class ConditionType(Enum):
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    CONTAINS = "contains"
    BETWEEN = "between"
    AND = "and"
    OR = "or"


@dataclass
class Trigger:
    trigger_id: str
    trigger_type: TriggerType
    config: Dict[str, Any]
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type.value,
            "config": self.config,
            "enabled": self.enabled,
        }


@dataclass
class Condition:
    condition_id: str
    condition_type: ConditionType
    entity: str
    value: Any
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "condition_id": self.condition_id,
            "condition_type": self.condition_type.value,
            "entity": self.entity,
            "value": self.value,
            "enabled": self.enabled,
        }


@dataclass
class Action:
    action_id: str
    action_type: str
    params: Dict[str, Any]
    enabled: bool = True
    delay_seconds: float = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "params": self.params,
            "enabled": self.enabled,
            "delay_seconds": self.delay_seconds,
        }


@dataclass
class Automation:
    automation_id: str
    name: str
    description: str
    triggers: List[Trigger] = field(default_factory=list)
    conditions: List[Condition] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    enabled: bool = True
    mode: str = "all"
    created_at: float = field(default_factory=time.time)
    last_triggered: Optional[float] = None
    trigger_count: int = 0

    def should_trigger(self, trigger_data: Dict[str, Any], state_data: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False

        trigger_match = self._check_triggers(trigger_data)
        if not trigger_match:
            return False

        condition_match = self._check_conditions(state_data)
        if not condition_match:
            return False

        return True

    def _check_triggers(self, trigger_data: Dict[str, Any]) -> bool:
        if not self.triggers:
            return True

        matches = []
        for trigger in self.triggers:
            if not trigger.enabled:
                continue
            match = self._check_single_trigger(trigger, trigger_data)
            matches.append(match)

        if self.mode == "all":
            return all(matches)
        else:
            return any(matches)

    def _check_single_trigger(self, trigger: Trigger, trigger_data: Dict[str, Any]) -> bool:
        trigger_type = trigger.trigger_type
        config = trigger.config

        if trigger_type == TriggerType.TIME:
            current_time = time.time()
            return self._check_time_trigger(config, current_time)

        elif trigger_type == TriggerType.EVENT:
            event_type = trigger_data.get("type")
            return event_type == config.get("event_type")

        elif trigger_type == TriggerType.STATE:
            entity_id = config.get("entity_id")
            expected_state = config.get("state")
            current_state = state_data.get(entity_id, {}).get("state")
            return current_state == expected_state

        return False

    def _check_time_trigger(self, config: Dict[str, Any], current_time: float) -> bool:
        import datetime
        now = datetime.datetime.fromtimestamp(current_time)
        current_minutes = now.hour * 60 + now.minute

        if "time" in config:
            target_time = config["time"]
            if ":" in target_time:
                h, m = map(int, target_time.split(":"))
                target_minutes = h * 60 + m
                return current_minutes == target_minutes

        if "after_time" in config:
            after_time = config["after_time"]
            if ":" in after_time:
                h, m = map(int, after_time.split(":"))
                after_minutes = h * 60 + m
                return current_minutes >= after_minutes

        if "before_time" in config:
            before_time = config["before_time"]
            if ":" in before_time:
                h, m = map(int, before_time.split(":"))
                before_minutes = h * 60 + m
                return current_minutes <= before_minutes

        return False

    def _check_conditions(self, state_data: Dict[str, Any]) -> bool:
        if not self.conditions:
            return True

        matches = []
        for condition in self.conditions:
            if not condition.enabled:
                continue
            match = self._check_single_condition(condition, state_data)
            matches.append(match)

        if self.mode == "all":
            return all(matches)
        else:
            return any(matches)

    def _check_single_condition(self, condition: Condition, state_data: Dict[str, Any]) -> bool:
        entity_state = state_data.get(condition.entity, {})
        current_value = entity_state.get("state")

        if current_value is None:
            return False

        cond_type = condition.condition_type

        if cond_type == ConditionType.EQUAL:
            return current_value == condition.value
        elif cond_type == ConditionType.NOT_EQUAL:
            return current_value != condition.value
        elif cond_type == ConditionType.GREATER_THAN:
            try:
                return float(current_value) > float(condition.value)
            except (ValueError, TypeError):
                return False
        elif cond_type == ConditionType.LESS_THAN:
            try:
                return float(current_value) < float(condition.value)
            except (ValueError, TypeError):
                return False
        elif cond_type == ConditionType.CONTAINS:
            return str(condition.value) in str(current_value)

        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "automation_id": self.automation_id,
            "name": self.name,
            "description": self.description,
            "triggers": [t.to_dict() for t in self.triggers],
            "conditions": [c.to_dict() for c in self.conditions],
            "actions": [a.to_dict() for a in self.actions],
            "enabled": self.enabled,
            "mode": self.mode,
            "created_at": self.created_at,
            "last_triggered": self.last_triggered,
            "trigger_count": self.trigger_count,
        }


class AutomationEngine:
    def __init__(self) -> None:
        self.automations: Dict[str, Automation] = {}
        self.action_executor: Optional[Callable] = None

    def add_automation(self, automation: Automation) -> None:
        self.automations[automation.automation_id] = automation
        logger.info(f"Added automation: {automation.name}")

    def remove_automation(self, automation_id: str) -> bool:
        if automation_id not in self.automations:
            return False
        automation = self.automations.pop(automation_id)
        logger.info(f"Removed automation: {automation.name}")
        return True

    def get_automation(self, automation_id: str) -> Optional[Automation]:
        return self.automations.get(automation_id)

    def list_automations(self, enabled_only: bool = False) -> List[Automation]:
        automations = list(self.automations.values())
        if enabled_only:
            automations = [a for a in automations if a.enabled]
        return automations

    def set_action_executor(self, executor: Callable) -> None:
        self.action_executor = executor

    def evaluate_triggers(
        self,
        trigger_data: Dict[str, Any],
        state_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        results = []

        for automation in self.automations.values():
            if automation.should_trigger(trigger_data, state_data):
                logger.info(f"Automation triggered: {automation.name}")
                result = self._execute_automation(automation)
                results.append(result)

        return results

    def _execute_automation(self, automation: Automation) -> Dict[str, Any]:
        result = {
            "automation_id": automation.automation_id,
            "automation_name": automation.name,
            "success": False,
            "executed_actions": [],
            "failed_actions": [],
            "timestamp": time.time(),
        }

        try:
            automation.last_triggered = time.time()
            automation.trigger_count += 1

            if self.action_executor:
                for action in automation.actions:
                    if not action.enabled:
                        continue

                    if action.delay_seconds > 0:
                        time.sleep(action.delay_seconds)

                    try:
                        action_result = self.action_executor(action.to_dict())
                        result["executed_actions"].append(action.to_dict())
                    except Exception as e:
                        logger.error(f"Action execution failed: {e}")
                        result["failed_actions"].append(action.to_dict())
            else:
                result["executed_actions"] = [
                    a.to_dict() for a in automation.actions if a.enabled
                ]

            result["success"] = len(result["failed_actions"]) == 0

        except Exception as e:
            logger.error(f"Automation execution failed: {e}")
            result["success"] = False

        return result

    def enable_automation(self, automation_id: str) -> bool:
        automation = self.automations.get(automation_id)
        if not automation:
            return False
        automation.enabled = True
        logger.info(f"Enabled automation: {automation.name}")
        return True

    def disable_automation(self, automation_id: str) -> bool:
        automation = self.automations.get(automation_id)
        if not automation:
            return False
        automation.enabled = False
        logger.info(f"Disabled automation: {automation.name}")
        return True

    def search_automations(self, query: str) -> List[Automation]:
        query_lower = query.lower()
        return [
            automation for automation in self.automations.values()
            if (query_lower in automation.name.lower() or 
                query_lower in automation.description.lower())
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "automations": [
                automation.to_dict() for automation in self.automations.values()
            ],
            "automation_count": len(self.automations),
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Automations saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "AutomationEngine":
        engine = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for auto_data in data.get("automations", []):
            triggers = []
            for trigger_data in auto_data.get("triggers", []):
                trigger = Trigger(
                    trigger_id=trigger_data["trigger_id"],
                    trigger_type=TriggerType(trigger_data["trigger_type"]),
                    config=trigger_data.get("config", {}),
                    enabled=trigger_data.get("enabled", True),
                )
                triggers.append(trigger)

            conditions = []
            for cond_data in auto_data.get("conditions", []):
                condition = Condition(
                    condition_id=cond_data["condition_id"],
                    condition_type=ConditionType(cond_data["condition_type"]),
                    entity=cond_data["entity"],
                    value=cond_data["value"],
                    enabled=cond_data.get("enabled", True),
                )
                conditions.append(condition)

            actions = []
            for action_data in auto_data.get("actions", []):
                action = Action(
                    action_id=action_data["action_id"],
                    action_type=action_data["action_type"],
                    params=action_data.get("params", {}),
                    enabled=action_data.get("enabled", True),
                    delay_seconds=action_data.get("delay_seconds", 0),
                )
                actions.append(action)

            automation = Automation(
                automation_id=auto_data["automation_id"],
                name=auto_data["name"],
                description=auto_data["description"],
                triggers=triggers,
                conditions=conditions,
                actions=actions,
                enabled=auto_data.get("enabled", True),
                mode=auto_data.get("mode", "all"),
                created_at=auto_data.get("created_at", time.time()),
                last_triggered=auto_data.get("last_triggered"),
                trigger_count=auto_data.get("trigger_count", 0),
            )
            engine.add_automation(automation)

        logger.info(f"Automations loaded from {filepath}")
        return engine
