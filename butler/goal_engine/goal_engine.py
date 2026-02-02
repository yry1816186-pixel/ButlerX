from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .goal_templates import GoalTemplateRegistry, GoalTemplate

logger = logging.getLogger(__name__)


class GoalStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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
        }


@dataclass
class GoalContext:
    user_id: Optional[str] = None
    current_room: Optional[str] = None
    time_of_day: Optional[str] = None
    weather: Optional[str] = None
    user_presence: Optional[Dict[str, bool]] = None
    device_states: Optional[Dict[str, Any]] = None
    additional_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "current_room": self.current_room,
            "time_of_day": self.time_of_day,
            "weather": self.weather,
            "user_presence": self.user_presence,
            "device_states": self.device_states,
            **self.additional_context,
        }


class GoalEngine:
    def __init__(
        self,
        template_registry: Optional[GoalTemplateRegistry] = None
    ) -> None:
        self.template_registry = template_registry or GoalTemplateRegistry()
        self.active_goals: Dict[str, Goal] = {}
        self.goal_history: List[Goal] = []
        self.max_history_size = 100

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
        )

        logger.info(f"Parsed goal: {goal.name} from text: {text}")
        return goal

    def execute_goal(
        self,
        goal: Goal,
        action_executor: Optional[callable] = None
    ) -> Dict[str, Any]:
        result = {
            "goal_id": goal.goal_id,
            "success": False,
            "message": "",
            "executed_actions": [],
            "failed_actions": [],
        }

        try:
            goal.status = GoalStatus.IN_PROGRESS
            goal.started_at = time.time()
            self.active_goals[goal.goal_id] = goal

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
            else:
                result["executed_actions"] = goal.actions

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

    def cancel_goal(self, goal_id: str) -> bool:
        goal = self.active_goals.get(goal_id)
        if not goal:
            return False

        goal.status = GoalStatus.CANCELLED
        goal.completed_at = time.time()
        del self.active_goals[goal_id]
        self._archive_goal(goal)
        logger.info(f"Cancelled goal: {goal.goal_id}")
        return True

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        if goal_id in self.active_goals:
            return self.active_goals[goal_id]
        for goal in reversed(self.goal_history):
            if goal.goal_id == goal_id:
                return goal
        return None

    def get_active_goals(self) -> List[Goal]:
        return list(self.active_goals.values())

    def get_goal_history(self, limit: int = 10) -> List[Goal]:
        return self.goal_history[-limit:]

    def get_goal_statistics(self) -> Dict[str, Any]:
        total = len(self.goal_history) + len(self.active_goals)
        completed = sum(1 for g in self.goal_history if g.status == GoalStatus.COMPLETED)
        failed = sum(1 for g in self.goal_history if g.status == GoalStatus.FAILED)
        cancelled = sum(1 for g in self.goal_history if g.status == GoalStatus.CANCELLED)
        
        return {
            "total_goals": total,
            "active_goals": len(self.active_goals),
            "completed_goals": completed,
            "failed_goals": failed,
            "cancelled_goals": cancelled,
            "success_rate": (completed / total * 100) if total > 0 else 0,
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
            del self.active_goals[goal.goal_id]
        
        self.goal_history.append(goal)
        
        if len(self.goal_history) > self.max_history_size:
            self.goal_history = self.goal_history[-self.max_history_size:]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_goals": [goal.to_dict() for goal in self.active_goals.values()],
            "goal_history": [goal.to_dict() for goal in self.goal_history],
            "statistics": self.get_goal_statistics(),
        }

    def save_to_file(self, filepath: str) -> None:
        data = {
            "goals": [goal.to_dict() for goal in self.goal_history],
            "templates": self.template_registry.to_dict(),
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
            )
            if goal.status in [GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.CANCELLED]:
                engine.goal_history.append(goal)
        
        logger.info(f"Goal engine loaded from {filepath}")
        return engine
