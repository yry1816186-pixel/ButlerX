from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Union
from enum import Enum
import json
import uuid
from datetime import datetime

from .trigger import Trigger, TriggerType, TriggerConfig, StateTrigger, TimeTrigger, EventTrigger
from .condition import Condition, ConditionType, ConditionConfig, StateCondition, AndCondition, OrCondition, NotCondition
from .action import Action, ActionType, ServiceAction, DelayAction, NotifyAction

class BlueprintParameterType(Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENTITY = "entity"
    DEVICE = "device"
    SELECT = "select"
    TIME = "time"
    DATE = "date"

@dataclass
class BlueprintParameter:
    name: str
    parameter_type: BlueprintParameterType
    default: Any = None
    required: bool = False
    description: Optional[str] = None
    options: Optional[List[Any]] = None
    min: Optional[Union[int, float]] = None
    max: Optional[Union[int, float]] = None
    selector: Optional[Dict[str, Any]] = None

    def validate(self, value: Any) -> bool:
        if value is None:
            return not self.required

        try:
            if self.parameter_type == BlueprintParameterType.STRING:
                if not isinstance(value, str):
                    return False

            elif self.parameter_type == BlueprintParameterType.NUMBER:
                num_value = float(value)
                if self.min is not None and num_value < self.min:
                    return False
                if self.max is not None and num_value > self.max:
                    return False

            elif self.parameter_type == BlueprintParameterType.BOOLEAN:
                if not isinstance(value, bool):
                    return False

            elif self.parameter_type == BlueprintParameterType.ENTITY:
                if not isinstance(value, str) or "." not in value:
                    return False

            elif self.parameter_type == BlueprintParameterType.SELECT:
                if self.options and value not in self.options:
                    return False

            return True

        except (ValueError, TypeError):
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.parameter_type.value,
            "default": self.default,
            "required": self.required,
            "description": self.description,
            "options": self.options,
            "min": self.min,
            "max": self.max,
            "selector": self.selector
        }

@dataclass
class BlueprintInput:
    parameters: Dict[str, BlueprintParameter] = field(default_factory=dict)
    triggers: List[Dict[str, Any]] = field(default_factory=list)
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameters": {name: param.to_dict() for name, param in self.parameters.items()},
            "triggers": self.triggers,
            "conditions": self.conditions,
            "actions": self.actions
        }

class Blueprint:
    def __init__(
        self,
        blueprint_id: str,
        name: str,
        description: str,
        domain: Optional[str] = None,
        author: Optional[str] = None,
        version: str = "1.0.0"
    ):
        self.blueprint_id = blueprint_id
        self.name = name
        self.description = description
        self.domain = domain
        self.author = author
        self.version = version
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.parameters: Dict[str, BlueprintParameter] = {}
        self.input = BlueprintInput()
        self._instances: Dict[str, Dict[str, Any]] = {}

    def add_parameter(
        self,
        name: str,
        parameter_type: BlueprintParameterType,
        default: Any = None,
        required: bool = False,
        description: Optional[str] = None,
        options: Optional[List[Any]] = None,
        min: Optional[Union[int, float]] = None,
        max: Optional[Union[int, float]] = None
    ) -> Blueprint:
        param = BlueprintParameter(
            name=name,
            parameter_type=parameter_type,
            default=default,
            required=required,
            description=description,
            options=options,
            min=min,
            max=max
        )
        self.parameters[name] = param
        self.input.parameters[name] = param
        self.updated_at = datetime.now()
        return self

    def add_trigger(self, trigger_config: Dict[str, Any]) -> Blueprint:
        self.input.triggers.append(trigger_config)
        self.updated_at = datetime.now()
        return self

    def add_condition(self, condition_config: Dict[str, Any]) -> Blueprint:
        self.input.conditions.append(condition_config)
        self.updated_at = datetime.now()
        return self

    def add_action(self, action_config: Dict[str, Any]) -> Blueprint:
        self.input.actions.append(action_config)
        self.updated_at = datetime.now()
        return self

    def create_instance(
        self,
        name: str,
        parameter_values: Dict[str, Any],
        automation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if automation_id is None:
            automation_id = f"{self.blueprint_id}_{uuid.uuid4().hex[:8]}"

        for param_name, param in self.parameters.items():
            value = parameter_values.get(param_name, param.default)
            if not param.validate(value):
                raise ValueError(f"Invalid value for parameter '{param_name}': {value}")

        instance = {
            "automation_id": automation_id,
            "name": name,
            "blueprint_id": self.blueprint_id,
            "parameter_values": parameter_values,
            "created_at": datetime.now().isoformat()
        }

        self._instances[automation_id] = instance
        return instance

    def get_instance(self, automation_id: str) -> Optional[Dict[str, Any]]:
        return self._instances.get(automation_id)

    def get_all_instances(self) -> List[Dict[str, Any]]:
        return list(self._instances.values())

    def delete_instance(self, automation_id: str) -> bool:
        if automation_id in self._instances:
            del self._instances[automation_id]
            return True
        return False

    def update_instance(
        self,
        automation_id: str,
        parameter_values: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if automation_id not in self._instances:
            return None

        for param_name, param in self.parameters.items():
            value = parameter_values.get(param_name, param.default)
            if not param.validate(value):
                raise ValueError(f"Invalid value for parameter '{param_name}': {value}")

        self._instances[automation_id]["parameter_values"] = parameter_values
        self._instances[automation_id]["updated_at"] = datetime.now().isoformat()
        return self._instances[automation_id]

    def instantiate_triggers(self, parameter_values: Dict[str, Any]) -> List[Trigger]:
        triggers = []
        for i, trigger_config in enumerate(self.input.triggers):
            resolved_config = self._resolve_config(trigger_config, parameter_values)
            trigger = self._create_trigger_from_config(resolved_config, f"trigger_{i}")
            if trigger:
                triggers.append(trigger)
        return triggers

    def instantiate_conditions(self, parameter_values: Dict[str, Any]) -> List[Condition]:
        conditions = []
        for i, condition_config in enumerate(self.input.conditions):
            resolved_config = self._resolve_config(condition_config, parameter_values)
            condition = self._create_condition_from_config(resolved_config, f"condition_{i}")
            if condition:
                conditions.append(condition)
        return conditions

    def instantiate_actions(self, parameter_values: Dict[str, Any]) -> List[Action]:
        actions = []
        for i, action_config in enumerate(self.input.actions):
            resolved_config = self._resolve_config(action_config, parameter_values)
            action = self._create_action_from_config(resolved_config, f"action_{i}")
            if action:
                actions.append(action)
        return actions

    def _resolve_config(self, config: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        resolved = {}
        for key, value in config.items():
            if isinstance(value, str) and value.startswith("!input "):
                param_name = value[7:]
                resolved[key] = parameters.get(param_name)
            elif isinstance(value, dict):
                resolved[key] = self._resolve_config(value, parameters)
            elif isinstance(value, list):
                resolved[key] = [
                    self._resolve_config(item, parameters) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                resolved[key] = value
        return resolved

    def _create_trigger_from_config(self, config: Dict[str, Any], trigger_id: str) -> Optional[Trigger]:
        trigger_config = TriggerConfig(
            trigger_id=trigger_id,
            trigger_type=TriggerType(config.get("platform", "state")),
            enabled=config.get("enabled", True),
            cooldown=config.get("cooldown"),
            for_duration=config.get("for"),
            variables=config.get("variables", {})
        )

        platform = trigger_config.trigger_type

        if platform == TriggerType.STATE:
            return StateTrigger(
                config=trigger_config,
                entity_id=config.get("entity_id"),
                from_state=config.get("from"),
                to_state=config.get("to"),
                for_duration=config.get("for"),
                attribute=config.get("attribute")
            )

        elif platform == TriggerType.TIME:
            return TimeTrigger(
                config=trigger_config,
                at=config.get("at"),
                after=config.get("after"),
                before=config.get("before"),
                weekday=config.get("weekday"),
                interval=config.get("interval")
            )

        elif platform == TriggerType.EVENT:
            return EventTrigger(
                config=trigger_config,
                event_type=config.get("event_type"),
                event_data=config.get("event_data")
            )

        return None

    def _create_condition_from_config(self, config: Dict[str, Any], condition_id: str) -> Optional[Condition]:
        condition_config = ConditionConfig(
            condition_id=condition_id,
            condition_type=ConditionType(config.get("condition", "state")),
            enabled=config.get("enabled", True),
            variables=config.get("variables", {})
        )

        condition_type = condition_config.condition_type

        if condition_type == ConditionType.AND:
            conditions = [self._create_condition_from_config(c, f"{condition_id}_{i}")
                          for i, c in enumerate(config.get("conditions", []))]
            return AndCondition(config=condition_config, conditions=conditions)

        elif condition_type == ConditionType.OR:
            conditions = [self._create_condition_from_config(c, f"{condition_id}_{i}")
                          for i, c in enumerate(config.get("conditions", []))]
            return OrCondition(config=condition_config, conditions=conditions)

        elif condition_type == ConditionType.NOT:
            inner = self._create_condition_from_config(config.get("condition", {}), f"{condition_id}_inner")
            return NotCondition(config=condition_config, condition=inner)

        elif condition_type == ConditionType.STATE:
            return StateCondition(
                config=condition_config,
                entity_id=config.get("entity_id"),
                state=config.get("state"),
                state_not=config.get("state_not"),
                for_duration=config.get("for"),
                attribute=config.get("attribute"),
                match=config.get("match")
            )

        return None

    def _create_action_from_config(self, config: Dict[str, Any], action_id: str) -> Optional[Action]:
        action_type = ActionType(config.get("action", "service"))

        if action_type == ActionType.SERVICE:
            return ServiceAction(
                action_id=action_id,
                service=config.get("service"),
                entity_id=config.get("entity_id"),
                service_data=config.get("data", {}),
                service_data_template=config.get("data_template", {})
            )

        elif action_type == ActionType.DELAY:
            return DelayAction(
                action_id=action_id,
                delay=config.get("delay", 0),
                delay_template=config.get("delay_template")
            )

        elif action_type == ActionType.NOTIFY:
            return NotifyAction(
                action_id=action_id,
                message=config.get("message", ""),
                title=config.get("title"),
                target=config.get("target"),
                message_template=config.get("message_template")
            )

        return None

    def to_dict(self, include_instances: bool = False) -> Dict[str, Any]:
        data = {
            "blueprint_id": self.blueprint_id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "author": self.author,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "input": self.input.to_dict(),
            "instance_count": len(self._instances)
        }

        if include_instances:
            data["instances"] = list(self._instances.values())

        return data

    def to_json(self, include_instances: bool = False) -> str:
        return json.dumps(self.to_dict(include_instances), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Blueprint:
        blueprint = cls(
            blueprint_id=data["blueprint_id"],
            name=data["name"],
            description=data["description"],
            domain=data.get("domain"),
            author=data.get("author"),
            version=data.get("version", "1.0.0")
        )

        if "input" in data:
            input_data = data["input"]
            for param_name, param_data in input_data.get("parameters", {}).items():
                param_type = BlueprintParameterType(param_data["type"])
                blueprint.parameters[param_name] = BlueprintParameter(
                    name=param_name,
                    parameter_type=param_type,
                    default=param_data.get("default"),
                    required=param_data.get("required", False),
                    description=param_data.get("description"),
                    options=param_data.get("options"),
                    min=param_data.get("min"),
                    max=param_data.get("max")
                )

            blueprint.input.triggers = input_data.get("triggers", [])
            blueprint.input.conditions = input_data.get("conditions", [])
            blueprint.input.actions = input_data.get("actions", [])

        return blueprint

    @classmethod
    def from_json(cls, json_str: str) -> Blueprint:
        return cls.from_dict(json.loads(json_str))

class BlueprintTemplate:
    def __init__(self):
        self._blueprints: Dict[str, Blueprint] = {}

    def register(self, blueprint: Blueprint) -> bool:
        if blueprint.blueprint_id in self._blueprints:
            return False
        self._blueprints[blueprint.blueprint_id] = blueprint
        return True

    def unregister(self, blueprint_id: str) -> bool:
        if blueprint_id in self._blueprints:
            del self._blueprints[blueprint_id]
            return True
        return False

    def get(self, blueprint_id: str) -> Optional[Blueprint]:
        return self._blueprints.get(blueprint_id)

    def get_all(self) -> List[Blueprint]:
        return list(self._blueprints.values())

    def search(self, **filters) -> List[Blueprint]:
        results = list(self._blueprints.values())

        if "domain" in filters:
            results = [b for b in results if b.domain == filters["domain"]]

        if "name" in filters:
            name_filter = filters["name"].lower()
            results = [b for b in results if name_filter in b.name.lower()]

        if "author" in filters:
            author_filter = filters["author"].lower()
            results = [b for b in results if b.author and author_filter in b.author.lower()]

        return results

    def get_statistics(self) -> Dict[str, Any]:
        total_instances = sum(len(b.get_all_instances()) for b in self._blueprints.values())
        domains = {}
        for blueprint in self._blueprints.values():
            if blueprint.domain:
                domains[blueprint.domain] = domains.get(blueprint.domain, 0) + 1

        return {
            "total_blueprints": len(self._blueprints),
            "total_instances": total_instances,
            "by_domain": domains
        }
