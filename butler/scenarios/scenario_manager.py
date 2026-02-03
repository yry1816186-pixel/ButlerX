from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .scenario import (
    Scenario,
    ScenarioCondition,
    ScenarioAction,
    ScenarioTransition,
    ScenarioType,
    ScenarioState,
)

logger = logging.getLogger(__name__)


class ScenarioPriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ScenarioTemplate:
    template_id: str
    name: str
    description: str
    scenario_type: ScenarioType
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    exit_actions: List[Dict[str, Any]] = field(default_factory=list)
    transitions: List[Dict[str, Any]] = field(default_factory=list)
    priority: ScenarioPriority = ScenarioPriority.MEDIUM
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def create_instance(self, name: str, parameter_values: Optional[Dict[str, Any]] = None) -> Scenario:
        scenario = Scenario(
            scenario_id=f"{self.template_id}_{int(time.time())}",
            name=name,
            description=self.description,
            scenario_type=self.scenario_type,
        )

        for cond_data in self.conditions:
            parameters = cond_data.copy()
            for param_name, param_value in (parameter_values or {}).items():
                if param_name in parameters:
                    if isinstance(parameters[param_name], str):
                        parameters[param_name] = parameters[param_name].replace(f"{{{param_name}}}", str(param_value))
                    else:
                        parameters[param_name] = param_value

            scenario.add_condition(ScenarioCondition(**parameters))

        for action_data in self.actions:
            parameters = action_data.copy()
            for param_name, param_value in (parameter_values or {}).items():
                if param_name in parameters:
                    if isinstance(parameters[param_name], str):
                        parameters[param_name] = parameters[param_name].replace(f"{{{param_name}}}", str(param_value))
                    else:
                        parameters[param_name] = param_value

            scenario.add_action(ScenarioAction(**parameters))

        for action_data in self.exit_actions:
            scenario.add_exit_action(ScenarioAction(**action_data))

        for trans_data in self.transitions:
            conditions = [
                ScenarioCondition(**cond_data)
                for cond_data in trans_data.get("conditions", [])
            ]
            scenario.add_transition(ScenarioTransition(
                from_scenario_id=trans_data["from_scenario_id"],
                to_scenario_id=trans_data["to_scenario_id"],
                conditions=conditions,
                trigger_mode=trans_data.get("trigger_mode", "all"),
                metadata=trans_data.get("metadata", {}),
            ))

        return scenario

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "scenario_type": self.scenario_type.value,
            "conditions": self.conditions,
            "actions": self.actions,
            "exit_actions": self.exit_actions,
            "transitions": self.transitions,
            "priority": self.priority.value,
            "parameters": self.parameters,
            "metadata": self.metadata,
        }


class ScenarioManager:
    def __init__(self):
        self.scenarios: Dict[str, Scenario] = {}
        self.templates: Dict[str, ScenarioTemplate] = {}
        self.active_scenarios: Set[str] = set()
        self.scenario_history: List[Dict[str, Any]] = []
        self._max_history_size = 100

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._listeners: List[Callable[[Scenario, str], None]] = []

        self._init_default_templates()

    def _init_default_templates(self) -> None:
        templates = [
            ScenarioTemplate(
                template_id="wake_up",
                name="起床模式",
                description="早上起床时的场景",
                scenario_type=ScenarioType.TIME_BASED,
                conditions=[
                    {
                        "condition_type": "time",
                        "operator": "equals",
                        "value": "morning",
                    },
                ],
                actions=[
                    {
                        "action_type": "set_brightness",
                        "parameters": {"target": "bedroom_light", "brightness": 80},
                        "delay": 0.0,
                    },
                    {
                        "action_type": "set_temperature",
                        "parameters": {"target": "thermostat", "value": 22},
                        "delay": 5.0,
                    },
                    {
                        "action_type": "play_music",
                        "parameters": {"playlist": "morning", "volume": 30},
                        "delay": 10.0,
                    },
                    {
                        "action_type": "notify",
                        "parameters": {"message": "早上好！新的一天开始了。"},
                        "delay": 15.0,
                    },
                ],
                exit_actions=[
                    {
                        "action_type": "set_brightness",
                        "parameters": {"target": "bedroom_light", "brightness": 0},
                    },
                ],
                priority=ScenarioPriority.HIGH,
            ),
            ScenarioTemplate(
                template_id="sleep",
                name="睡眠模式",
                description="晚上睡觉时的场景",
                scenario_type=ScenarioType.TIME_BASED,
                conditions=[
                    {
                        "condition_type": "time",
                        "operator": "equals",
                        "value": "night",
                    },
                ],
                actions=[
                    {
                        "action_type": "turn_off",
                        "parameters": {"target": "living_room_light"},
                    },
                    {
                        "action_type": "turn_off",
                        "parameters": {"target": "kitchen_light"},
                    },
                    {
                        "action_type": "set_brightness",
                        "parameters": {"target": "bedroom_light", "brightness": 10},
                        "delay": 2.0,
                    },
                    {
                        "action_type": "set_temperature",
                        "parameters": {"target": "thermostat", "value": 20},
                        "delay": 5.0,
                    },
                    {
                        "action_type": "arm_security",
                        "parameters": {"mode": "night"},
                        "delay": 10.0,
                    },
                ],
                exit_actions=[
                    {
                        "action_type": "disarm_security",
                        "parameters": {},
                    },
                ],
                priority=ScenarioPriority.HIGH,
            ),
            ScenarioTemplate(
                template_id="away",
                name="离家模式",
                description="离开家时的场景",
                scenario_type=ScenarioType.LOCATION_BASED,
                conditions=[
                    {
                        "condition_type": "location",
                        "operator": "not_equals",
                        "value": "home",
                    },
                ],
                actions=[
                    {
                        "action_type": "turn_off",
                        "parameters": {"target": "all_lights"},
                    },
                    {
                        "action_type": "set_temperature",
                        "parameters": {"target": "thermostat", "value": 18},
                        "delay": 2.0,
                    },
                    {
                        "action_type": "arm_security",
                        "parameters": {"mode": "away"},
                        "delay": 5.0,
                    },
                    {
                        "action_type": "close_cover",
                        "parameters": {"target": "curtains"},
                        "delay": 8.0,
                    },
                ],
                exit_actions=[
                    {
                        "action_type": "disarm_security",
                        "parameters": {},
                    },
                ],
                priority=ScenarioPriority.HIGH,
            ),
            ScenarioTemplate(
                template_id="home",
                name="回家模式",
                description="回到家时的场景",
                scenario_type=ScenarioType.LOCATION_BASED,
                conditions=[
                    {
                        "condition_type": "location",
                        "operator": "equals",
                        "value": "home",
                    },
                ],
                actions=[
                    {
                        "action_type": "disarm_security",
                        "parameters": {},
                    },
                    {
                        "action_type": "turn_on",
                        "parameters": {"target": "living_room_light"},
                        "delay": 2.0,
                    },
                    {
                        "action_type": "set_temperature",
                        "parameters": {"target": "thermostat", "value": 24},
                        "delay": 5.0,
                    },
                    {
                        "action_type": "notify",
                        "parameters": {"message": "欢迎回家！"},
                        "delay": 10.0,
                    },
                ],
                priority=ScenarioPriority.HIGH,
            ),
            ScenarioTemplate(
                template_id="relax",
                name="放松模式",
                description="放松休息时的场景",
                scenario_type=ScenarioType.MANUAL,
                conditions=[],
                actions=[
                    {
                        "action_type": "set_brightness",
                        "parameters": {"target": "living_room_light", "brightness": 50},
                    },
                    {
                        "action_type": "set_temperature",
                        "parameters": {"target": "thermostat", "value": 23},
                        "delay": 2.0,
                    },
                    {
                        "action_type": "play_music",
                        "parameters": {"playlist": "relax", "volume": 40},
                        "delay": 5.0,
                    },
                    {
                        "action_type": "open_cover",
                        "parameters": {"target": "curtains"},
                        "delay": 8.0,
                    },
                ],
                exit_actions=[
                    {
                        "action_type": "stop_music",
                        "parameters": {},
                    },
                ],
                priority=ScenarioPriority.MEDIUM,
            ),
            ScenarioTemplate(
                template_id="movie",
                name="观影模式",
                description="观看电影时的场景",
                scenario_type=ScenarioType.MANUAL,
                conditions=[],
                actions=[
                    {
                        "action_type": "turn_off",
                        "parameters": {"target": "ambient_lights"},
                    },
                    {
                        "action_type": "set_brightness",
                        "parameters": {"target": "tv_backlight", "brightness": 20},
                        "delay": 1.0,
                    },
                    {
                        "action_type": "turn_on",
                        "parameters": {"target": "tv"},
                        "delay": 2.0,
                    },
                    {
                        "action_type": "set_temperature",
                        "parameters": {"target": "thermostat", "value": 22},
                        "delay": 5.0,
                    },
                ],
                exit_actions=[
                    {
                        "action_type": "turn_off",
                        "parameters": {"target": "tv"},
                    },
                    {
                        "action_type": "turn_on",
                        "parameters": {"target": "ambient_lights"},
                    },
                ],
                priority=ScenarioPriority.MEDIUM,
            ),
            ScenarioTemplate(
                template_id="guest",
                name="客人模式",
                description="有客人来访时的场景",
                scenario_type=ScenarioType.USER_ACTIVITY,
                conditions=[
                    {
                        "condition_type": "user_presence",
                        "operator": "equals",
                        "value": True,
                        "parameters": {"user_id": "guest"},
                    },
                ],
                actions=[
                    {
                        "action_type": "set_brightness",
                        "parameters": {"target": "living_room_light", "brightness": 80},
                    },
                    {
                        "action_type": "play_music",
                        "parameters": {"playlist": "ambient", "volume": 35},
                        "delay": 2.0,
                    },
                    {
                        "action_type": "notify",
                        "parameters": {"message": "欢迎客人！"},
                        "delay": 5.0,
                    },
                ],
                priority=ScenarioPriority.MEDIUM,
            ),
            ScenarioTemplate(
                template_id="work",
                name="工作模式",
                description="在家工作时的场景",
                scenario_type=ScenarioType.MANUAL,
                conditions=[],
                actions=[
                    {
                        "action_type": "set_brightness",
                        "parameters": {"target": "desk_light", "brightness": 100},
                    },
                    {
                        "action_type": "set_temperature",
                        "parameters": {"target": "thermostat", "value": 22},
                        "delay": 2.0,
                    },
                    {
                        "action_type": "turn_on",
                        "parameters": {"target": "air_purifier"},
                        "delay": 5.0,
                    },
                ],
                exit_actions=[
                    {
                        "action_type": "turn_off",
                        "parameters": {"target": "desk_light"},
                    },
                ],
                priority=ScenarioPriority.MEDIUM,
            ),
        ]

        for template in templates:
            self.templates[template.template_id] = template

        logger.info(f"Initialized {len(templates)} scenario templates")

    async def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._evaluation_loop())
        logger.info("Scenario manager started")

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Scenario manager stopped")

    async def _evaluation_loop(self) -> None:
        while self._running:
            await self._evaluate_scenarios()
            await asyncio.sleep(5.0)

    async def _evaluate_scenarios(self) -> None:
        context = self._build_context()

        for scenario_id, scenario in self.scenarios.items():
            if scenario.state == ScenarioState.INACTIVE:
                if scenario.evaluate_conditions(context):
                    await self._activate_scenario(scenario_id, context)
            elif scenario.state == ScenarioState.ACTIVE:
                transition_target = scenario.check_transitions(context)
                if transition_target:
                    await self._deactivate_scenario(scenario_id, context)
                    await self._activate_scenario(transition_target, context)

    def _build_context(self) -> Dict[str, Any]:
        import datetime

        now = datetime.datetime.now()
        current_time = now.timestamp()
        hour = now.hour

        time_of_day = "day"
        if 5 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 18:
            time_of_day = "afternoon"
        elif 18 <= hour < 22:
            time_of_day = "evening"
        else:
            time_of_day = "night"

        return {
            "current_time": current_time,
            "time_of_day": time_of_day,
            "hour": hour,
            "weather": {},
            "user_location": "home",
            "user_presence": {},
            "device_states": {},
        }

    async def _activate_scenario(self, scenario_id: str, context: Dict[str, Any]) -> bool:
        scenario = self.scenarios.get(scenario_id)
        if not scenario:
            return False

        success = await scenario.activate(context)
        if success:
            self.active_scenarios.add(scenario_id)
            self._record_scenario_event(scenario, "activated")
            self._notify_listeners(scenario, "activated")

        return success

    async def _deactivate_scenario(self, scenario_id: str, context: Dict[str, Any]) -> bool:
        scenario = self.scenarios.get(scenario_id)
        if not scenario:
            return False

        success = await scenario.deactivate(context)
        if success:
            self.active_scenarios.discard(scenario_id)
            self._record_scenario_event(scenario, "deactivated")
            self._notify_listeners(scenario, "deactivated")

        return success

    def _record_scenario_event(self, scenario: Scenario, event_type: str) -> None:
        event = {
            "scenario_id": scenario.scenario_id,
            "scenario_name": scenario.name,
            "event_type": event_type,
            "timestamp": time.time(),
            "state": scenario.state.value,
        }
        self.scenario_history.append(event)

        if len(self.scenario_history) > self._max_history_size:
            self.scenario_history = self.scenario_history[-self._max_history_size:]

    def _notify_listeners(self, scenario: Scenario, event: str) -> None:
        for listener in self._listeners:
            try:
                listener(scenario, event)
            except Exception as e:
                logger.error(f"Error notifying scenario listener: {e}")

    def add_listener(self, listener: Callable[[Scenario, str], None]) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[Scenario, str], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def register_template(self, template: ScenarioTemplate) -> None:
        self.templates[template.template_id] = template
        logger.info(f"Registered scenario template: {template.name}")

    def unregister_template(self, template_id: str) -> bool:
        if template_id in self.templates:
            del self.templates[template_id]
            return True
        return False

    def create_scenario_from_template(
        self,
        template_id: str,
        name: str,
        parameter_values: Optional[Dict[str, Any]] = None
    ) -> Optional[Scenario]:
        template = self.templates.get(template_id)
        if not template:
            return None

        scenario = template.create_instance(name, parameter_values)
        self.scenarios[scenario.scenario_id] = scenario

        logger.info(f"Created scenario from template: {name}")
        return scenario

    def add_scenario(self, scenario: Scenario) -> None:
        self.scenarios[scenario.scenario_id] = scenario
        logger.info(f"Added scenario: {scenario.name}")

    def remove_scenario(self, scenario_id: str) -> bool:
        if scenario_id in self.scenarios:
            scenario = self.scenarios[scenario_id]
            if scenario.state == ScenarioState.ACTIVE:
                context = self._build_context()
                asyncio.create_task(self._deactivate_scenario(scenario_id, context))

            del self.scenarios[scenario_id]
            logger.info(f"Removed scenario: {scenario_id}")
            return True
        return False

    async def activate_scenario(self, scenario_id: str) -> bool:
        context = self._build_context()
        return await self._activate_scenario(scenario_id, context)

    async def deactivate_scenario(self, scenario_id: str) -> bool:
        context = self._build_context()
        return await self._deactivate_scenario(scenario_id, context)

    def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        return self.scenarios.get(scenario_id)

    def get_scenarios(self) -> List[Scenario]:
        return list(self.scenarios.values())

    def get_active_scenarios(self) -> List[Scenario]:
        return [
            self.scenarios[sid] for sid in self.active_scenarios
            if sid in self.scenarios
        ]

    def get_template(self, template_id: str) -> Optional[ScenarioTemplate]:
        return self.templates.get(template_id)

    def get_templates(self) -> List[ScenarioTemplate]:
        return list(self.templates.values())

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.scenario_history[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        total = len(self.scenarios)
        active = len(self.active_scenarios)
        by_type = {}
        by_state = {}

        for scenario in self.scenarios.values():
            type_name = scenario.scenario_type.value
            state_name = scenario.state.value

            by_type[type_name] = by_type.get(type_name, 0) + 1
            by_state[state_name] = by_state.get(state_name, 0) + 1

        activation_counts = {}
        for event in self.scenario_history:
            if event["event_type"] == "activated":
                scenario_name = event["scenario_name"]
                activation_counts[scenario_name] = activation_counts.get(scenario_name, 0) + 1

        most_used = sorted(activation_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_scenarios": total,
            "active_scenarios": active,
            "by_type": by_type,
            "by_state": by_state,
            "total_history_events": len(self.scenario_history),
            "most_used_scenarios": [{"name": name, "count": count} for name, count in most_used],
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenarios": [scenario.to_dict() for scenario in self.scenarios.values()],
            "templates": [template.to_dict() for template in self.templates.values()],
            "active_scenarios": list(self.active_scenarios),
            "statistics": self.get_statistics(),
        }

    def save_to_file(self, filepath: str) -> None:
        data = {
            "scenarios": [scenario.to_dict() for scenario in self.scenarios.values()],
            "templates": [template.to_dict() for template in self.templates.values()],
            "history": self.scenario_history,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Scenario manager saved to {filepath}")

    def load_from_file(self, filepath: str) -> None:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            for template_data in data.get("templates", []):
                template = ScenarioTemplate(**template_data)
                self.templates[template.template_id] = template

            logger.info(f"Scenario manager loaded from {filepath}")
        except Exception as e:
            logger.error(f"Error loading scenario manager from {filepath}: {e}")
