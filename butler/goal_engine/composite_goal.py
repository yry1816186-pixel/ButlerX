from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class GoalRelationType(Enum):
    DEPENDS_ON = "depends_on"
    CONFLICTS_WITH = "conflicts_with"
    REINFORCES = "reinforces"
    EXCLUSIVE = "exclusive"


class SubGoalStrategy(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    PRIORITY_BASED = "priority_based"
    CONDITIONAL = "conditional"


@dataclass
class GoalRelation:
    source_goal_id: str
    target_goal_id: str
    relation_type: GoalRelationType
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SubGoalConfig:
    goal_id: str
    strategy: SubGoalStrategy = SubGoalStrategy.SEQUENTIAL
    priority: int = 0
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    timeout: Optional[float] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SubGoal:
    goal_id: str
    name: str
    priority: int = 0
    strategy: SubGoalStrategy = SubGoalStrategy.SEQUENTIAL
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    timeout: Optional[float] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompositeGoal:
    goal_id: str
    name: str
    description: str
    status: str
    sub_goals: List[SubGoalConfig] = field(default_factory=list)
    sub_goal_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    execution_strategy: SubGoalStrategy = SubGoalStrategy.SEQUENTIAL
    relations: List[GoalRelation] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    current_sub_goal_index: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_sub_goal(self, config: SubGoalConfig) -> None:
        self.sub_goals.append(config)
        logger.debug(f"Added sub-goal {config.goal_id} to composite goal {self.goal_id}")

    def add_relation(self, relation: GoalRelation) -> None:
        self.relations.append(relation)
        logger.debug(f"Added relation {relation.relation_type.value} from {relation.source_goal_id} to {relation.target_goal_id}")

    def get_sub_goal(self, goal_id: str) -> Optional[SubGoalConfig]:
        for sub_goal in self.sub_goals:
            if sub_goal.goal_id == goal_id:
                return sub_goal
        return None

    def get_dependencies(self, goal_id: str) -> List[str]:
        dependencies = []
        for relation in self.relations:
            if relation.target_goal_id == goal_id and relation.relation_type == GoalRelationType.DEPENDS_ON:
                dependencies.append(relation.source_goal_id)
        return dependencies

    def get_conflicts(self, goal_id: str) -> List[str]:
        conflicts = []
        for relation in self.relations:
            if relation.target_goal_id == goal_id and relation.relation_type == GoalRelationType.CONFLICTS_WITH:
                conflicts.append(relation.source_goal_id)
        return conflicts

    def get_next_sub_goal(self) -> Optional[SubGoalConfig]:
        if self.current_sub_goal_index < len(self.sub_goals):
            return self.sub_goals[self.current_sub_goal_index]
        return None

    def mark_sub_goal_complete(self, goal_id: str, result: Dict[str, Any]) -> None:
        self.sub_goal_results[goal_id] = result
        logger.info(f"Marked sub-goal {goal_id} as complete")

    def is_sub_goal_complete(self, goal_id: str) -> bool:
        return goal_id in self.sub_goal_results

    def can_execute_sub_goal(self, goal_id: str) -> tuple[bool, Optional[str]]:
        dependencies = self.get_dependencies(goal_id)
        for dep_id in dependencies:
            if not self.is_sub_goal_complete(dep_id):
                return False, f"Dependency {dep_id} not completed"
        return True, None

    def get_progress(self) -> float:
        if not self.sub_goals:
            return 0.0
        completed = sum(1 for sg in self.sub_goals if self.is_sub_goal_complete(sg.goal_id))
        return completed / len(self.sub_goals)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "sub_goals": [
                {
                    "goal_id": sg.goal_id,
                    "strategy": sg.strategy.value,
                    "priority": sg.priority,
                    "conditions": sg.conditions,
                    "timeout": sg.timeout,
                    "retry_count": sg.retry_count,
                    "metadata": sg.metadata,
                }
                for sg in self.sub_goals
            ],
            "sub_goal_results": self.sub_goal_results,
            "execution_strategy": self.execution_strategy.value,
            "relations": [
                {
                    "source_goal_id": r.source_goal_id,
                    "target_goal_id": r.target_goal_id,
                    "relation_type": r.relation_type.value,
                    "metadata": r.metadata,
                }
                for r in self.relations
            ],
            "context": self.context,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "current_sub_goal_index": self.current_sub_goal_index,
            "error": self.error,
            "metadata": self.metadata,
            "progress": self.get_progress(),
        }


class CompositeGoalExecutor:
    def __init__(self):
        self.active_composite_goals: Dict[str, CompositeGoal] = {}
        self.goal_executor: Optional[Callable] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def set_goal_executor(self, executor: Callable) -> None:
        self.goal_executor = executor

    async def execute_composite_goal(self, composite_goal: CompositeGoal) -> Dict[str, Any]:
        result = {
            "goal_id": composite_goal.goal_id,
            "success": False,
            "message": "",
            "executed_sub_goals": [],
            "failed_sub_goals": [],
            "progress": 0.0,
        }

        try:
            composite_goal.status = "in_progress"
            composite_goal.started_at = time.time()
            self.active_composite_goals[composite_goal.goal_id] = composite_goal

            if composite_goal.execution_strategy == SubGoalStrategy.SEQUENTIAL:
                await self._execute_sequential(composite_goal, result)
            elif composite_goal.execution_strategy == SubGoalStrategy.PARALLEL:
                await self._execute_parallel(composite_goal, result)
            elif composite_goal.execution_strategy == SubGoalStrategy.PRIORITY_BASED:
                await self._execute_priority_based(composite_goal, result)
            elif composite_goal.execution_strategy == SubGoalStrategy.CONDITIONAL:
                await self._execute_conditional(composite_goal, result)

            if not result["failed_sub_goals"]:
                composite_goal.status = "completed"
                result["success"] = True
                result["message"] = f"成功完成复合目标: {composite_goal.name}"
            else:
                composite_goal.status = "failed"
                result["success"] = False
                result["message"] = f"复合目标部分失败: {composite_goal.name}"

            composite_goal.completed_at = time.time()
            del self.active_composite_goals[composite_goal.goal_id]

        except Exception as e:
            logger.error(f"Composite goal execution failed: {e}")
            composite_goal.status = "failed"
            composite_goal.error = str(e)
            result["success"] = False
            result["message"] = f"复合目标执行失败: {str(e)}"

        result["progress"] = composite_goal.get_progress()
        return result

    async def _execute_sequential(self, composite_goal: CompositeGoal, result: Dict[str, Any]) -> None:
        for sub_goal_config in composite_goal.sub_goals:
            can_execute, reason = composite_goal.can_execute_sub_goal(sub_goal_config.goal_id)
            if not can_execute:
                logger.warning(f"Cannot execute sub-goal {sub_goal_config.goal_id}: {reason}")
                continue

            composite_goal.current_sub_goal_index = composite_goal.sub_goals.index(sub_goal_config)
            sub_goal_result = await self._execute_sub_goal(sub_goal_config, composite_goal)

            if sub_goal_result.get("success", False):
                result["executed_sub_goals"].append(sub_goal_config.goal_id)
            else:
                result["failed_sub_goals"].append(sub_goal_config.goal_id)

    async def _execute_parallel(self, composite_goal: CompositeGoal, result: Dict[str, Any]) -> None:
        tasks = []
        for sub_goal_config in composite_goal.sub_goals:
            can_execute, _ = composite_goal.can_execute_sub_goal(sub_goal_config.goal_id)
            if can_execute:
                task = asyncio.create_task(self._execute_sub_goal(sub_goal_config, composite_goal))
                tasks.append((sub_goal_config.goal_id, task))

        for goal_id, task in tasks:
            try:
                sub_goal_result = await task
                if sub_goal_result.get("success", False):
                    result["executed_sub_goals"].append(goal_id)
                else:
                    result["failed_sub_goals"].append(goal_id)
            except Exception as e:
                logger.error(f"Parallel sub-goal {goal_id} failed: {e}")
                result["failed_sub_goals"].append(goal_id)

    async def _execute_priority_based(self, composite_goal: CompositeGoal, result: Dict[str, Any]) -> None:
        sorted_sub_goals = sorted(composite_goal.sub_goals, key=lambda sg: sg.priority, reverse=True)

        for sub_goal_config in sorted_sub_goals:
            can_execute, reason = composite_goal.can_execute_sub_goal(sub_goal_config.goal_id)
            if not can_execute:
                logger.warning(f"Cannot execute sub-goal {sub_goal_config.goal_id}: {reason}")
                continue

            composite_goal.current_sub_goal_index = composite_goal.sub_goals.index(sub_goal_config)
            sub_goal_result = await self._execute_sub_goal(sub_goal_config, composite_goal)

            if sub_goal_result.get("success", False):
                result["executed_sub_goals"].append(sub_goal_config.goal_id)
            else:
                result["failed_sub_goals"].append(sub_goal_config.goal_id)

    async def _execute_conditional(self, composite_goal: CompositeGoal, result: Dict[str, Any]) -> None:
        for sub_goal_config in composite_goal.sub_goals:
            if not self._check_conditions(sub_goal_config.conditions, composite_goal.context):
                logger.info(f"Conditions not met for sub-goal {sub_goal_config.goal_id}, skipping")
                continue

            can_execute, reason = composite_goal.can_execute_sub_goal(sub_goal_config.goal_id)
            if not can_execute:
                logger.warning(f"Cannot execute sub-goal {sub_goal_config.goal_id}: {reason}")
                continue

            composite_goal.current_sub_goal_index = composite_goal.sub_goals.index(sub_goal_config)
            sub_goal_result = await self._execute_sub_goal(sub_goal_config, composite_goal)

            if sub_goal_result.get("success", False):
                result["executed_sub_goals"].append(sub_goal_config.goal_id)
            else:
                result["failed_sub_goals"].append(sub_goal_config.goal_id)

    async def _execute_sub_goal(self, config: SubGoalConfig, composite_goal: CompositeGoal) -> Dict[str, Any]:
        if self.goal_executor:
            goal_data = {
                "goal_id": config.goal_id,
                "context": composite_goal.context,
                "metadata": config.metadata,
            }

            if config.timeout:
                try:
                    result = await asyncio.wait_for(self.goal_executor(goal_data), timeout=config.timeout)
                except asyncio.TimeoutError:
                    logger.error(f"Sub-goal {config.goal_id} timed out after {config.timeout}s")
                    result = {"success": False, "message": "Timeout"}
            else:
                result = await self.goal_executor(goal_data)

            composite_goal.mark_sub_goal_complete(config.goal_id, result)
            return result

        return {"success": False, "message": "No goal executor configured"}

    def _check_conditions(self, conditions: List[Dict[str, Any]], context: Dict[str, Any]) -> bool:
        if not conditions:
            return True

        for condition in conditions:
            condition_type = condition.get("type")
            if condition_type == "equals":
                key = condition.get("key")
                value = condition.get("value")
                if context.get(key) != value:
                    return False
            elif condition_type == "greater_than":
                key = condition.get("key")
                value = condition.get("value")
                if context.get(key, 0) <= value:
                    return False
            elif condition_type == "less_than":
                key = condition.get("key")
                value = condition.get("value")
                if context.get(key, 0) >= value:
                    return False
            elif condition_type == "contains":
                key = condition.get("key")
                value = condition.get("value")
                if value not in context.get(key, ""):
                    return False
            elif condition_type == "custom":
                callback = condition.get("callback")
                if callback and callable(callback):
                    if not callback(context):
                        return False

        return True

    def get_active_composite_goals(self) -> List[CompositeGoal]:
        return list(self.active_composite_goals.values())

    def get_composite_goal(self, goal_id: str) -> Optional[CompositeGoal]:
        return self.active_composite_goals.get(goal_id)

    def cancel_composite_goal(self, goal_id: str) -> bool:
        composite_goal = self.active_composite_goals.get(goal_id)
        if not composite_goal:
            return False

        composite_goal.status = "cancelled"
        composite_goal.completed_at = time.time()
        del self.active_composite_goals[goal_id]
        logger.info(f"Cancelled composite goal: {goal_id}")
        return True
