from __future__ import annotations

from typing import Any, Dict


def map_ha_event(raw_event: Dict[str, Any]) -> Dict[str, Any]:
    """Map Home Assistant event to Butler standard event payload."""
    return {
        "source": "ha",
        "type": raw_event.get("type", "arrival"),
        "payload": raw_event.get("payload", {}),
        "severity": int(raw_event.get("severity", 1)),
    }
