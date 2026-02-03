from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .goal_templates import GoalTemplateRegistry, GoalTemplate
from .composite_goal import (
    CompositeGoal, CompositeGoalExecutor, SubGoalConfig,
    GoalRelation, GoalRelationType, SubGoalStrategy
)
from .goal_conflict_resolver import (
    GoalConflictResolver, ConflictResolutionStrategy,
    ConflictSeverity, GoalConflict, ConflictResolution
)
from .goal_priority_manager import (
    GoalPriorityManager, PriorityFactor, PriorityAdjustment
)
from .adaptive_goal import (
    AdaptiveGoalManager, AdaptationTrigger, AdaptationAction,
    AdaptationEvent, AdaptationResult, LearningData
)

logger = logging.getLogger(__name__)


class GoalStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEFERRED = "deferred"
    ABORTED = "aborted"
    ACTIVE = "active"
    PAUSED = "paused"

class GoalState(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEFERRED = "deferred"
    ABORTED = "aborted"
    ACTIVE = "active"
    PAUSED = "paused"

@dataclass
class GoalStatistics:
    total_goals: int = 0
    active_goals: int = 0
    completed_goals: int = 0
    failed_goals: int = 0
    cancelled_goals: int = 0
    deferred_goals: int = 0
    success_rate: float = 0.0
    average_completion_time: float = 0.0
    last_goal_completed: Optional[datetime] = None
    last_goal_failed: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_goals": self.total_goals,
            "active_goals": self.active_goals,
            "completed_goals": self.completed_goals,
            "failed_goals": self.failed_goals,
            "cancelled_goals": self.cancelled_goals,
            "deferred_goals": self.deferred_goals,
            "success_rate": self.success_rate,
            "average_completion_time": self.average_completion_time,
            "last_goal_completed": self.last_goal_completed.isoformat() if self.last_goal_completed else None,
            "last_goal_failed": self.last_goal_failed.isoformat() if self.last_goal_failed else None
        }


@dataclass
class GoalConfig:
    goal_id: str
    template_id: str
    name: str
    description: Optional[str] = None
    priority: int = 0
    enabled: bool = True
    auto_start: bool = False
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority,
            "enabled": self.enabled,
            "auto_start": self.auto_start,
            "conditions": self.conditions,
            "metadata": self.metadata,
        }


@dataclass
class Goal:
    goal_id: str
    template_id: str
    name: str
    status: GoalStatus
    actions: List[Dict[str, Any]] = field(default_factory=list)
    action_results: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    priority: int = 0
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_strategy: str = "sequential"
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "template_id": self.template_id,
            "name": self.name,
            "status": self.status.value,
            "actions": self.actions,
            "action_results": self.action_results,
            "context": self.context,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "metadata": self.metadata,
            "execution_strategy": self.execution_strategy,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


@dataclass
class GoalContext:
    user_id: Optional[str] = None
    current_room: Optional[str] = None
    time_of_day: Optional[str] = None
    weather: Optional[str] = None
    user_presence: Optional[Dict[str, bool]] = None
    device_states: Optional[Dict[str, Any]] = None
    resource_states: Dict[str, Any] = field(default_factory=dict)
    additional_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "current_room": self.current_room,
            "time_of_day": self.time_of_day,
            "weather": self.weather,
            "user_presence": self.user_presence,
            "device_states": self.device_states,
            "resource_states": self.resource_states,
            **self.additional_context,
        }


class GoalEngine:
    def __init__(
        self,
        template_registry: Optional[GoalTemplateRegistry] = None
    ) -> None:
        self.template_registry = template_registry or GoalTemplateRegistry()
        self.active_goals: Dict[str, Goal] = {}
        self.active_composite_goals: Dict[str, CompositeGoal] = {}
        self.goal_history: List[Goal] = []
        self.composite_goal_history: List[CompositeGoal] = []
        self.max_history_size = 100

        self.conflict_resolver = GoalConflictResolver()
        self.priority_manager = GoalPriorityManager()
        self.adaptive_manager = AdaptiveGoalManager()
        self.composite_executor = CompositeGoalExecutor()

        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._background_tasks())
        logger.info("Goal engine started")

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

        logger.info("Goal engine stopped")

    async def _background_tasks(self) -> None:
        while self._running:
            await asyncio.sleep(60)
            await self._check_deferred_goals()
            await self._cleanup_old_history()

    def parse_goal(
        self,
        text: str,
        context: Optional[GoalContext] = None
    ) -> Optional[Goal]:
        context = context or GoalContext()

        template = self.template_registry.find_matching_template(text)
        if not template:
            return None

        import uuid
        goal = Goal(
            goal_id=str(uuid.uuid4()),
            template_id=template.template_id,
            name=template.name,
            status=GoalStatus.PENDING,
            actions=template.required_actions.copy(),
            context=context.to_dict(),
            priority=template.priority,
            metadata={"template": template.to_dict()},
        )

        logger.info(f"Parsed goal: {goal.name} from text: {text}")
        return goal

    async def execute_goal(
        self,
        goal: Goal,
        action_executor: Optional[callable] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        context = context or {}
        result = {
            "goal_id": goal.goal_id,
            "success": False,
            "message": "",
            "executed_actions": [],
            "failed_actions": [],
            "adaptations": [],
        }

        try:
            goal.status = GoalStatus.IN_PROGRESS
            goal.started_at = time.time()

            final_priority = self.priority_manager.calculate_priority(goal.to_dict(), context)
            goal.priority = final_priority

            self.active_goals[goal.goal_id] = goal

            conflicts = self._check_goal_conflicts(goal, context)
            if conflicts:
                for conflict in conflicts:
                    resolution = await self.conflict_resolver.resolve_conflict(conflict, goal.to_dict(), context)
                    if resolution.actions:
                        goal.actions = resolution.actions
                        result["adaptations"].append({
                            "type": "conflict_resolution",
                            "resolution": resolution.to_dict() if hasattr(resolution, 'to_dict') else str(resolution),
                        })

            if action_executor:
                for action in goal.actions:
                    try:
                        action_result = action_executor(action, goal.context)
                        goal.action_results.append({
                            "action": action,
                            "result": action_result,
                            "success": True,
                        })
                        result["executed_actions"].append(action)
                    except Exception as e:
                        logger.error(f"Action execution failed: {e}")
                        goal.action_results.append({
                            "action": action,
                            "result": str(e),
                            "success": False,
                        })
                        result["failed_actions"].append(action)

                        adaptation_event = AdaptationEvent(
                            goal_id=goal.goal_id,
                            trigger=AdaptationTrigger.FAILURE,
                            context=goal.context,
                        )
                        adaptation_result = await self.adaptive_manager.adapt_goal(adaptation_event, goal.to_dict(), context)
                        if adaptation_result.success and adaptation_result.modified_goal:
                            goal.actions = adaptation_result.modified_goal.get("actions", [])
                            result["adaptations"].append({
                                "type": "adaptation",
                                "result": str(adaptation_result),
                            })
                            goal.retry_count += 1
                            if goal.retry_count <= goal.max_retries:
                                continue

            if not result["failed_actions"]:
                goal.status = GoalStatus.COMPLETED
                result["success"] = True
                result["message"] = f"成功完成目标: {goal.name}"
            else:
                goal.status = GoalStatus.FAILED
                result["success"] = False
                result["message"] = f"目标部分失败: {goal.name}"

            goal.completed_at = time.time()
            self._archive_goal(goal)

        except Exception as e:
            logger.error(f"Goal execution failed: {e}")
            goal.status = GoalStatus.FAILED
            goal.error = str(e)
            result["success"] = False
            result["message"] = f"目标执行失败: {str(e)}"

        return result

    def create_composite_goal(
        self,
        name: str,
        description: str,
        sub_goals: List[Dict[str, Any]],
        execution_strategy: str = "sequential",
        context: Optional[Dict[str, Any]] = None
    ) -> CompositeGoal:
        import uuid
        composite_goal = CompositeGoal(
            goal_id=str(uuid.uuid4()),
            name=name,
            description=description,
            status="pending",
            execution_strategy=SubGoalStrategy(execution_strategy),
            context=context or {},
        )

        for sub_goal_data in sub_goals:
            config = SubGoalConfig(
                goal_id=sub_goal_data.get("goal_id", str(uuid.uuid4())),
                strategy=SubGoalStrategy(sub_goal_data.get("strategy", "sequential")),
                priority=sub_goal_data.get("priority", 0),
                conditions=sub_goal_data.get("conditions", []),
                timeout=sub_goal_data.get("timeout"),
                retry_count=sub_goal_data.get("retry_count", 0),
                metadata=sub_goal_data.get("metadata", {}),
            )
            composite_goal.add_sub_goal(config)

            for dep in sub_goal_data.get("dependencies", []):
                relation = GoalRelation(
                    source_goal_id=dep,
                    target_goal_id=config.goal_id,
                    relation_type=GoalRelationType.DEPENDS_ON,
                )
                composite_goal.add_relation(relation)

        self.active_composite_goals[composite_goal.goal_id] = composite_goal
        logger.info(f"Created composite goal: {composite_goal.name}")
        return composite_goal

    async def execute_composite_goal(
        self,
        composite_goal: CompositeGoal,
        goal_executor: Optional[Callable] = None
    ) -> Dict[str, Any]:
        if goal_executor:
            self.composite_executor.set_goal_executor(goal_executor)

        result = await self.composite_executor.execute_composite_goal(composite_goal)

        if composite_goal.status in ["completed", "failed", "cancelled"]:
            self._archive_composite_goal(composite_goal)

        return result

    def _check_goal_conflicts(self, goal: Goal, context: Dict[str, Any]) -> List[GoalConflict]:
        conflicts = []

        for active_goal in self.active_goals.values():
            if active_goal.goal_id == goal.goal_id:
                continue

            detected = self.conflict_resolver.detect_conflicts(goal.to_dict(), active_goal.to_dict())
            conflicts.extend(detected)

        return conflicts

    async def _check_deferred_goals(self) -> None:
        current_time = time.time()

        for goal in list(self.active_goals.values()):
            if goal.status == GoalStatus.DEFERRED:
                deferred_until = goal.metadata.get("deferred_until", 0)
                if current_time >= deferred_until:
                    goal.status = GoalStatus.PENDING
                    logger.info(f"Deferred goal {goal.goal_id} is now eligible for execution")

    async def _cleanup_old_history(self) -> None:
        if len(self.goal_history) > self.max_history_size:
            self.goal_history = self.goal_history[-self.max_history_size:]

        if len(self.composite_goal_history) > self.max_history_size:
            self.composite_goal_history = self.composite_goal_history[-self.max_history_size:]

    def cancel_goal(self, goal_id: str) -> bool:
        goal = self.active_goals.get(goal_id)
        if goal:
            goal.status = GoalStatus.CANCELLED
            goal.completed_at = time.time()
            del self.active_goals[goal_id]
            self._archive_goal(goal)
            logger.info(f"Cancelled goal: {goal.goal_id}")
            return True

        return self.composite_executor.cancel_composite_goal(goal_id)

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        if goal_id in self.active_goals:
            return self.active_goals[goal_id]
        for goal in reversed(self.goal_history):
            if goal.goal_id == goal_id:
                return goal
        return None

    def get_composite_goal(self, goal_id: str) -> Optional[CompositeGoal]:
        if goal_id in self.active_composite_goals:
            return self.active_composite_goals[goal_id]
        for goal in reversed(self.composite_goal_history):
            if goal.goal_id == goal_id:
                return goal
        return None

    def get_active_goals(self) -> List[Goal]:
        return list(self.active_goals.values())

    def get_active_composite_goals(self) -> List[CompositeGoal]:
        return list(self.active_composite_goals.values())

    def get_goal_history(self, limit: int = 10) -> List[Goal]:
        return self.goal_history[-limit:]

    def get_composite_goal_history(self, limit: int = 10) -> List[CompositeGoal]:
        return self.composite_goal_history[-limit:]

    def get_goal_statistics(self) -> Dict[str, Any]:
        total = len(self.goal_history) + len(self.active_goals)
        completed = sum(1 for g in self.goal_history if g.status == GoalStatus.COMPLETED)
        failed = sum(1 for g in self.goal_history if g.status == GoalStatus.FAILED)
        cancelled = sum(1 for g in self.goal_history if g.status == GoalStatus.CANCELLED)

        conflict_stats = self.conflict_resolver.get_conflict_statistics()
        adaptation_stats = self.adaptive_manager.get_adaptation_statistics()
        priority_stats = self.priority_manager.get_priority_statistics()

        return {
            "total_goals": total,
            "active_goals": len(self.active_goals),
            "active_composite_goals": len(self.active_composite_goals),
            "completed_goals": completed,
            "failed_goals": failed,
            "cancelled_goals": cancelled,
            "success_rate": (completed / total * 100) if total > 0 else 0,
            "conflicts": conflict_stats,
            "adaptations": adaptation_stats,
            "priorities": priority_stats,
        }

    def suggest_goals(
        self,
        context: Optional[GoalContext] = None
    ) -> List[Dict[str, Any]]:
        context = context or GoalContext()
        suggestions = []

        if context.time_of_day == "morning":
            suggestions.append({
                "template_id": "wake_up",
                "name": "起床模式",
                "reason": "现在是早上",
            })

        if context.time_of_day == "evening":
            suggestions.append({
                "template_id": "relax",
                "name": "放松模式",
                "reason": "现在是晚上",
            })

        if context.time_of_day == "night":
            suggestions.append({
                "template_id": "sleep",
                "name": "睡眠模式",
                "reason": "现在是深夜",
            })

        if context.weather == "hot":
            suggestions.append({
                "template_id": "relax",
                "name": "降温模式",
                "reason": "天气炎热",
            })

        return suggestions

    def _archive_goal(self, goal: Goal) -> None:
        if goal.goal_id in self.active_goals:
            del self.active_goals[goal_id]
        
        self.goal_history.append(goal)
        
        if len(self.goal_history) > self.max_history_size:
            self.goal_history = self.goal_history[-self.max_history_size:]

    def _archive_composite_goal(self, composite_goal: CompositeGoal) -> None:
        if composite_goal.goal_id in self.active_composite_goals:
            del self.active_composite_goals[composite_goal.goal_id]
        
        self.composite_goal_history.append(composite_goal)
        
        if len(self.composite_goal_history) > self.max_history_size:
            self.composite_goal_history = self.composite_goal_history[-self.max_history_size:]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_goals": [goal.to_dict() for goal in self.active_goals.values()],
            "active_composite_goals": [goal.to_dict() for goal in self.active_composite_goals.values()],
            "goal_history": [goal.to_dict() for goal in self.goal_history],
            "composite_goal_history": [goal.to_dict() for goal in self.composite_goal_history],
            "statistics": self.get_goal_statistics(),
        }

    def save_to_file(self, filepath: str) -> None:
        data = {
            "goals": [goal.to_dict() for goal in self.goal_history],
            "composite_goals": [goal.to_dict() for goal in self.composite_goal_history],
            "templates": self.template_registry.to_dict(),
            "adaptation_history": [
                {
                    "goal_pattern": d.goal_pattern,
                    "trigger": d.adaptation_trigger.value,
                    "action": d.adaptation_action.value,
                    "success": d.success,
                    "timestamp": d.timestamp,
                }
                for d in self.adaptive_manager.learning_history
            ],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Goal engine saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "GoalEngine":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        template_registry = GoalTemplateRegistry()
        if "templates" in data:
            template_registry = GoalTemplateRegistry.load_from_json_data(data["templates"])
        
        engine = cls(template_registry)
        
        for goal_data in data.get("goals", []):
            goal = Goal(
                goal_id=goal_data["goal_id"],
                template_id=goal_data["template_id"],
                name=goal_data["name"],
                status=GoalStatus(goal_data["status"]),
                actions=goal_data.get("actions", []),
                action_results=goal_data.get("action_results", []),
                context=goal_data.get("context", {}),
                created_at=goal_data.get("created_at", time.time()),
                started_at=goal_data.get("started_at"),
                completed_at=goal_data.get("completed_at"),
                error=goal_data.get("error"),
                priority=goal_data.get("priority", 0),
                dependencies=goal_data.get("dependencies", []),
                metadata=goal_data.get("metadata", {}),
                execution_strategy=goal_data.get("execution_strategy", "sequential"),
                retry_count=goal_data.get("retry_count", 0),
                max_retries=goal_data.get("max_retries", 3),
            )
            if goal.status in [GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.CANCELLED]:
                engine.goal_history.append(goal)
        
        logger.info(f"Goal engine loaded from {filepath}")
        return engine
