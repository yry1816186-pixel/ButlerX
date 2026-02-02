from __future__ import annotations

import os
from typing import Any, Dict, List

from ..core.utils import new_uuid, utc_ts


class PTZOnvif:
    def __init__(self, mock: bool = True) -> None:
        self.mock = mock

    def goto_preset(self, name: str) -> Dict[str, Any]:
        return {
            "status": "ok",
            "output": {"preset": name, "ts": utc_ts()},
        }

    def patrol(self, presets: List[str], dwell_s: int) -> Dict[str, Any]:
        return {
            "status": "ok",
            "output": {"presets": presets, "dwell_s": dwell_s, "ts": utc_ts()},
        }

    def stop(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "output": {"stopped": True, "ts": utc_ts()},
        }

    def snapshot(self) -> Dict[str, Any]:
        snapshot_id = new_uuid()
        base_path = os.getenv("EVIDENCE_BASE_PATH", "/evidence").rstrip("/")
        return {
            "status": "ok",
            "output": {
                "snapshot_ref": f"{base_path}/snapshot/{snapshot_id}",
                "ts": utc_ts(),
            },
        }
