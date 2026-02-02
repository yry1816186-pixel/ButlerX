from __future__ import annotations

from typing import Any, Dict

from ..core.utils import utc_ts


def send_notification(title: str, message: str, level: str = "info") -> Dict[str, Any]:
    return {
        "status": "ok",
        "title": title,
        "message": message,
        "level": level,
        "ts": utc_ts(),
    }
