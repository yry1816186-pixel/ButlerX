from __future__ import annotations

import os
from typing import Any, Dict

from ..core.utils import new_uuid, utc_ts


def store_event(kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    record_id = new_uuid()
    base_path = os.getenv("EVIDENCE_BASE_PATH", "/evidence").rstrip("/")
    output: Dict[str, Any] = {
        "status": "ok",
        "kind": kind,
        "record_id": record_id,
        "path": f"/app/butler/data/{kind}/{record_id}.bin",
        "payload": payload,
        "ts": utc_ts(),
    }
    kind_lower = kind.lower()
    if kind_lower in {"snapshot", "image"}:
        output["snapshot_ref"] = f"{base_path}/snapshot/{record_id}"
    elif kind_lower in {"record", "clip", "video"}:
        output["clip_ref"] = f"{base_path}/clip/{record_id}"
    return output
