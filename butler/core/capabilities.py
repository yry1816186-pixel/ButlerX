from __future__ import annotations

from typing import Any, Dict, List


def action_catalog() -> List[Dict[str, Any]]:
    return [
        {
            "action_type": "notify",
            "params": {"title": "string", "message": "string", "level": "info|warning|critical"},
        },
        {
            "action_type": "ha_call_service",
            "params": {"domain": "string", "service": "string", "data": "object"},
        },
        {"action_type": "ptz_goto_preset", "params": {"name": "string"}},
        {"action_type": "ptz_patrol", "params": {"presets": "list", "dwell_s": "int"}},
        {"action_type": "ptz_stop", "params": {}},
        {"action_type": "snapshot", "params": {}},
        {"action_type": "store_event", "params": {"kind": "string", "...": "any"}},
        {"action_type": "email_read", "params": {"limit": "int", "folder": "string", "unread_only": "bool"}},
        {
            "action_type": "email_send",
            "params": {"to": "list|string", "subject": "string", "body": "string", "from": "string?"},
        },
        {
            "action_type": "image_generate",
            "params": {"prompt": "string", "size": "string", "n": "int"},
        },
        {
            "action_type": "vision_detect",
            "params": {
                "image": "base64|url|path",
                "images": "list?",
                "model": "object|face",
                "min_conf": "float?",
                "max_det": "int?",
                "match_faces": "bool?",
                "top_k": "int?",
            },
        },
        {
            "action_type": "face_enroll",
            "params": {"label": "string", "image": "base64|url|path", "face_index": "int?"},
        },
        {
            "action_type": "face_verify",
            "params": {
                "image": "base64|url|path",
                "label": "string?",
                "faceprint_id": "string?",
            },
        },
        {
            "action_type": "voice_transcribe",
            "params": {"audio": "base64|url", "language": "string?", "prompt": "string?"},
        },
        {
            "action_type": "voice_enroll",
            "params": {"label": "string", "audio": "base64|url"},
        },
        {
            "action_type": "voice_verify",
            "params": {"voiceprint_id": "string?", "label": "string?", "audio": "base64|url"},
        },
        {
            "action_type": "wakeword_detect",
            "params": {"text": "string?", "audio": "base64|url?"},
        },
        {
            "action_type": "web_search",
            "params": {"query": "string", "limit": "int"},
        },
        {
            "action_type": "gateway_request",
            "params": {"method": "GET|POST", "path": "/path", "body": "object?"},
        },
        {
            "action_type": "system_exec",
            "params": {"command": "string", "args": "list"},
        },
        {"action_type": "script_run", "params": {"script": "string", "args": "list"}},
        {
            "action_type": "schedule_task",
            "params": {"run_at": "int", "delay_sec": "int", "actions": "list", "note": "string"},
        },
        {
            "action_type": "openclaw_message_send",
            "params": {"target": "string", "message": "string", "channel": "string?", "account": "string?"},
        },
    ]
