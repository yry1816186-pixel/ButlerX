from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum

class ActionType(Enum):
    SERVICE = "service"
    SCRIPT = "script"
    DELAY = "delay"
    NOTIFY = "notify"
    SCENE = "scene"
    ACTIVATE_SCENE = "activate_scene"
    DEACTIVATE_SCENE = "deactivate_scene"
    CHOOSE = "choose"
    PARALLEL = "parallel"
    REPEAT = "repeat"
    IF = "if"
    WAIT = "wait"
    TEMPLATE = "template"
    VARIABLES = "variables"
    EVENT = "event"
    LOG = "log"

@dataclass
class ActionResult:
    success: bool
    action_id: str
    action_type: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "error": self.error
        }

class Action(ABC):
    def __init__(self, action_id: str, action_type: ActionType):
        self.action_id = action_id
        self.action_type = action_type
        self._enabled = True
        self._metadata: Dict[str, Any] = {}

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    def set_metadata(self, key: str, value: Any):
        self._metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        return self._metadata.get(key, default)

class ServiceAction(Action):
    def __init__(
        self,
        action_id: str,
        service: str,
        entity_id: Optional[str] = None,
        service_data: Optional[Dict[str, Any]] = None,
        service_data_template: Optional[Dict[str, Any]] = None
    ):
        super().__init__(action_id, ActionType.SERVICE)
        self.service = service
        self.entity_id = entity_id
        self.service_data = service_data or {}
        self.service_data_template = service_data_template or {}

    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        if not self._enabled:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error="Action is disabled"
            )

        try:
            service_caller = context.get("service_caller")
            if not service_caller:
                return ActionResult(
                    success=False,
                    action_id=self.action_id,
                    action_type=self.action_type.value,
                    error="No service caller available in context"
                )

            data = self._resolve_templates(self.service_data, context)
            if self.service_data_template:
                template_data = self._resolve_templates(self.service_data_template, context)
                data.update(template_data)

            if self.entity_id:
                data["entity_id"] = self.entity_id

            result = await service_caller(self.service, data)

            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type.value,
                data={"service": self.service, "data": data, "result": result}
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error=str(e)
            )

    def _resolve_templates(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        from jinja2 import Template, TemplateError
        resolved = {}

        for key, value in data.items():
            if isinstance(value, str):
                try:
                    template = Template(value)
                    resolved[key] = template.render(**context)
                except (TemplateError, ValueError, KeyError):
                    resolved[key] = value
            else:
                resolved[key] = value

        return resolved

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "enabled": self._enabled,
            "service": self.service,
            "entity_id": self.entity_id,
            "service_data": self.service_data,
            "service_data_template": self.service_data_template,
            "metadata": self._metadata
        }

class ScriptAction(Action):
    def __init__(
        self,
        action_id: str,
        script_id: str,
        variables: Optional[Dict[str, Any]] = None
    ):
        super().__init__(action_id, ActionType.SCRIPT)
        self.script_id = script_id
        self.variables = variables or {}

    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        if not self._enabled:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error="Action is disabled"
            )

        try:
            script_executor = context.get("script_executor")
            if not script_executor:
                return ActionResult(
                    success=False,
                    action_id=self.action_id,
                    action_type=self.action_type.value,
                    error="No script executor available in context"
                )

            script_context = {**context, **self.variables}
            result = await script_executor(self.script_id, script_context)

            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type.value,
                data={"script_id": self.script_id, "result": result}
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error=str(e)
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "enabled": self._enabled,
            "script_id": self.script_id,
            "variables": self.variables,
            "metadata": self._metadata
        }

class DelayAction(Action):
    def __init__(
        self,
        action_id: str,
        delay: Union[float, str],
        delay_template: Optional[str] = None
    ):
        super().__init__(action_id, ActionType.DELAY)
        self.delay = delay
        self.delay_template = delay_template

    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        if not self._enabled:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error="Action is disabled"
            )

        try:
            import asyncio

            if self.delay_template:
                from jinja2 import Template
                template = Template(self.delay_template)
                delay_str = template.render(**context)
                delay_seconds = self._parse_delay(delay_str)
            elif isinstance(self.delay, str):
                delay_seconds = self._parse_delay(self.delay)
            else:
                delay_seconds = float(self.delay)

            await asyncio.sleep(delay_seconds)

            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type.value,
                data={"delay_seconds": delay_seconds}
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error=str(e)
            )

    def _parse_delay(self, delay_str: str) -> float:
        import re
        pattern = r'(?:(\d+)\s*(hours?|hrs?|h))\s*(?:(\d+)\s*(minutes?|mins?|m))?\s*(?:(\d+)\s*(seconds?|secs?|s))?'
        match = re.match(pattern, delay_str.lower())
        if not match:
            return float(delay_str)

        hours = int(match.group(1)) if match.group(1) else 0
        minutes = int(match.group(3)) if match.group(3) else 0
        seconds = int(match.group(5)) if match.group(5) else 0

        return hours * 3600 + minutes * 60 + seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "enabled": self._enabled,
            "delay": self.delay,
            "delay_template": self.delay_template,
            "metadata": self._metadata
        }

class NotifyAction(Action):
    def __init__(
        self,
        action_id: str,
        message: str,
        title: Optional[str] = None,
        target: Optional[str] = None,
        message_template: Optional[str] = None
    ):
        super().__init__(action_id, ActionType.NOTIFY)
        self.message = message
        self.title = title
        self.target = target
        self.message_template = message_template

    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        if not self._enabled:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error="Action is disabled"
            )

        try:
            notifier = context.get("notifier")
            if not notifier:
                return ActionResult(
                    success=False,
                    action_id=self.action_id,
                    action_type=self.action_type.value,
                    error="No notifier available in context"
                )

            if self.message_template:
                from jinja2 import Template
                template = Template(self.message_template)
                final_message = template.render(**context)
            else:
                final_message = self.message

            await notifier(
                message=final_message,
                title=self.title,
                target=self.target
            )

            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type.value,
                data={"message": final_message, "title": self.title, "target": self.target}
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error=str(e)
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "enabled": self._enabled,
            "message": self.message,
            "title": self.title,
            "target": self.target,
            "message_template": self.message_template,
            "metadata": self._metadata
        }

class SceneAction(Action):
    def __init__(
        self,
        action_id: str,
        scene_id: str,
        activate: bool = True
    ):
        super().__init__(action_id, ActionType.SCENE if activate else ActionType.SCRIPT)
        self.scene_id = scene_id
        self.activate = activate

    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        if not self._enabled:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error="Action is disabled"
            )

        try:
            scene_executor = context.get("scene_executor")
            if not scene_executor:
                return ActionResult(
                    success=False,
                    action_id=self.action_id,
                    action_type=self.action_type.value,
                    error="No scene executor available in context"
                )

            if self.activate:
                await scene_executor.activate_scene(self.scene_id)
            else:
                await scene_executor.deactivate_scene(self.scene_id)

            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type.value,
                data={"scene_id": self.scene_id, "activated": self.activate}
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error=str(e)
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "enabled": self._enabled,
            "scene_id": self.scene_id,
            "activate": self.activate,
            "metadata": self._metadata
        }

class ChooseAction(Action):
    def __init__(
        self,
        action_id: str,
        choices: List[Dict[str, Any]],
        default: Optional[List[Action]] = None
    ):
        super().__init__(action_id, ActionType.CHOOSE)
        self.choices = choices
        self.default = default or []

    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        if not self._enabled:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error="Action is disabled"
            )

        try:
            for choice in self.choices:
                conditions = choice.get("conditions", [])
                actions = choice.get("actions", [])

                all_met = True
                for condition in conditions:
                    if hasattr(condition, "evaluate"):
                        if not await condition.evaluate(context):
                            all_met = False
                            break

                if all_met:
                    results = []
                    for action in actions:
                        if hasattr(action, "execute"):
                            result = await action.execute(context)
                            results.append(result.to_dict())

                    return ActionResult(
                        success=True,
                        action_id=self.action_id,
                        action_type=self.action_type.value,
                        data={"choice_index": self.choices.index(choice), "results": results}
                    )

            if self.default:
                results = []
                for action in self.default:
                    if hasattr(action, "execute"):
                        result = await action.execute(context)
                        results.append(result.to_dict())

                return ActionResult(
                    success=True,
                    action_id=self.action_id,
                    action_type=self.action_type.value,
                    data={"choice": "default", "results": results}
                )

            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error="No matching choice found and no default action"
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error=str(e)
            )

    def to_dict(self) -> Dict[str, Any]:
        choices_data = []
        for choice in self.choices:
            choices_data.append({
                "conditions": [c.to_dict() if hasattr(c, "to_dict") else c for c in choice.get("conditions", [])],
                "actions": [a.to_dict() if hasattr(a, "to_dict") else a for a in choice.get("actions", [])]
            })

        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "enabled": self._enabled,
            "choices": choices_data,
            "default": [a.to_dict() if hasattr(a, "to_dict") else a for a in self.default],
            "metadata": self._metadata
        }

class ParallelAction(Action):
    def __init__(
        self,
        action_id: str,
        actions: List[Action],
        max_parallel: Optional[int] = None
    ):
        super().__init__(action_id, ActionType.PARALLEL)
        self.actions = actions
        self.max_parallel = max_parallel

    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        if not self._enabled:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error="Action is disabled"
            )

        try:
            import asyncio

            if self.max_parallel:
                semaphore = asyncio.Semaphore(self.max_parallel)

                async def execute_with_semaphore(action):
                    async with semaphore:
                        return await action.execute(context)

                tasks = [execute_with_semaphore(action) for action in self.actions]
            else:
                tasks = [action.execute(context) for action in self.actions]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            success_count = sum(1 for r in results if isinstance(r, ActionResult) and r.success)
            error_count = len(results) - success_count

            return ActionResult(
                success=error_count == 0,
                action_id=self.action_id,
                action_type=self.action_type.value,
                data={
                    "total_actions": len(self.actions),
                    "success_count": success_count,
                    "error_count": error_count,
                    "results": [r.to_dict() if isinstance(r, ActionResult) else {"error": str(r)} for r in results]
                }
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error=str(e)
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "enabled": self._enabled,
            "actions": [a.to_dict() if hasattr(a, "to_dict") else a for a in self.actions],
            "max_parallel": self.max_parallel,
            "metadata": self._metadata
        }

class RepeatAction(Action):
    def __init__(
        self,
        action_id: str,
        repeat: Union[int, str],
        sequence: List[Action],
        repeat_template: Optional[str] = None
    ):
        super().__init__(action_id, ActionType.REPEAT)
        self.repeat = repeat
        self.sequence = sequence
        self.repeat_template = repeat_template

    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        if not self._enabled:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error="Action is disabled"
            )

        try:
            if self.repeat_template:
                from jinja2 import Template
                template = Template(self.repeat_template)
                repeat_str = template.render(**context)
                count = int(repeat_str)
            elif isinstance(self.repeat, str):
                count = int(self.repeat)
            else:
                count = self.repeat

            all_results = []
            for i in range(count):
                loop_context = {**context, "repeat_index": i, "repeat_count": count}
                for action in self.sequence:
                    result = await action.execute(loop_context)
                    all_results.append(result.to_dict())

            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type.value,
                data={"repeat_count": count, "results": all_results}
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error=str(e)
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "enabled": self._enabled,
            "repeat": self.repeat,
            "repeat_template": self.repeat_template,
            "sequence": [a.to_dict() if hasattr(a, "to_dict") else a for a in self.sequence],
            "metadata": self._metadata
        }

class TemplateAction(Action):
    def __init__(
        self,
        action_id: str,
        value_template: str
    ):
        super().__init__(action_id, ActionType.TEMPLATE)
        self.value_template = value_template

    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        if not self._enabled:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error="Action is disabled"
            )

        try:
            from jinja2 import Template
            template = Template(self.value_template)
            result = template.render(**context)

            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type.value,
                data={"result": result}
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error=str(e)
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "enabled": self._enabled,
            "value_template": self.value_template,
            "metadata": self._metadata
        }

class LogAction(Action):
    def __init__(
        self,
        action_id: str,
        message: str,
        level: str = "info"
    ):
        super().__init__(action_id, ActionType.LOG)
        self.message = message
        self.level = level

    async def execute(self, context: Dict[str, Any]) -> ActionResult:
        try:
            from jinja2 import Template
            template = Template(self.message)
            log_message = template.render(**context)

            logger = context.get("logger")
            if logger:
                if self.level == "debug":
                    logger.debug(log_message)
                elif self.level == "info":
                    logger.info(log_message)
                elif self.level == "warning":
                    logger.warning(log_message)
                elif self.level == "error":
                    logger.error(log_message)

            return ActionResult(
                success=True,
                action_id=self.action_id,
                action_type=self.action_type.value,
                data={"message": log_message, "level": self.level}
            )

        except Exception as e:
            return ActionResult(
                success=False,
                action_id=self.action_id,
                action_type=self.action_type.value,
                error=str(e)
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "enabled": self._enabled,
            "message": self.message,
            "level": self.level,
            "metadata": self._metadata
        }
