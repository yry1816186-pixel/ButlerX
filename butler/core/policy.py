from __future__ import annotations

from typing import List

from .config import ButlerConfig
from .db import Database
from .models import ActionPlan, Event
from .utils import new_uuid, utc_ts


class PolicyEngine:
    def __init__(self, db: Database, config: ButlerConfig) -> None:
        self.db = db
        self.config = config

    def evaluate(self, event: Event) -> List[ActionPlan]:
        plans: List[ActionPlan] = []
        mode = self.db.get_state("mode", self.config.mode_default)

        # Only process zone_person_detected events in arrival_zone
        if not (event.type == "zone_person_detected" and event.payload.get("zone") == self.config.arrival_zone):
            return plans

        # R1: Arrival notification when mode is not "away"
        if mode != "away" and self._cooldown_ok("R1_arrival", self.config.r1_cooldown_sec):
            cooldown_min = max(int(self.config.r1_cooldown_sec / 60), 1)
            reason = (
                f"entry_zone={self.config.arrival_zone}, "
                f"mode={mode}, cooldown>={cooldown_min}m"
            )
            plans.append(
                ActionPlan(
                    plan_id=new_uuid(),
                    triggered_by_event_id=event.event_id,
                    actions=[
                        {
                            "action_type": "notify",
                            "params": {
                                "title": self.config.arrival_notify_title,
                                "message": self.config.arrival_notify_message,
                                "level": "info",
                            },
                        }
                    ],
                    policy="R1_arrival",
                    reason=reason,
                    created_ts=utc_ts(),
                )
            )
        # R2: Intrusion alert when mode is "away"
        elif mode == "away":
            since_ts = max(event.ts - self.config.intrusion_window_sec, 0)
            count = self.db.count_events(
                "zone_person_detected",
                since_ts,
                {"zone": self.config.arrival_zone},
            )
            if count >= self.config.intrusion_count_threshold:
                window_sec = self.config.intrusion_window_sec
                reason = (
                    f"entry_zone={self.config.arrival_zone}, mode=away, "
                    f"count={count} within {window_sec}s"
                )
                camera = event.payload.get("camera", self.config.intrusion_camera_default)
                plans.append(
                    ActionPlan(
                        plan_id=new_uuid(),
                        triggered_by_event_id=event.event_id,
                        actions=[
                            {
                                "action_type": "notify",
                                "params": {
                                    "title": "Intrusion alert",
                                    "message": f"Entry activity detected at {camera}.",
                                    "level": "critical",
                                },
                            },
                            {
                                "action_type": "store_event",
                                "params": {
                                    "kind": "record",
                                    "camera": camera,
                                    "duration_sec": self.config.intrusion_record_duration_sec,
                                },
                            },
                        ],
                        policy="R2_intrusion_entry",
                        reason=reason,
                        created_ts=utc_ts(),
                    )
                )

        return plans

    def _cooldown_ok(self, policy: str, cooldown_sec: int) -> bool:
        last_ts = self.db.get_last_plan_ts(policy)
        if last_ts is None:
            return True
        return (utc_ts() - last_ts) > cooldown_sec
