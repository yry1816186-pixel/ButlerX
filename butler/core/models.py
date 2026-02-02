from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Event:
    event_id: str
    ts: int
    source: str
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    severity: int = 0
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "ts": self.ts,
            "source": self.source,
            "type": self.type,
            "payload": self.payload,
            "severity": self.severity,
            "correlation_id": self.correlation_id,
        }


@dataclass
class ActionPlan:
    plan_id: str
    triggered_by_event_id: str
    actions: List[Dict[str, Any]]
    policy: str
    reason: str
    created_ts: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "triggered_by_event_id": self.triggered_by_event_id,
            "actions": self.actions,
            "policy": self.policy,
            "reason": self.reason,
            "created_ts": self.created_ts,
        }


@dataclass
class ActionResult:
    plan_id: str
    action_type: str
    status: str
    output: Dict[str, Any]
    ts: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "action_type": self.action_type,
            "status": self.status,
            "output": self.output,
            "ts": self.ts,
        }
