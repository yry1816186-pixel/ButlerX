from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ScenarioType(Enum):
    TIME_BASED = "time_based"
    EVENT_BASED = "event_based"
    LOCATION_BASED = "location_based"
    WEATHER_BASED = "weather_based"
    USER_ACTIVITY = "user_activity"
    MANUAL = "manual"
    COMPOSITE = "composite"


class ScenarioState(Enum):
    INACTIVE = "inactive"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class ScenarioCondition:
    condition_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    operator: str = "equals"
    value: Any = None
    enabled: bool = True

    def evaluate(self, context: Dict[str, Any]) -> bool:
        if not self.enabled:
            return True

        if self.condition_type == "time":
            return self._evaluate_time(context)
        elif self.condition_type == "device_state":
            return self._evaluate_device_state(context)
        elif self.condition_type == "weather":
            return self._evaluate_weather(context)
        elif self.condition_type == "location":
            return self._evaluate_location(context)
        elif self.condition_type == "user_presence":
            return self._evaluate_user_presence(context)
        elif self.condition_type == "custom":
            callback = self.parameters.get("callback")
            if callback and callable(callback):
                return callback(context)
        elif self.condition_type == "expression":
            expr = self.parameters.get("expression")
            if expr:
                return self._evaluate_expression(expr, context)

        return False

    def _evaluate_time(self, context: Dict[str, Any]) -> bool:
        current_time = context.get("current_time", time.time())
        time_of_day = context.get("time_of_day", "")

        if self.operator == "equals":
            return time_of_day == self.value
        elif self.operator == "not_equals":
            return time_of_day != self.value
        elif self.operator == "in_range":
            start_time = self.parameters.get("start_time")
            end_time = self.parameters.get("end_time")
            if start_time and end_time:
                return start_time <= current_time <= end_time

        return False

    def _evaluate_device_state(self, context: Dict[str, Any]) -> bool:
        device_states = context.get("device_states", {})
        device_id = self.parameters.get("device_id")
        state = device_states.get(device_id)

        if state is None:
            return False

        if self.operator == "equals":
            return state == self.value
        elif self.operator == "not_equals":
            return state != self.value
        elif self.operator == "greater_than":
            return state > self.value
        elif self.operator == "less_than":
            return state < self.value

        return False

    def _evaluate_weather(self, context: Dict[str, Any]) -> bool:
        weather = context.get("weather", {})

        if self.condition_type == "weather":
            condition = self.parameters.get("condition")
            if condition == "temperature":
                temp = weather.get("temperature", 0)
                if self.operator == "greater_than":
                    return temp > self.value
                elif self.operator == "less_than":
                    return temp < self.value
            elif condition == "condition":
                weather_condition = weather.get("condition", "")
                return weather_condition == self.value

        return False

    def _evaluate_location(self, context: Dict[str, Any]) -> bool:
        user_location = context.get("user_location", "")
        locations = self.value if isinstance(self.value, list) else [self.value]

        if self.operator == "equals":
            return user_location in locations
        elif self.operator == "not_equals":
            return user_location not in locations

        return False

    def _evaluate_user_presence(self, context: Dict[str, Any]) -> bool:
        user_presence = context.get("user_presence", {})
        user_id = self.parameters.get("user_id")

        if user_id:
            is_present = user_presence.get(user_id, False)
            if self.operator == "equals":
                return is_present == self.value
            elif self.operator == "not_equals":
                return is_present != self.value

        return False

    def _evaluate_expression(self, expr: str, context: Dict[str, Any]) -> bool:
        try:
            return eval(expr, {"__builtins__": {}}, context)
        except Exception as e:
            logger.warning(f"Error evaluating expression '{expr}': {e}")
            return False


@dataclass
class ScenarioAction:
    action_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    delay: float = 0.0
    retry_count: int = 0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return {"success": True, "skipped": True}

        if self.delay > 0:
            await asyncio.sleep(self.delay)

        action_executor = context.get("action_executor")
        if not action_executor:
            logger.warning(f"No action executor available for {self.action_type}")
            return {"success": False, "error": "No action executor"}

        try:
            result = await action_executor(self.action_type, self.parameters)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error executing action {self.action_type}: {e}")
            return {"success": False, "error": str(e)}


@dataclass
class ScenarioTransition:
    from_scenario_id: str
    to_scenario_id: str
    conditions: List[ScenarioCondition] = field(default_factory=list)
    trigger_mode: str = "all"
    metadata: Dict[str, Any] = field(default_factory=dict)


class Scenario:
    def __init__(
        self,
        scenario_id: str,
        name: str,
        description: str = "",
        scenario_type: ScenarioType = ScenarioType.MANUAL,
    ):
        self.scenario_id = scenario_id
        self.name = name
        self.description = description
        self.scenario_type = scenario_type

        self.state = ScenarioState.INACTIVE
        self.conditions: List[ScenarioCondition] = []
        self.actions: List[ScenarioAction] = []
        self.transitions: List[ScenarioTransition] = []
        self.exit_actions: List[ScenarioAction] = []

        self.context: Dict[str, Any] = {}
        self.created_at: float = time.time()
        self.activated_at: Optional[float] = None
        self.deactivated_at: Optional[float] = None
        self.activation_count: int = 0
        self.last_execution_time: Optional[float] = None

        self._listeners: List[Callable[[Scenario], None]] = []

    def add_condition(self, condition: ScenarioCondition) -> None:
        self.conditions.append(condition)

    def add_action(self, action: ScenarioAction) -> None:
        self.actions.append(action)

    def add_exit_action(self, action: ScenarioAction) -> None:
        self.exit_actions.append(action)

    def add_transition(self, transition: ScenarioTransition) -> None:
        self.transitions.append(transition)

    def add_listener(self, listener: Callable[[Scenario], None]) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[Scenario], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_listeners(self) -> None:
        for listener in self._listeners:
            try:
                listener(self)
            except Exception as e:
                logger.error(f"Error notifying scenario listener: {e}")

    def evaluate_conditions(self, context: Dict[str, Any]) -> bool:
        if not self.conditions:
            return True

        for condition in self.conditions:
            if not condition.evaluate(context):
                return False

        return True

    def check_transitions(self, context: Dict[str, Any]) -> Optional[str]:
        for transition in self.transitions:
            all_match = True

            for condition in transition.conditions:
                if not condition.evaluate(context):
                    all_match = False
                    break

            if all_match:
                return transition.to_scenario_id

        return None

    async def activate(self, context: Dict[str, Any]) -> bool:
        if self.state == ScenarioState.ACTIVE:
            return True

        try:
            self.state = ScenarioState.ACTIVATING
            self._notify_listeners()

            for action in self.actions:
                result = await action.execute(context)
                if not result.get("success", False):
                    logger.warning(f"Action failed during scenario activation: {result}")

            self.state = ScenarioState.ACTIVE
            self.activated_at = time.time()
            self.activation_count += 1
            self.context = context

            logger.info(f"Scenario activated: {self.name}")
            self._notify_listeners()
            return True

        except Exception as e:
            logger.error(f"Error activating scenario {self.name}: {e}")
            self.state = ScenarioState.ERROR
            self._notify_listeners()
            return False

    async def deactivate(self, context: Dict[str, Any]) -> bool:
        if self.state == ScenarioState.INACTIVE:
            return True

        try:
            self.state = ScenarioState.DEACTIVATING
            self._notify_listeners()

            for action in self.exit_actions:
                result = await action.execute(context)
                if not result.get("success", False):
                    logger.warning(f"Exit action failed during scenario deactivation: {result}")

            self.state = ScenarioState.INACTIVE
            self.deactivated_at = time.time()

            logger.info(f"Scenario deactivated: {self.name}")
            self._notify_listeners()
            return True

        except Exception as e:
            logger.error(f"Error deactivating scenario {self.name}: {e}")
            self.state = ScenarioState.ERROR
            self._notify_listeners()
            return False

    def pause(self) -> None:
        if self.state == ScenarioState.ACTIVE:
            self.state = ScenarioState.PAUSED
            logger.info(f"Scenario paused: {self.name}")
            self._notify_listeners()

    def resume(self) -> None:
        if self.state == ScenarioState.PAUSED:
            self.state = ScenarioState.ACTIVE
            logger.info(f"Scenario resumed: {self.name}")
            self._notify_listeners()

    def get_active_duration(self) -> float:
        if self.activated_at is None:
            return 0.0

        if self.deactivated_at is not None:
            return self.deactivated_at - self.activated_at

        return time.time() - self.activated_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "scenario_type": self.scenario_type.value,
            "state": self.state.value,
            "conditions": [
                {
                    "condition_type": c.condition_type,
                    "parameters": c.parameters,
                    "operator": c.operator,
                    "value": c.value,
                    "enabled": c.enabled,
                }
                for c in self.conditions
            ],
            "actions": [
                {
                    "action_type": a.action_type,
                    "parameters": a.parameters,
                    "delay": a.delay,
                    "retry_count": a.retry_count,
                    "enabled": a.enabled,
                }
                for a in self.actions
            ],
            "transitions": [
                {
                    "from_scenario_id": t.from_scenario_id,
                    "to_scenario_id": t.to_scenario_id,
                    "conditions_count": len(t.conditions),
                }
                for t in self.transitions
            ],
            "exit_actions_count": len(self.exit_actions),
            "created_at": self.created_at,
            "activated_at": self.activated_at,
            "deactivated_at": self.deactivated_at,
            "activation_count": self.activation_count,
            "last_execution_time": self.last_execution_time,
            "active_duration": self.get_active_duration(),
        }
