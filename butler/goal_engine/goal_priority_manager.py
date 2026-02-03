from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class PriorityFactor(Enum):
    USER_IMPORTANCE = "user_importance"
    URGENCY = "urgency"
    DEPENDENCY_DEPTH = "dependency_depth"
    RESOURCE_AVAILABILITY = "resource_availability"
    TIME_SENSITIVITY = "time_sensitivity"
    ENERGY_EFFICIENCY = "energy_efficiency"
    USER_PRESENCE = "user_presence"
    SAFETY_CRITICAL = "safety_critical"
    CUSTOM = "custom"


@dataclass
class PriorityFactorWeight:
    factor: PriorityFactor
    weight: float = 1.0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PriorityWeight:
    factor: PriorityFactor
    weight: float = 1.0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PriorityAdjustment:
    goal_id: str
    original_priority: int
    new_priority: int
    reason: str
    factors: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class PriorityRule:
    condition: Callable[[Dict[str, Any]], bool]
    priority_adjustment: int
    reason: str
    enabled: bool = True


class GoalPriorityManager:
    def __init__(self):
        self.factor_weights: Dict[PriorityFactor, PriorityFactorWeight] = {}
        self.adjustment_rules: List[PriorityRule] = []
        self.adjustment_history: List[PriorityAdjustment] = []
        self.custom_factor_evaluators: Dict[str, Callable] = {}
        self._init_default_weights()
        self._init_default_rules()

    def _init_default_weights(self) -> None:
        default_weights = {
            PriorityFactor.USER_IMPORTANCE: 2.0,
            PriorityFactor.URGENCY: 1.8,
            PriorityFactor.SAFETY_CRITICAL: 2.5,
            PriorityFactor.TIME_SENSITIVITY: 1.5,
            PriorityFactor.DEPENDENCY_DEPTH: 1.2,
            PriorityFactor.USER_PRESENCE: 1.3,
            PriorityFactor.RESOURCE_AVAILABILITY: 1.0,
            PriorityFactor.ENERGY_EFFICIENCY: 0.8,
        }

        for factor, weight in default_weights.items():
            self.factor_weights[factor] = PriorityFactorWeight(factor=factor, weight=weight)

        logger.info(f"Initialized {len(self.factor_weights)} priority factor weights")

    def _init_default_rules(self) -> None:
        self.add_priority_rule(PriorityRule(
            condition=lambda g: g.get("safety_critical", False),
            priority_adjustment=100,
            reason="Safety critical goal",
        ))

        self.add_priority_rule(PriorityRule(
            condition=lambda g: g.get("user_requested", False),
            priority_adjustment=50,
            reason="User requested goal",
        ))

        self.add_priority_rule(PriorityRule(
            condition=lambda g: g.get("emergency", False),
            priority_adjustment=200,
            reason="Emergency goal",
        ))

        self.add_priority_rule(PriorityRule(
            condition=lambda g: self._is_time_sensitive(g),
            priority_adjustment=30,
            reason="Time sensitive goal",
        ))

        self.add_priority_rule(PriorityRule(
            condition=lambda g: g.get("user_present", False) and g.get("action_type") in ["turn_on", "set_brightness"],
            priority_adjustment=20,
            reason="User present lighting action",
        ))

        logger.info(f"Initialized {len(self.adjustment_rules)} priority adjustment rules")

    def _is_time_sensitive(self, goal: Dict[str, Any]) -> bool:
        time_constraints = goal.get("time_constraints", {})
        return (
            time_constraints.get("deadline") is not None or
            time_constraints.get("time_window") is not None or
            goal.get("urgency", 0) > 5
        )

    def set_factor_weight(self, factor: PriorityFactor, weight: float) -> None:
        if factor in self.factor_weights:
            self.factor_weights[factor].weight = weight
            logger.info(f"Set {factor.value} weight to {weight}")
        else:
            self.factor_weights[factor] = PriorityFactorWeight(factor=factor, weight=weight)
            logger.info(f"Added {factor.value} with weight {weight}")

    def get_factor_weight(self, factor: PriorityFactor) -> float:
        return self.factor_weights.get(factor, PriorityFactorWeight(factor=factor)).weight

    def enable_factor(self, factor: PriorityFactor) -> None:
        if factor in self.factor_weights:
            self.factor_weights[factor].enabled = True

    def disable_factor(self, factor: PriorityFactor) -> None:
        if factor in self.factor_weights:
            self.factor_weights[factor].enabled = False

    def add_priority_rule(self, rule: PriorityRule) -> None:
        self.adjustment_rules.append(rule)
        logger.info(f"Added priority rule: {rule.reason}")

    def remove_priority_rule(self, rule_index: int) -> bool:
        if 0 <= rule_index < len(self.adjustment_rules):
            del self.adjustment_rules[rule_index]
            return True
        return False

    def register_custom_evaluator(self, factor_name: str, evaluator: Callable) -> None:
        self.custom_factor_evaluators[factor_name] = evaluator
        logger.info(f"Registered custom evaluator: {factor_name}")

    def calculate_priority(
        self,
        goal: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> int:
        context = context or {}
        base_priority = goal.get("priority", 0)

        factor_scores = {}

        for factor, weight_config in self.factor_weights.items():
            if not weight_config.enabled:
                continue

            score = self._evaluate_factor(factor, goal, context)
            factor_scores[factor.value] = score

        total_adjustment = 0
        for factor, weight_config in self.factor_weights.items():
            if weight_config.enabled and factor.value in factor_scores:
                total_adjustment += factor_scores[factor.value] * weight_config.weight

        final_priority = int(base_priority + total_adjustment)

        adjustment = PriorityAdjustment(
            goal_id=goal.get("goal_id", ""),
            original_priority=base_priority,
            new_priority=final_priority,
            reason="Priority calculated from factors",
            factors=factor_scores,
        )
        self.adjustment_history.append(adjustment)

        logger.debug(
            f"Priority for {goal.get('goal_id', 'unknown')}: "
            f"{base_priority} -> {final_priority} (adjustment: {total_adjustment:.1f})"
        )

        return final_priority

    def _evaluate_factor(
        self,
        factor: PriorityFactor,
        goal: Dict[str, Any],
        context: Dict[str, Any]
    ) -> float:
        if factor == PriorityFactor.USER_IMPORTANCE:
            return self._evaluate_user_importance(goal, context)
        elif factor == PriorityFactor.URGENCY:
            return self._evaluate_urgency(goal, context)
        elif factor == PriorityFactor.DEPENDENCY_DEPTH:
            return self._evaluate_dependency_depth(goal, context)
        elif factor == PriorityFactor.RESOURCE_AVAILABILITY:
            return self._evaluate_resource_availability(goal, context)
        elif factor == PriorityFactor.TIME_SENSITIVITY:
            return self._evaluate_time_sensitivity(goal, context)
        elif factor == PriorityFactor.ENERGY_EFFICIENCY:
            return self._evaluate_energy_efficiency(goal, context)
        elif factor == PriorityFactor.USER_PRESENCE:
            return self._evaluate_user_presence(goal, context)
        elif factor == PriorityFactor.SAFETY_CRITICAL:
            return self._evaluate_safety_critical(goal, context)
        else:
            return 0.0

    def _evaluate_user_importance(self, goal: Dict[str, Any], context: Dict[str, Any]) -> float:
        importance = goal.get("user_importance", 0)

        if goal.get("user_requested", False):
            importance += 30

        if goal.get("recurring", False):
            importance += 10

        if goal.get("template_id") in ["sleep", "wake_up"]:
            importance += 25

        return importance

    def _evaluate_urgency(self, goal: Dict[str, Any], context: Dict[str, Any]) -> float:
        urgency = goal.get("urgency", 0)

        time_constraints = goal.get("time_constraints", {})
        deadline = time_constraints.get("deadline")

        if deadline:
            time_remaining = deadline - time.time()
            if time_remaining < 300:
                urgency += 50
            elif time_remaining < 600:
                urgency += 30
            elif time_remaining < 1800:
                urgency += 15

        if goal.get("immediate", False):
            urgency += 40

        return urgency

    def _evaluate_dependency_depth(self, goal: Dict[str, Any], context: Dict[str, Any]) -> float:
        dependencies = goal.get("dependencies", [])
        depth = len(dependencies)

        if depth == 0:
            return 10

        return -depth * 2

    def _evaluate_resource_availability(self, goal: Dict[str, Any], context: Dict[str, Any]) -> float:
        resource_states = context.get("resource_states", {})

        action_type = goal.get("action_type")
        if action_type in ["turn_on", "set_brightness"]:
            energy_level = resource_states.get("energy_level", 100)
            if energy_level < 20:
                return -20
            elif energy_level < 50:
                return -10

        if action_type in ["play_music", "turn_on_tv"]:
            network_bandwidth = resource_states.get("network_bandwidth", 100)
            if network_bandwidth < 30:
                return -15

        return 0.0

    def _evaluate_time_sensitivity(self, goal: Dict[str, Any], context: Dict[str, Any]) -> float:
        time_constraints = goal.get("time_constraints", {})

        if time_constraints.get("deadline"):
            return 25

        if time_constraints.get("time_window"):
            return 15

        if goal.get("time_sensitive", False):
            return 20

        time_of_day = context.get("time_of_day")
        if time_of_day == "night" and goal.get("action_type") == "turn_off":
            return 10

        return 0.0

    def _evaluate_energy_efficiency(self, goal: Dict[str, Any], context: Dict[str, Any]) -> float:
        action_type = goal.get("action_type")

        if action_type in ["turn_on", "set_brightness"]:
            brightness = goal.get("params", {}).get("brightness", 100)
            if brightness < 30:
                return 15
            elif brightness < 60:
                return 5

        if action_type in ["turn_off", "set_temperature"]:
            return 20

        return 0.0

    def _evaluate_user_presence(self, goal: Dict[str, Any], context: Dict[str, Any]) -> float:
        user_presence = context.get("user_presence", {})

        if not user_presence.get("any_user", True):
            return -10

        if user_presence.get("owner_present", False):
            return 15

        action_type = goal.get("action_type")
        if action_type in ["notify", "alert"] and not user_presence.get("owner_present", False):
            return 10

        return 0.0

    def _evaluate_safety_critical(self, goal: Dict[str, Any], context: Dict[str, Any]) -> float:
        if goal.get("safety_critical", False):
            return 100

        if goal.get("emergency", False):
            return 150

        action_type = goal.get("action_type")
        if action_type in ["arm_security", "disarm_security", "lock", "unlock"]:
            return 30

        if action_type in ["alert", "emergency_alert"]:
            return 50

        return 0.0

    def apply_priority_rules(self, goal: Dict[str, Any]) -> int:
        adjustment = 0
        reasons = []

        for rule in self.adjustment_rules:
            if not rule.enabled:
                continue

            try:
                if rule.condition(goal):
                    adjustment += rule.priority_adjustment
                    reasons.append(rule.reason)
            except Exception as e:
                logger.warning(f"Priority rule evaluation failed: {e}")

        return adjustment

    def rank_goals(
        self,
        goals: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        scored_goals = []

        for goal in goals:
            priority = self.calculate_priority(goal, context)
            rule_adjustment = self.apply_priority_rules(goal)
            total_priority = priority + rule_adjustment

            scored_goals.append({
                "goal": goal,
                "priority": total_priority,
                "base_priority": goal.get("priority", 0),
                "calculated_priority": priority,
                "rule_adjustment": rule_adjustment,
            })

        scored_goals.sort(key=lambda g: g["priority"], reverse=True)

        return [item["goal"] for item in scored_goals]

    def get_adjustment_history(
        self,
        goal_id: Optional[str] = None,
        limit: int = 100
    ) -> List[PriorityAdjustment]:
        history = self.adjustment_history

        if goal_id:
            history = [adj for adj in history if adj.goal_id == goal_id]

        return history[-limit:]

    def get_priority_statistics(self) -> Dict[str, Any]:
        total = len(self.adjustment_history)

        if total == 0:
            return {"total_adjustments": 0}

        avg_adjustment = sum(adj.new_priority - adj.original_priority for adj in self.adjustment_history) / total

        increased = sum(1 for adj in self.adjustment_history if adj.new_priority > adj.original_priority)
        decreased = sum(1 for adj in self.adjustment_history if adj.new_priority < adj.original_priority)
        unchanged = total - increased - decreased

        return {
            "total_adjustments": total,
            "average_adjustment": avg_adjustment,
            "increased": increased,
            "decreased": decreased,
            "unchanged": unchanged,
            "increase_rate": increased / total * 100,
            "decrease_rate": decreased / total * 100,
        }
