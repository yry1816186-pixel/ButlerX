from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..core.models import ActionPlan
from ..core.utils import new_uuid, utc_ts

logger = logging.getLogger(__name__)


@dataclass
class BrainRule:
    rule_id: str
    all: List[str] = field(default_factory=list)
    any: List[str] = field(default_factory=list)
    not_: List[str] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    policy: str = "RULE"
    reason: str = "Matched rule"
    enabled: bool = True


class BrainRuleEngine:
    def __init__(self, rules: List[BrainRule]) -> None:
        self.rules = rules

    @classmethod
    def from_config(cls, config: List[Dict[str, Any]]) -> "BrainRuleEngine":
        rules: List[BrainRule] = []
        for item in config or []:
            if not isinstance(item, dict):
                continue
            rule_id = str(item.get("id") or item.get("rule_id") or "").strip()
            if not rule_id:
                continue
            actions = item.get("actions") or []
            if not isinstance(actions, list):
                actions = []
            rules.append(
                BrainRule(
                    rule_id=rule_id,
                    all=_to_list(item.get("all")),
                    any=_to_list(item.get("any")),
                    not_=_to_list(item.get("not")),
                    actions=[a for a in actions if isinstance(a, dict)],
                    policy=str(item.get("policy") or f"RULE_{rule_id}"),
                    reason=str(item.get("reason") or "Matched rule"),
                    enabled=bool(item.get("enabled", True)),
                )
            )
        return cls(rules)

    def match(self, text: str) -> Tuple[Optional[ActionPlan], Dict[str, Any]]:
        normalized = (text or "").strip().lower()
        trace: Dict[str, Any] = {"source": "rules", "matched": False, "rule_id": None}
        if not normalized:
            return None, trace

        for rule in self.rules:
            if not rule.enabled:
                continue
            if not _contains_all(normalized, rule.all):
                continue
            if rule.any and not _contains_any(normalized, rule.any):
                continue
            if rule.not_ and _contains_any(normalized, rule.not_):
                continue
            if not rule.actions:
                continue
            actions = _normalize_actions(rule.actions)
            if not actions:
                continue
            trace = {"source": "rules", "matched": True, "rule_id": rule.rule_id}
            plan = ActionPlan(
                plan_id=new_uuid(),
                triggered_by_event_id="brain",
                actions=actions,
                policy=rule.policy,
                reason=rule.reason,
                created_ts=utc_ts(),
            )
            return plan, trace

        return None, trace


def _to_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _contains_all(text: str, tokens: List[str]) -> bool:
    return all(token.lower() in text for token in tokens if token)


def _contains_any(text: str, tokens: List[str]) -> bool:
    return any(token.lower() in text for token in tokens if token)


def _normalize_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned = []
    for item in actions:
        action_type = str(item.get("action_type") or "").strip()
        if not action_type:
            continue
        params = item.get("params")
        if not isinstance(params, dict):
            params = {}
        cleaned.append({"action_type": action_type, "params": params})
    return cleaned
