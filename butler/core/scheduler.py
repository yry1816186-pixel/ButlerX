from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional

from .models import ActionPlan
from .utils import new_uuid, utc_ts


class ScheduleRunner:
    def __init__(
        self,
        db,
        tool_runner,
        get_privacy_mode: Callable[[], bool],
        on_plan: Callable[[Dict[str, Any]], None],
        on_result: Callable[[Dict[str, Any]], None],
        interval_sec: int = 5,
    ) -> None:
        self.db = db
        self.tool_runner = tool_runner
        self.get_privacy_mode = get_privacy_mode
        self.on_plan = on_plan
        self.on_result = on_result
        self.interval_sec = max(int(interval_sec), 1)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def schedule_actions(self, actions: List[Dict[str, Any]], run_at: int, note: str = "") -> Dict[str, Any]:
        schedule = {
            "schedule_id": new_uuid(),
            "run_at": int(run_at),
            "actions": actions,
            "status": "pending",
            "created_ts": utc_ts(),
            "note": note,
        }
        self.db.insert_schedule(schedule)
        return schedule

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            now = utc_ts()
            due = self.db.get_due_schedules(now, limit=10)
            for entry in due:
                self._execute_schedule(entry)
            self._stop.wait(self.interval_sec)

    def _execute_schedule(self, entry: Dict[str, Any]) -> None:
        schedule_id = entry.get("schedule_id")
        actions = entry.get("actions") or []
        if not schedule_id or not isinstance(actions, list) or not actions:
            if schedule_id:
                self.db.mark_schedule_done(schedule_id)
            return

        self.db.mark_schedule_done(schedule_id)
        plan = ActionPlan(
            plan_id=new_uuid(),
            triggered_by_event_id=schedule_id,
            actions=actions,
            policy="SCHEDULE",
            reason=entry.get("note") or "Scheduled task",
            created_ts=utc_ts(),
        )
        plan_dict = plan.to_dict()
        self.on_plan(plan_dict)

        privacy_mode = self.get_privacy_mode()
        results = self.tool_runner.execute_plan(plan.plan_id, plan.actions, privacy_mode)
        for result in results:
            self.on_result(result.to_dict())
