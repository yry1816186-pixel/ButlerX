from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
import uuid
from enum import Enum

from .trigger import Trigger, TriggerConfig, StateTrigger, TimeTrigger, EventTrigger
from .condition import Condition, ConditionConfig, StateCondition, AndCondition, OrCondition
from .action import Action, ActionResult, ServiceAction, DelayAction, NotifyAction, ParallelAction
from .blueprint import Blueprint, BlueprintTemplate

from ..core.entity_model import Entity, Automation

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    SINGLE = "single"
    RESTART = "restart"
    QUEUED = "queued"
    PARALLEL = "parallel"


@dataclass
class AutomationConfig:
    automation_id: str
    name: str
    description: Optional[str] = None
    enabled: bool = True
    mode: str = "single"  # single, restart, queued, parallel
    max_exceeded: str = "silent"  # silent, warn, error
    trigger_id: Optional[str] = None
    blueprint_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "automation_id": self.automation_id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "mode": self.mode,
            "max_exceeded": self.max_exceeded,
            "trigger_id": self.trigger_id,
            "blueprint_id": self.blueprint_id
        }

@dataclass
class AutomationState:
    is_running: bool = False
    last_triggered: Optional[datetime] = None
    last_triggered_by: Optional[str] = None
    trigger_count: int = 0
    action_count: int = 0
    success_count: int = 0
    error_count: int = 0
    current_action: Optional[str] = None
    current_action_start: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "last_triggered_by": self.last_triggered_by,
            "trigger_count": self.trigger_count,
            "action_count": self.action_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "current_action": self.current_action,
            "current_action_start": self.current_action_start.isoformat() if self.current_action_start else None
        }

@dataclass
class AutomationStatistics:
    total_triggers: int = 0
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    last_triggered: Optional[datetime] = None
    last_run: Optional[datetime] = None
    average_run_time: float = 0.0

    def get_success_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.successful_runs / self.total_runs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_triggers": self.total_triggers,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "average_run_time": self.average_run_time,
            "success_rate": self.get_success_rate()
        }

class AutomationStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    DISABLED = "disabled"

@dataclass
class AutomationExecution:
    execution_id: str
    automation_id: str
    started_at: datetime
    triggered_by: str
    context: Dict[str, Any]
    state: AutomationState = field(default_factory=AutomationState)
    results: List[ActionResult] = field(default_factory=list)
    completed: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "automation_id": self.automation_id,
            "started_at": self.started_at.isoformat(),
            "triggered_by": self.triggered_by,
            "context": self.context,
            "state": self.state.to_dict(),
            "results": [r.to_dict() for r in self.results],
            "completed": self.completed,
            "error": self.error
        }

class AutomationEntity(Automation):
    def __init__(
        self,
        config: AutomationConfig,
        triggers: List[Trigger],
        conditions: List[Condition],
        actions: List[Action]
    ):
        super().__init__(
            entity_id=config.automation_id,
            name=config.name,
            triggers=[t.to_dict() for t in triggers],
            conditions=[c.to_dict() for c in conditions],
            actions=[a.to_dict() for a in actions],
            metadata={"description": config.description, "mode": config.mode}
        )
        self.config = config
        self.triggers = triggers
        self.conditions = conditions
        self.actions = actions
        self.state = AutomationState()
        self._execution_history: List[AutomationExecution] = []
        self._current_execution: Optional[AutomationExecution] = None
        self._running_executions: Set[str] = set()

    @property
    def is_running(self) -> bool:
        return self.state.is_running

    def enable(self):
        super().enable()
        self.config.enabled = True
        logger.info(f"Automation {self.config.automation_id} enabled")

    def disable(self):
        super().disable()
        self.config.enabled = False
        logger.info(f"Automation {self.config.automation_id} disabled")

    def trigger(self) -> bool:
        result = super().trigger()
        if result:
            self.state.last_triggered = datetime.now()
            self.state.trigger_count += 1
        return result

    def get_execution_history(self, limit: int = 10) -> List[AutomationExecution]:
        return self._execution_history[-limit:]

    def get_current_execution(self) -> Optional[AutomationExecution]:
        return self._current_execution

class AutomationExecutor:
    def __init__(self):
        self._executor_id = str(uuid.uuid4())[:8]
        self._active: bool = True

    async def execute(
        self,
        automation: AutomationEntity,
        context: Dict[str, Any],
        triggered_by: str
    ) -> AutomationExecution:
        execution_id = f"{automation.config.automation_id}_{self._executor_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        execution = AutomationExecution(
            execution_id=execution_id,
            automation_id=automation.config.automation_id,
            started_at=datetime.now(),
            triggered_by=triggered_by,
            context=context
        )

        automation._current_execution = execution
        automation.state.is_running = True
        automation.state.last_triggered = datetime.now()
        automation.state.last_triggered_by = triggered_by

        try:
            mode = automation.config.mode

            if mode == "single":
                if automation._running_executions:
                    self._handle_max_exceeded(automation, execution)
                    return execution
                automation._running_executions.add(execution_id)

            elif mode == "restart":
                for running_id in list(automation._running_executions):
                    await self._cancel_execution(automation, running_id)
                automation._running_executions = {execution_id}

            elif mode == "queued":
                automation._running_executions.add(execution_id)
                await self._wait_for_turn(automation, execution_id)

            elif mode == "parallel":
                automation._running_executions.add(execution_id)

            logger.info(f"Starting execution {execution_id} for automation {automation.config.automation_id}")

            if not await self._check_conditions(automation.conditions, context):
                execution.completed = True
                execution.error = "Conditions not met"
                logger.info(f"Execution {execution_id} skipped: conditions not met")
                return execution

            for action in automation.actions:
                if not self._active:
                    execution.error = "Executor stopped"
                    break

                automation.state.current_action = action.action_id
                automation.state.current_action_start = datetime.now()

                try:
                    result = await action.execute(context)
                    execution.results.append(result)
                    automation.state.action_count += 1

                    if result.success:
                        automation.state.success_count += 1
                    else:
                        automation.state.error_count += 1
                        logger.error(f"Action {action.action_id} failed: {result.error}")

                except Exception as e:
                    error_result = ActionResult(
                        success=False,
                        action_id=action.action_id,
                        action_type=action.action_type.value,
                        error=str(e)
                    )
                    execution.results.append(error_result)
                    automation.state.error_count += 1
                    logger.exception(f"Action {action.action_id} raised exception")

            automation.state.trigger_count += 1
            execution.completed = True

            logger.info(
                f"Execution {execution_id} completed. "
                f"Actions: {len(execution.results)}, "
                f"Success: {automation.state.success_count}, "
                f"Errors: {automation.state.error_count}"
            )

        except Exception as e:
            execution.error = str(e)
            execution.completed = True
            logger.exception(f"Execution {execution_id} failed with exception")

        finally:
            automation._running_executions.discard(execution_id)
            automation.state.is_running = False
            automation.state.current_action = None
            automation.state.current_action_start = None
            automation._current_execution = None
            automation._execution_history.append(execution)

            if len(automation._execution_history) > 100:
                automation._execution_history = automation._execution_history[-100:]

        return execution

    async def _check_conditions(
        self,
        conditions: List[Condition],
        context: Dict[str, Any]
    ) -> bool:
        for condition in conditions:
            try:
                if not await condition.evaluate(context):
                    return False
            except Exception as e:
                logger.error(f"Condition evaluation failed: {e}")
                return False
        return True

    def _handle_max_exceeded(
        self,
        automation: AutomationEntity,
        execution: AutomationExecution
    ):
        max_exceeded = automation.config.max_exceeded

        if max_exceeded == "silent":
            execution.completed = True
            execution.error = "Max exceeded - silent"

        elif max_exceeded == "warn":
            logger.warning(f"Automation {automation.config.automation_id} max exceeded")
            execution.completed = True
            execution.error = "Max exceeded - warned"

        elif max_exceeded == "error":
            logger.error(f"Automation {automation.config.automation_id} max exceeded")
            execution.completed = True
            execution.error = "Max exceeded - error"

    async def _cancel_execution(self, automation: AutomationEntity, execution_id: str):
        logger.info(f"Cancelling execution {execution_id}")
        automation._running_executions.discard(execution_id)

    async def _wait_for_turn(self, automation: AutomationEntity, execution_id: str):
        while len(automation._running_executions) > 1:
            await asyncio.sleep(0.1)

    def stop(self):
        self._active = False

class AutomationEngine:
    def __init__(self):
        self._automations: Dict[str, AutomationEntity] = {}
        self._executors: Dict[str, AutomationExecutor] = {}
        self._blueprint_template = BlueprintTemplate()
        self._context: Dict[str, Any] = {}
        self._service_caller: Optional[Callable] = None
        self._script_executor: Optional[Callable] = None
        self._notifier: Optional[Callable] = None
        self._scene_executor: Optional[Callable] = None
        self._change_listeners: List[Callable] = []
        self._running = False
        self._check_interval = 1.0

    def register_automation(
        self,
        config: AutomationConfig,
        triggers: List[Trigger],
        conditions: List[Condition],
        actions: List[Action]
    ) -> AutomationEntity:
        if config.automation_id in self._automations:
            raise ValueError(f"Automation {config.automation_id} already registered")

        automation = AutomationEntity(config, triggers, conditions, actions)
        automation.register()
        self._automations[config.automation_id] = automation

        for trigger in triggers:
            trigger.add_callback(self._on_trigger)

        logger.info(f"Registered automation: {config.automation_id} - {config.name}")

        self._notify_listeners()

        return automation

    def unregister_automation(self, automation_id: str) -> bool:
        if automation_id not in self._automations:
            return False

        automation = self._automations[automation_id]
        automation.unregister()

        for trigger in automation.triggers:
            trigger.remove_callback(self._on_trigger)

        del self._automations[automation_id]

        if automation_id in self._executors:
            del self._executors[automation_id]

        logger.info(f"Unregistered automation: {automation_id}")

        self._notify_listeners()

        return True

    def get_automation(self, automation_id: str) -> Optional[AutomationEntity]:
        return self._automations.get(automation_id)

    def get_all_automations(self) -> List[AutomationEntity]:
        return list(self._automations.values())

    def enable_automation(self, automation_id: str) -> bool:
        automation = self._automations.get(automation_id)
        if automation:
            automation.enable()
            return True
        return False

    def disable_automation(self, automation_id: str) -> bool:
        automation = self._automations.get(automation_id)
        if automation:
            automation.disable()
            return True
        return False

    def trigger_automation(self, automation_id: str, context: Dict[str, Any]) -> bool:
        automation = self._automations.get(automation_id)
        if not automation or not automation.config.enabled:
            return False

        return automation.trigger()

    async def _on_trigger(self, trigger_data: Dict[str, Any]):
        automation_id = trigger_data.get("automation_id")
        if not automation_id:
            return

        automation = self._automations.get(automation_id)
        if not automation or not automation.config.enabled:
            return

        trigger_id = trigger_data.get("trigger_id")

        for trigger in automation.triggers:
            if trigger.config.trigger_id == trigger_id:
                if trigger_id == automation.config.trigger_id:
                    await self._execute_automation(automation, trigger_data)
                break

    async def _execute_automation(
        self,
        automation: AutomationEntity,
        trigger_data: Dict[str, Any]
    ) -> AutomationExecution:
        if automation.config.automation_id not in self._executors:
            self._executors[automation.config.automation_id] = AutomationExecutor()

        executor = self._executors[automation.config.automation_id]

        context = {
            **self._context,
            "trigger": trigger_data,
            "entities": {eid: entity.to_dict() for eid, entity in Entity.get_all()},
            "service_caller": self._service_caller,
            "script_executor": self._script_executor,
            "notifier": self._notifier,
            "scene_executor": self._scene_executor,
            "logger": logger
        }

        return await executor.execute(
            automation=automation,
            context=context,
            triggered_by=trigger_data.get("trigger_id", "unknown")
        )

    def register_blueprint(self, blueprint: Blueprint) -> bool:
        return self._blueprint_template.register(blueprint)

    def unregister_blueprint(self, blueprint_id: str) -> bool:
        return self._blueprint_template.unregister(blueprint_id)

    def get_blueprint(self, blueprint_id: str) -> Optional[Blueprint]:
        return self._blueprint_template.get(blueprint_id)

    def get_all_blueprints(self) -> List[Blueprint]:
        return self._blueprint_template.get_all()

    def create_automation_from_blueprint(
        self,
        blueprint_id: str,
        name: str,
        parameter_values: Dict[str, Any]
    ) -> Optional[AutomationEntity]:
        blueprint = self._blueprint_template.get(blueprint_id)
        if not blueprint:
            return None

        instance = blueprint.create_instance(name, parameter_values)

        triggers = blueprint.instantiate_triggers(parameter_values)
        conditions = blueprint.instantiate_conditions(parameter_values)
        actions = blueprint.instantiate_actions(parameter_values)

        config = AutomationConfig(
            automation_id=instance["automation_id"],
            name=name,
            description=f"Created from blueprint: {blueprint.name}",
            blueprint_id=blueprint_id
        )

        return self.register_automation(config, triggers, conditions, actions)

    def set_context(self, context: Dict[str, Any]):
        self._context.update(context)

    def update_context(self, key: str, value: Any):
        self._context[key] = value

    def set_service_caller(self, caller: Callable):
        self._service_caller = caller

    def set_script_executor(self, executor: Callable):
        self._script_executor = executor

    def set_notifier(self, notifier: Callable):
        self._notifier = notifier

    def set_scene_executor(self, executor: Callable):
        self._scene_executor = executor

    def register_change_listener(self, listener: Callable):
        if listener not in self._change_listeners:
            self._change_listeners.append(listener)

    def unregister_change_listener(self, listener: Callable):
        if listener in self._change_listeners:
            self._change_listeners.remove(listener)

    def _notify_listeners(self):
        for listener in self._change_listeners:
            try:
                listener(self)
            except Exception as e:
                logger.error(f"Change listener error: {e}")

    async def start(self):
        if self._running:
            return

        self._running = True

        async def check_triggers():
            while self._running:
                try:
                    for automation in self._automations.values():
                        if not automation.config.enabled:
                            continue

                        for trigger in automation.triggers:
                            context = {
                                **self._context,
                                "entities": {eid: entity.to_dict() for eid, entity in Entity.get_all()},
                                "event": self._context.get("event"),
                                "mqtt_message": self._context.get("mqtt_message"),
                                "sun_events": self._context.get("sun_events", {})
                            }
                            await trigger.trigger(context)

                except Exception as e:
                    logger.exception(f"Error checking triggers: {e}")

                await asyncio.sleep(self._check_interval)

        asyncio.create_task(check_triggers())
        logger.info("Automation engine started")

    async def stop(self):
        if not self._running:
            return

        self._running = False

        for executor in self._executors.values():
            executor.stop()

        logger.info("Automation engine stopped")

    def get_statistics(self) -> Dict[str, Any]:
        total_triggers = sum(a.state.trigger_count for a in self._automations.values())
        total_actions = sum(a.state.action_count for a in self._automations.values())
        total_success = sum(a.state.success_count for a in self._automations.values())
        total_errors = sum(a.state.error_count for a in self._automations.values())

        running_count = sum(1 for a in self._automations.values() if a.is_running)
        enabled_count = sum(1 for a in self._automations.values() if a.config.enabled)

        return {
            "total_automations": len(self._automations),
            "enabled_automations": enabled_count,
            "disabled_automations": len(self._automations) - enabled_count,
            "running_automations": running_count,
            "total_blueprints": len(self._blueprint_template.get_all()),
            "total_triggers": total_triggers,
            "total_actions": total_actions,
            "total_success": total_success,
            "total_errors": total_errors,
            "success_rate": total_success / total_actions if total_actions > 0 else 0
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "automations": [a.to_dict() for a in self._automations.values()],
            "blueprints": [b.to_dict() for b in self._blueprint_template.get_all()],
            "statistics": self.get_statistics(),
            "running": self._running
        }
