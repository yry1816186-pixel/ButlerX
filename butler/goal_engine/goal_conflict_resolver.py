from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ConflictResolutionStrategy(Enum):
    PRIORITY_BASED = "priority_based"
    TIME_BASED = "time_based"
    USER_PREFERENCE = "user_preference"
    MERGE = "merge"
    ABORT_LOWER_PRIORITY = "abort_lower_priority"
    DELAY_LOWER_PRIORITY = "delay_lower_priority"
    CUSTOM = "custom"


class ConflictSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ConflictRule:
    action_type_a: str
    action_type_b: str
    severity: ConflictSeverity
    resolution_strategy: ConflictResolutionStrategy
    metadata: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class GoalConflict:
    goal_id_a: str
    goal_id_b: str
    action_a: Dict[str, Any]
    action_b: Dict[str, Any]
    rule: ConflictRule
    severity: ConflictSeverity
    suggested_resolution: Optional[Dict[str, Any]] = None


@dataclass
class ConflictResolution:
    conflict: GoalConflict
    strategy: ConflictResolutionStrategy
    actions: List[Dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class GoalConflictResolver:
    def __init__(self):
        self.conflict_rules: List[ConflictRule] = []
        self.resolution_history: List[ConflictResolution] = []
        self.custom_resolvers: Dict[str, Callable] = {}
        self._init_default_rules()

    def _init_default_rules(self) -> None:
        self.add_conflict_rule(ConflictRule(
            action_type_a="turn_on",
            action_type_b="turn_off",
            severity=ConflictSeverity.HIGH,
            resolution_strategy=ConflictResolutionStrategy.PRIORITY_BASED,
        ))

        self.add_conflict_rule(ConflictRule(
            action_type_a="set_temperature",
            action_type_b="set_temperature",
            severity=ConflictSeverity.MEDIUM,
            resolution_strategy=ConflictResolutionStrategy.TIME_BASED,
        ))

        self.add_conflict_rule(ConflictRule(
            action_type_a="open_cover",
            action_type_b="close_cover",
            severity=ConflictSeverity.HIGH,
            resolution_strategy=ConflictResolutionStrategy.PRIORITY_BASED,
        ))

        self.add_conflict_rule(ConflictRule(
            action_type_a="lock",
            action_type_b="unlock",
            severity=ConflictSeverity.CRITICAL,
            resolution_strategy=ConflictResolutionStrategy.PRIORITY_BASED,
        ))

        self.add_conflict_rule(ConflictRule(
            action_type_a="arm_security",
            action_type_b="disarm_security",
            severity=ConflictSeverity.CRITICAL,
            resolution_strategy=ConflictResolutionStrategy.PRIORITY_BASED,
        ))

        self.add_conflict_rule(ConflictRule(
            action_type_a="set_mode",
            action_type_b="set_mode",
            severity=ConflictSeverity.MEDIUM,
            resolution_strategy=ConflictResolutionStrategy.TIME_BASED,
        ))

        self.add_conflict_rule(ConflictRule(
            action_type_a="turn_on",
            action_type_b="turn_on",
            severity=ConflictSeverity.LOW,
            resolution_strategy=ConflictResolutionStrategy.MERGE,
        ))

        self.add_conflict_rule(ConflictRule(
            action_type_a="set_brightness",
            action_type_b="set_brightness",
            severity=ConflictSeverity.LOW,
            resolution_strategy=ConflictResolutionStrategy.MERGE,
        ))

        logger.info(f"Initialized {len(self.conflict_rules)} conflict rules")

    def add_conflict_rule(self, rule: ConflictRule) -> None:
        self.conflict_rule = rule
        logger.info(f"Added conflict rule: {rule.action_type_a} vs {rule.action_type_b}")

    def remove_conflict_rule(self, action_type_a: str, action_type_b: str) -> bool:
        self.conflict_rules = [
            r for r in self.conflict_rules
            if not (r.action_type_a == action_type_a and r.action_type_b == action_type_b)
        ]
        return True

    def register_custom_resolver(self, strategy_name: str, resolver: Callable) -> None:
        self.custom_resolvers[strategy_name] = resolver
        logger.info(f"Registered custom resolver: {strategy_name}")

    def detect_conflicts(
        self,
        goal_a: Dict[str, Any],
        goal_b: Dict[str, Any]
    ) -> List[GoalConflict]:
        conflicts = []

        actions_a = goal_a.get("actions", [])
        actions_b = goal_b.get("actions", [])

        for action_a in actions_a:
            for action_b in actions_b:
                conflict = self._check_action_conflict(action_a, action_b, goal_a, goal_b)
                if conflict:
                    conflicts.append(conflict)

        return conflicts

    def _check_action_conflict(
        self,
        action_a: Dict[str, Any],
        action_b: Dict[str, Any],
        goal_a: Dict[str, Any],
        goal_b: Dict[str, Any]
    ) -> Optional[GoalConflict]:
        action_type_a = action_a.get("action_type")
        action_type_b = action_b.get("action_type")

        if not action_type_a or not action_type_b:
            return None

        params_a = action_a.get("params", {})
        params_b = action_b.get("params", {})

        for rule in self.conflict_rules:
            if not rule.enabled:
                continue

            if (rule.action_type_a == action_type_a and rule.action_type_b == action_type_b) or \
               (rule.action_type_a == action_type_b and rule.action_type_b == action_type_a):

                if self._actions_conflict(action_a, action_b, rule):
                    return GoalConflict(
                        goal_id_a=goal_a.get("goal_id", ""),
                        goal_id_b=goal_b.get("goal_id", ""),
                        action_a=action_a,
                        action_b=action_b,
                        rule=rule,
                        severity=rule.severity,
                    )

        return None

    def _actions_conflict(self, action_a: Dict[str, Any], action_b: Dict[str, Any], rule: ConflictRule) -> bool:
        action_type_a = action_a.get("action_type")
        action_type_b = action_b.get("action_type")

        params_a = action_a.get("params", {})
        params_b = action_b.get("params", {})

        if rule.resolution_strategy == ConflictResolutionStrategy.PRIORITY_BASED:
            if action_type_a in ["turn_on", "turn_off"] and action_type_b in ["turn_on", "turn_off"]:
                target_a = params_a.get("target")
                target_b = params_b.get("target")
                return target_a == target_b

            if action_type_a in ["open_cover", "close_cover"] and action_type_b in ["open_cover", "close_cover"]:
                target_a = params_a.get("target")
                target_b = params_b.get("target")
                return target_a == target_b

            if action_type_a in ["lock", "unlock"] and action_type_b in ["lock", "unlock"]:
                target_a = params_a.get("target")
                target_b = params_b.get("target")
                return target_a == target_b

            if action_type_a == "arm_security" and action_type_b == "disarm_security":
                return True

            if action_type_a == "disarm_security" and action_type_b == "arm_security":
                return True

        if rule.resolution_strategy == ConflictResolutionStrategy.TIME_BASED:
            if action_type_a == action_type_b:
                target_a = params_a.get("target")
                target_b = params_b.get("target")
                return target_a == target_b

        if rule.resolution_strategy == ConflictResolutionStrategy.MERGE:
            if action_type_a == action_type_b:
                target_a = params_a.get("target")
                target_b = params_b.get("target")
                return target_a == target_b

        return False

    async def resolve_conflict(
        self,
        conflict: GoalConflict,
        goal_a: Dict[str, Any],
        goal_b: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ConflictResolution:
        context = context or {}
        strategy = conflict.rule.resolution_strategy

        if strategy == ConflictResolutionStrategy.PRIORITY_BASED:
            resolution = self._resolve_priority_based(conflict, goal_a, goal_b)
        elif strategy == ConflictResolutionStrategy.TIME_BASED:
            resolution = self._resolve_time_based(conflict, goal_a, goal_b)
        elif strategy == ConflictResolutionStrategy.MERGE:
            resolution = self._resolve_merge(conflict, goal_a, goal_b)
        elif strategy == ConflictResolutionStrategy.ABORT_LOWER_PRIORITY:
            resolution = self._resolve_abort_lower(conflict, goal_a, goal_b)
        elif strategy == ConflictResolutionStrategy.DELAY_LOWER_PRIORITY:
            resolution = self._resolve_delay_lower(conflict, goal_a, goal_b)
        elif strategy == ConflictResolutionStrategy.CUSTOM:
            resolution = self._resolve_custom(conflict, goal_a, goal_b, context)
        else:
            resolution = ConflictResolution(
                conflict=conflict,
                strategy=strategy,
                reason="Unknown resolution strategy",
            )

        self.resolution_history.append(resolution)
        return resolution

    def _resolve_priority_based(
        self,
        conflict: GoalConflict,
        goal_a: Dict[str, Any],
        goal_b: Dict[str, Any]
    ) -> ConflictResolution:
        priority_a = goal_a.get("priority", 0)
        priority_b = goal_b.get("priority", 0)

        if priority_a >= priority_b:
            actions = [conflict.action_a]
            reason = f"Goal {conflict.goal_id_a} has higher priority ({priority_a} >= {priority_b})"
        else:
            actions = [conflict.action_b]
            reason = f"Goal {conflict.goal_id_b} has higher priority ({priority_b} > {priority_a})"

        return ConflictResolution(
            conflict=conflict,
            strategy=ConflictResolutionStrategy.PRIORITY_BASED,
            actions=actions,
            reason=reason,
        )

    def _resolve_time_based(
        self,
        conflict: GoalConflict,
        goal_a: Dict[str, Any],
        goal_b: Dict[str, Any]
    ) -> ConflictResolution:
        time_a = goal_a.get("created_at", 0)
        time_b = goal_b.get("created_at", 0)

        if time_a >= time_b:
            actions = [conflict.action_a]
            reason = f"Goal {conflict.goal_id_a} is more recent ({time_a} >= {time_b})"
        else:
            actions = [conflict.action_b]
            reason = f"Goal {conflict.goal_id_b} is more recent ({time_b} > {time_a})"

        return ConflictResolution(
            conflict=conflict,
            strategy=ConflictResolutionStrategy.TIME_BASED,
            actions=actions,
            reason=reason,
        )

    def _resolve_merge(
        self,
        conflict: GoalConflict,
        goal_a: Dict[str, Any],
        goal_b: Dict[str, Any]
    ) -> ConflictResolution:
        params_a = conflict.action_a.get("params", {})
        params_b = conflict.action_b.get("params", {})

        merged_params = {}
        for key, value in params_a.items():
            merged_params[key] = value
        for key, value in params_b.items():
            if key in merged_params:
                if isinstance(value, (int, float)):
                    merged_params[key] = max(merged_params[key], value)
                elif isinstance(value, bool):
                    merged_params[key] = merged_params[key] or value
            else:
                merged_params[key] = value

        merged_action = {
            "action_type": conflict.action_a.get("action_type"),
            "params": merged_params,
        }

        return ConflictResolution(
            conflict=conflict,
            strategy=ConflictResolutionStrategy.MERGE,
            actions=[merged_action],
            reason=f"Merged actions from {conflict.goal_id_a} and {conflict.goal_id_b}",
            metadata={"merged_params": merged_params},
        )

    def _resolve_abort_lower(
        self,
        conflict: GoalConflict,
        goal_a: Dict[str, Any],
        goal_b: Dict[str, Any]
    ) -> ConflictResolution:
        priority_a = goal_a.get("priority", 0)
        priority_b = goal_b.get("priority", 0)

        if priority_a >= priority_b:
            actions = [conflict.action_a]
            reason = f"Goal {conflict.goal_id_b} aborted due to lower priority"
        else:
            actions = [conflict.action_b]
            reason = f"Goal {conflict.goal_id_a} aborted due to lower priority"

        return ConflictResolution(
            conflict=conflict,
            strategy=ConflictResolutionStrategy.ABORT_LOWER_PRIORITY,
            actions=actions,
            reason=reason,
            metadata={"aborted_goal_id": conflict.goal_id_b if priority_a >= priority_b else conflict.goal_id_a},
        )

    def _resolve_delay_lower(
        self,
        conflict: GoalConflict,
        goal_a: Dict[str, Any],
        goal_b: Dict[str, Any]
    ) -> ConflictResolution:
        priority_a = goal_a.get("priority", 0)
        priority_b = goal_b.get("priority", 0)

        if priority_a >= priority_b:
            actions = [conflict.action_a]
            reason = f"Goal {conflict.goal_id_b} delayed due to lower priority"
        else:
            actions = [conflict.action_b]
            reason = f"Goal {conflict.goal_id_a} delayed due to lower priority"

        return ConflictResolution(
            conflict=conflict,
            strategy=ConflictResolutionStrategy.DELAY_LOWER_PRIORITY,
            actions=actions,
            reason=reason,
            metadata={"delayed_goal_id": conflict.goal_id_b if priority_a >= priority_b else conflict.goal_id_a},
        )

    def _resolve_custom(
        self,
        conflict: GoalConflict,
        goal_a: Dict[str, Any],
        goal_b: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ConflictResolution:
        strategy_name = conflict.rule.metadata.get("custom_strategy")
        if strategy_name and strategy_name in self.custom_resolvers:
            try:
                resolver = self.custom_resolvers[strategy_name]
                result = resolver(conflict, goal_a, goal_b, context)
                return ConflictResolution(
                    conflict=conflict,
                    strategy=ConflictResolutionStrategy.CUSTOM,
                    actions=result.get("actions", []),
                    reason=result.get("reason", ""),
                    metadata=result.get("metadata", {}),
                )
            except Exception as e:
                logger.error(f"Custom resolver failed: {e}")

        return ConflictResolution(
            conflict=conflict,
            strategy=ConflictResolutionStrategy.CUSTOM,
            reason="Custom resolver not found or failed",
        )

    def get_conflict_statistics(self) -> Dict[str, Any]:
        total = len(self.resolution_history)

        by_severity = {s.value: 0 for s in ConflictSeverity}
        by_strategy = {s.value: 0 for s in ConflictResolutionStrategy}

        for resolution in self.resolution_history:
            by_severity[resolution.conflict.severity.value] += 1
            by_strategy[resolution.strategy.value] += 1

        return {
            "total_resolutions": total,
            "by_severity": by_severity,
            "by_strategy": by_strategy,
        }
