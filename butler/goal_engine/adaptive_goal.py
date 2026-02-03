from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class AdaptationTrigger(Enum):
    FAILURE = "failure"
    TIMEOUT = "timeout"
    RESOURCE_CONSTRAINT = "resource_constraint"
    USER_FEEDBACK = "user_feedback"
    CONTEXT_CHANGE = "context_change"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    PREFERENCE_CHANGE = "preference_change"
    SCHEDULED = "scheduled"


class AdaptationAction(Enum):
    RETRY = "retry"
    ABORT = "abort"
    MODIFY_PARAMS = "modify_params"
    CHANGE_STRATEGY = "change_strategy"
    REDUCE_SCOPE = "reduce_scope"
    DEFER = "defer"
    ALTERNATIVE_ACTION = "alternative_action"
    DELEGATE = "delegate"
    REQUEST_APPROVAL = "request_approval"


@dataclass
class AdaptationRule:
    trigger: AdaptationTrigger
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    actions: List[AdaptationAction] = field(default_factory=list)
    priority: int = 0
    max_attempts: int = 3
    cooldown: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class AdaptationEvent:
    goal_id: str
    trigger: AdaptationTrigger
    timestamp: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)
    original_goal: Optional[Dict[str, Any]] = None


@dataclass
class AdaptationResult:
    event: AdaptationEvent
    actions_taken: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = False
    reason: str = ""
    modified_goal: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LearningData:
    goal_pattern: str
    adaptation_trigger: AdaptationTrigger
    adaptation_action: AdaptationAction
    success: bool
    timestamp: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)


class AdaptiveGoalManager:
    def __init__(self):
        self.adaptation_rules: List[AdaptationRule] = []
        self.learning_history: List[LearningData] = []
        self.adaptation_history: List[AdaptationResult] = []
        self.goal_attempt_counts: Dict[str, int] = {}
        self.last_adaptation_time: Dict[str, float] = {}
        self.custom_adapters: Dict[str, Callable] = {}
        self._init_default_rules()

    def _init_default_rules(self) -> None:
        self.add_adaptation_rule(AdaptationRule(
            trigger=AdaptationTrigger.FAILURE,
            actions=[AdaptationAction.RETRY, AdaptationAction.MODIFY_PARAMS],
            priority=10,
            max_attempts=3,
            cooldown=5.0,
        ))

        self.add_adaptation_rule(AdaptationRule(
            trigger=AdaptationTrigger.TIMEOUT,
            actions=[AdaptationAction.ABORT, AdaptationAction.ALTERNATIVE_ACTION],
            priority=15,
            max_attempts=2,
            cooldown=10.0,
        ))

        self.add_adaptation_rule(AdaptationRule(
            trigger=AdaptationTrigger.RESOURCE_CONSTRAINT,
            actions=[AdaptationAction.DEFER, AdaptationAction.MODIFY_PARAMS],
            priority=8,
            max_attempts=2,
            cooldown=30.0,
        ))

        self.add_adaptation_rule(AdaptationRule(
            trigger=AdaptationTrigger.USER_FEEDBACK,
            actions=[AdaptationAction.CHANGE_STRATEGY, AdaptationAction.MODIFY_PARAMS],
            priority=20,
            max_attempts=1,
            cooldown=0.0,
        ))

        self.add_adaptation_rule(AdaptationRule(
            trigger=AdaptationTrigger.CONTEXT_CHANGE,
            actions=[AdaptationAction.MODIFY_PARAMS, AdaptationAction.REDUCE_SCOPE],
            priority=5,
            max_attempts=2,
            cooldown=15.0,
        ))

        self.add_adaptation_rule(AdaptationRule(
            trigger=AdaptationTrigger.PERFORMANCE_DEGRADATION,
            actions=[AdaptationAction.REDUCE_SCOPE, AdaptationAction.DEFER],
            priority=7,
            max_attempts=2,
            cooldown=20.0,
        ))

        logger.info(f"Initialized {len(self.adaptation_rules)} adaptation rules")

    def add_adaptation_rule(self, rule: AdaptationRule) -> None:
        self.adaptation_rules.append(rule)
        logger.info(f"Added adaptation rule: {rule.trigger.value}")

    def remove_adaptation_rule(self, rule_index: int) -> bool:
        if 0 <= rule_index < len(self.adaptation_rules):
            del self.adaptation_rules[rule_index]
            return True
        return False

    def register_custom_adapter(self, action_name: str, adapter: Callable) -> None:
        self.custom_adapters[action_name] = adapter
        logger.info(f"Registered custom adapter: {action_name}")

    async def adapt_goal(
        self,
        event: AdaptationEvent,
        goal: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> AdaptationResult:
        context = context or {}
        event.original_goal = goal.copy()
        goal_id = goal.get("goal_id", "")

        if not self._can_adapt(goal_id, event):
            return AdaptationResult(
                event=event,
                success=False,
                reason="Adaptation blocked by cooldown or max attempts",
            )

        applicable_rules = self._find_applicable_rules(event, goal)

        if not applicable_rules:
            logger.info(f"No applicable adaptation rules for {goal_id}")
            return AdaptationResult(
                event=event,
                success=False,
                reason="No applicable adaptation rules",
            )

        rule = applicable_rules[0]
        self._record_attempt(goal_id)

        actions_taken = []
        modified_goal = goal.copy()

        for action in rule.actions:
            try:
                action_result = await self._execute_adaptation_action(
                    action,
                    modified_goal,
                    event,
                    context
                )
                actions_taken.append(action_result)

                if action_result.get("success", False):
                    modified_goal = action_result.get("modified_goal", modified_goal)
                else:
                    logger.warning(f"Adaptation action {action.value} failed")
            except Exception as e:
                logger.error(f"Adaptation action execution failed: {e}")
                actions_taken.append({
                    "action": action.value,
                    "success": False,
                    "error": str(e),
                })

        success = any(a.get("success", False) for a in actions_taken)
        result = AdaptationResult(
            event=event,
            actions_taken=actions_taken,
            success=success,
            reason=f"Adapted using rule: {rule.trigger.value}",
            modified_goal=modified_goal if success else None,
            metadata={"rule_priority": rule.priority},
        )

        self.adaptation_history.append(result)
        self._learn_from_adaptation(event, result, context)

        return result

    def _can_adapt(self, goal_id: str, event: AdaptationEvent) -> bool:
        current_time = time.time()

        attempt_count = self.goal_attempt_counts.get(goal_id, 0)
        last_adaptation = self.last_adaptation_time.get(goal_id, 0)

        applicable_rules = self._find_applicable_rules(event, {"goal_id": goal_id})
        if not applicable_rules:
            return False

        rule = applicable_rules[0]

        if attempt_count >= rule.max_attempts:
            logger.info(f"Goal {goal_id} exceeded max adaptation attempts ({rule.max_attempts})")
            return False

        cooldown_passed = (current_time - last_adaptation) >= rule.cooldown
        if not cooldown_passed:
            logger.info(f"Goal {goal_id} still in cooldown ({rule.cooldown}s)")
            return False

        return True

    def _find_applicable_rules(self, event: AdaptationEvent, goal: Dict[str, Any]) -> List[AdaptationRule]:
        applicable = []

        for rule in self.adaptation_rules:
            if not rule.enabled:
                continue

            if rule.trigger != event.trigger:
                continue

            if rule.condition:
                try:
                    if not rule.condition(goal):
                        continue
                except Exception as e:
                    logger.warning(f"Rule condition evaluation failed: {e}")
                    continue

            applicable.append(rule)

        applicable.sort(key=lambda r: r.priority, reverse=True)
        return applicable

    def _record_attempt(self, goal_id: str) -> None:
        self.goal_attempt_counts[goal_id] = self.goal_attempt_counts.get(goal_id, 0) + 1
        self.last_adaptation_time[goal_id] = time.time()

    async def _execute_adaptation_action(
        self,
        action: AdaptationAction,
        goal: Dict[str, Any],
        event: AdaptationEvent,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        result = {"action": action.value, "success": False}

        if action == AdaptationAction.RETRY:
            result["success"] = True
            result["message"] = "Goal marked for retry"

        elif action == AdaptationAction.ABORT:
            result["success"] = True
            result["message"] = "Goal aborted"
            result["modified_goal"] = {**goal, "status": "aborted"}

        elif action == AdaptationAction.MODIFY_PARAMS:
            modified_goal = self._modify_goal_params(goal, event, context)
            result["success"] = True
            result["message"] = "Goal parameters modified"
            result["modified_goal"] = modified_goal

        elif action == AdaptationAction.CHANGE_STRATEGY:
            modified_goal = self._change_goal_strategy(goal, event, context)
            result["success"] = True
            result["message"] = "Goal strategy changed"
            result["modified_goal"] = modified_goal

        elif action == AdaptationAction.REDUCE_SCOPE:
            modified_goal = self._reduce_goal_scope(goal, event, context)
            result["success"] = True
            result["message"] = "Goal scope reduced"
            result["modified_goal"] = modified_goal

        elif action == AdaptationAction.DEFER:
            result["success"] = True
            result["message"] = "Goal deferred"
            result["modified_goal"] = {
                **goal,
                "status": "deferred",
                "deferred_until": time.time() + 3600,
            }

        elif action == AdaptationAction.ALTERNATIVE_ACTION:
            modified_goal = self._find_alternative_action(goal, event, context)
            result["success"] = True
            result["message"] = "Alternative action found"
            result["modified_goal"] = modified_goal

        elif action == AdaptationAction.DELEGATE:
            result["success"] = True
            result["message"] = "Goal delegated"
            result["modified_goal"] = {**goal, "delegate": True}

        elif action == AdaptationAction.REQUEST_APPROVAL:
            result["success"] = True
            result["message"] = "Approval requested"
            result["modified_goal"] = {**goal, "requires_approval": True}

        return result

    def _modify_goal_params(self, goal: Dict[str, Any], event: AdaptationEvent, context: Dict[str, Any]) -> Dict[str, Any]:
        modified_goal = goal.copy()

        action_type = goal.get("action_type")
        params = modified_goal.get("params", {}).copy()

        if action_type in ["turn_on", "set_brightness"]:
            current_brightness = params.get("brightness", 100)
            new_brightness = max(current_brightness * 0.8, 30)
            params["brightness"] = int(new_brightness)

        elif action_type == "set_temperature":
            current_temp = params.get("value", 24)
            new_temp = min(current_temp + 1, 26)
            params["value"] = new_temp

        elif action_type == "play_music":
            current_volume = params.get("volume", 50)
            new_volume = max(current_volume * 0.9, 20)
            params["volume"] = int(new_volume)

        modified_goal["params"] = params
        modified_goal["adapted"] = True

        return modified_goal

    def _change_goal_strategy(self, goal: Dict[str, Any], event: AdaptationEvent, context: Dict[str, Any]) -> Dict[str, Any]:
        modified_goal = goal.copy()

        current_strategy = modified_goal.get("execution_strategy", "sequential")
        strategies = ["sequential", "parallel", "priority_based"]

        if current_strategy in strategies:
            current_index = strategies.index(current_strategy)
            next_strategy = strategies[(current_index + 1) % len(strategies)]
            modified_goal["execution_strategy"] = next_strategy
            modified_goal["adapted"] = True

        return modified_goal

    def _reduce_goal_scope(self, goal: Dict[str, Any], event: AdaptationEvent, context: Dict[str, Any]) -> Dict[str, Any]:
        modified_goal = goal.copy()

        actions = modified_goal.get("actions", [])
        if len(actions) > 1:
            modified_goal["actions"] = actions[:max(1, len(actions) - 1)]
            modified_goal["scope_reduced"] = True
            modified_goal["adapted"] = True

        optional_actions = modified_goal.get("optional_actions", [])
        if optional_actions:
            modified_goal["optional_actions"] = []
            modified_goal["scope_reduced"] = True

        return modified_goal

    def _find_alternative_action(self, goal: Dict[str, Any], event: AdaptationEvent, context: Dict[str, Any]) -> Dict[str, Any]:
        modified_goal = goal.copy()
        action_type = goal.get("action_type")

        alternatives = {
            "turn_on": "set_brightness",
            "set_brightness": "turn_on",
            "play_music": "notify",
            "set_temperature": "notify",
        }

        if action_type in alternatives:
            modified_goal["action_type"] = alternatives[action_type]
            modified_goal["alternative_used"] = True
            modified_goal["adapted"] = True

        return modified_goal

    def _learn_from_adaptation(
        self,
        event: AdaptationEvent,
        result: AdaptationResult,
        context: Dict[str, Any]
    ) -> None:
        goal_pattern = self._extract_goal_pattern(event.original_goal or {})

        for action_result in result.actions_taken:
            action_name = action_result.get("action", "")
            success = action_result.get("success", False)

            try:
                action_enum = AdaptationAction(action_name)
            except ValueError:
                continue

            learning_data = LearningData(
                goal_pattern=goal_pattern,
                adaptation_trigger=event.trigger,
                adaptation_action=action_enum,
                success=success,
                context=context,
            )
            self.learning_history.append(learning_data)

        if len(self.learning_history) > 1000:
            self.learning_history = self.learning_history[-1000:]

    def _extract_goal_pattern(self, goal: Dict[str, Any]) -> str:
        action_type = goal.get("action_type", "unknown")
        target = goal.get("params", {}).get("target", "unknown")
        return f"{action_type}:{target}"

    def get_learning_insights(self, limit: int = 100) -> Dict[str, Any]:
        recent = self.learning_history[-limit:]

        if not recent:
            return {"message": "No learning data available"}

        by_trigger = {}
        by_action = {}
        by_pattern = {}

        success_rates = {}

        for data in recent:
            trigger = data.adaptation_trigger.value
            action = data.adaptation_action.value
            pattern = data.goal_pattern

            by_trigger[trigger] = by_trigger.get(trigger, 0) + 1
            by_action[action] = by_action.get(action, 0) + 1
            by_pattern[pattern] = by_pattern.get(pattern, 0) + 1

            key = f"{trigger}:{action}"
            if key not in success_rates:
                success_rates[key] = {"success": 0, "total": 0}
            success_rates[key]["total"] += 1
            if data.success:
                success_rates[key]["success"] += 1

        for key in success_rates:
            success_rates[key]["rate"] = (
                success_rates[key]["success"] / success_rates[key]["total"] * 100
            )

        return {
            "total_learnings": len(recent),
            "by_trigger": by_trigger,
            "by_action": by_action,
            "by_pattern": dict(sorted(by_pattern.items(), key=lambda x: x[1], reverse=True)[:10]),
            "success_rates": success_rates,
        }

    def get_adaptation_statistics(self) -> Dict[str, Any]:
        total = len(self.adaptation_history)

        if total == 0:
            return {"total_adaptations": 0}

        by_trigger = {}
        by_action = {}
        successful = sum(1 for r in self.adaptation_history if r.success)

        for result in self.adaptation_history:
            trigger = result.event.trigger.value
            by_trigger[trigger] = by_trigger.get(trigger, 0) + 1

            for action_result in result.actions_taken:
                action = action_result.get("action", "unknown")
                by_action[action] = by_action.get(action, 0) + 1

        return {
            "total_adaptations": total,
            "successful_adaptations": successful,
            "failed_adaptations": total - successful,
            "success_rate": successful / total * 100,
            "by_trigger": by_trigger,
            "by_action": by_action,
        }

    def reset_attempt_counts(self, goal_id: Optional[str] = None) -> None:
        if goal_id:
            self.goal_attempt_counts.pop(goal_id, None)
            self.last_adaptation_time.pop(goal_id, None)
        else:
            self.goal_attempt_counts.clear()
            self.last_adaptation_time.clear()

        logger.info(f"Reset attempt counts for {goal_id or 'all goals'}")
