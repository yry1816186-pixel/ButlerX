from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .glm_client import GLMClient, GLMConfig, normalize_image_inputs, try_parse_json
from ..core.models import ActionPlan
from ..core.utils import new_uuid, utc_ts

logger = logging.getLogger(__name__)


@dataclass
class BrainRequest:
    text: str
    images: List[Any] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrainPlanResult:
    plan: Optional[ActionPlan]
    raw: Dict[str, Any]
    vision: Optional[Dict[str, Any]] = None
    cached: bool = False


@dataclass
class BrainPlannerConfig:
    max_actions: int = 6
    cache_ttl_sec: int = 30
    cache_size: int = 128
    retry_attempts: int = 1
    allowed_actions: List[str] = field(default_factory=list)
    system_exec_allowlist: List[str] = field(default_factory=list)
    script_allowlist: List[str] = field(default_factory=list)


@dataclass
class _CacheEntry:
    ts: float
    result: BrainPlanResult


class BrainPlanner:
    def __init__(self, glm: GLMClient, config: Optional[BrainPlannerConfig] = None) -> None:
        self.glm = glm
        self.config = config or BrainPlannerConfig()
        
        # 验证并标准化配置参数
        try:
            self.config.cache_ttl_sec = max(int(self.config.cache_ttl_sec), 0)
        except (ValueError, TypeError):
            logger.warning(f"Invalid cache_ttl_sec: {self.config.cache_ttl_sec}, using default 30")
            self.config.cache_ttl_sec = 30
            
        try:
            self.config.cache_size = max(int(self.config.cache_size), 0)
        except (ValueError, TypeError):
            logger.warning(f"Invalid cache_size: {self.config.cache_size}, using default 128")
            self.config.cache_size = 128
            
        try:
            self.config.max_actions = max(int(self.config.max_actions), 1)
        except (ValueError, TypeError):
            logger.warning(f"Invalid max_actions: {self.config.max_actions}, using default 6")
            self.config.max_actions = 6
            
        try:
            self.config.retry_attempts = max(int(self.config.retry_attempts), 0)
        except (ValueError, TypeError):
            logger.warning(f"Invalid retry_attempts: {self.config.retry_attempts}, using default 1")
            self.config.retry_attempts = 1
            
        self._cache: "OrderedDict[str, _CacheEntry]" = OrderedDict()

    def plan(self, req: BrainRequest, use_cache: bool = True) -> BrainPlanResult:
        cache_key = self._build_cache_key(req)
        if use_cache:
            cached = self._get_cache(cache_key)
            if cached is not None:
                return cached

        vision_payload = None
        if req.images:
            vision_payload = self._run_vision(req)

        plan_json = self._run_plan(req, vision_payload)
        plan = self._build_plan(plan_json, req)

        result = BrainPlanResult(plan=plan, raw=plan_json, vision=vision_payload, cached=False)
        if use_cache:
            self._set_cache(cache_key, result)
        return result

    def _run_vision(self, req: BrainRequest) -> Optional[Dict[str, Any]]:
        if not self.glm.config.model_vision:
            logger.warning("Vision requested but model_vision is not configured")
            return None

        content: List[Dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "You are a vision sensor for a home assistant. "
                    "Return JSON only with keys: summary, objects, hazards, people. "
                    "Use short strings."
                ),
            }
        ]
        content.extend(normalize_image_inputs(req.images))
        messages = [{"role": "user", "content": content}]
        text, raw = self.glm.chat(messages=messages, model=self.glm.config.model_vision)
        parsed = try_parse_json(text)
        if parsed is None:
            parsed = {"summary": text.strip()}
        parsed["_raw"] = raw
        return parsed

    def _run_plan(self, req: BrainRequest, vision_payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        system_prompt = self._system_prompt()
        user_context = {
            "text": req.text,
            "vision": vision_payload or {},
            "context": req.context,
        }
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(user_context, ensure_ascii=False),
            },
        ]
        text, raw = self.glm.chat(messages=messages)
        parsed = try_parse_json(text)
        attempts = max(int(self.config.retry_attempts), 0)
        retry_index = 0
        while parsed is None and retry_index < attempts:
            retry_index += 1
            retry_prompt = (
                "Previous response was invalid JSON. "
                "Return ONLY valid JSON for the same input. No markdown, no comments."
            )
            retry_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "assistant", "content": text},
                {"role": "user", "content": retry_prompt},
            ]
            text, raw = self.glm.chat(messages=retry_messages)
            parsed = try_parse_json(text)
        if parsed is None:
            parsed = {"actions": [], "reason": "LLM output was not valid JSON", "raw": text}
        parsed["_raw"] = raw
        return parsed

    def _build_plan(self, payload: Dict[str, Any], req: BrainRequest) -> Optional[ActionPlan]:
        actions = payload.get("actions")
        if not isinstance(actions, list):
            return None
        cleaned = []
        skipped = 0
        allowed = set([item for item in self.config.allowed_actions if item])
        allowlist = set([cmd for cmd in self.config.system_exec_allowlist if cmd])
        script_allowlist = set([name for name in self.config.script_allowlist if name])
        for item in actions:
            if not isinstance(item, dict):
                skipped += 1
                continue
            action_type = str(item.get("action_type") or "").strip()
            if not action_type:
                skipped += 1
                continue
            if allowed and action_type not in allowed:
                skipped += 1
                continue
            params = item.get("params")
            if not isinstance(params, dict):
                params = {}
            if action_type == "system_exec":
                command = str(params.get("command") or "").strip()
                if allowlist and command not in allowlist:
                    skipped += 1
                    continue
            if action_type == "script_run":
                script = str(params.get("script") or params.get("name") or "").strip()
                if not script:
                    skipped += 1
                    continue
                if script_allowlist and script not in script_allowlist:
                    skipped += 1
                    continue
            if action_type == "openclaw_message_send":
                target = str(params.get("target") or "").strip()
                message = str(params.get("message") or "").strip()
                if not target or not message:
                    skipped += 1
                    continue
            cleaned.append({"action_type": action_type, "params": params})

        if not cleaned:
            return None
        max_actions = max(int(self.config.max_actions), 1)
        if len(cleaned) > max_actions:
            cleaned = cleaned[:max_actions]

        reason = payload.get("reason") or req.text[:120]
        if skipped > 0:
            reason = f"{reason} (skipped {skipped} unsupported actions)"

        return ActionPlan(
            plan_id=new_uuid(),
            triggered_by_event_id=payload.get("event_id") or "brain",
            actions=cleaned,
            policy=payload.get("policy") or "LLM_PLAN",
            reason=reason,
            created_ts=utc_ts(),
        )

    def _system_prompt(self) -> str:
        allowlist = ", ".join(self.config.system_exec_allowlist) or "none"
        script_allowlist = ", ".join(self.config.script_allowlist) or "none"
        return (
            "You are the planning brain of a home assistant. "
            "Return JSON only. Do not include markdown. "
            "Schema: {policy, reason, actions:[{action_type, params}]}. "
            "Available action_type values:\n"
            "- notify: {title, message, level}\n"
            "- ha_call_service: {domain, service, data}\n"
            "- ptz_goto_preset: {name}\n"
            "- ptz_patrol: {presets, dwell_s}\n"
            "- ptz_stop: {}\n"
            "- snapshot: {}\n"
            "- store_event: {kind, ...}\n"
            "- email_read: {limit, folder, unread_only}\n"
            "- email_send: {to, subject, body, from?}\n"
            "- image_generate: {prompt, size, n}\n"
            "- vision_detect: {image or images, model, min_conf?, max_det?, match_faces?, top_k?}\n"
            "- face_enroll: {label, image, face_index?}\n"
            "- face_verify: {image, label?, faceprint_id?}\n"
            "- voice_transcribe: {audio, language?, prompt?}\n"
            "- voice_enroll: {label, audio}\n"
            "- voice_verify: {voiceprint_id?, label?, audio}\n"
            "- wakeword_detect: {text?, audio?}\n"
            "- web_search: {query, limit}\n"
            "- gateway_request: {method, path, body?}\n"
            "- system_exec: {command, args}\n"
            "- script_run: {script, args}\n"
            "- schedule_task: {run_at or delay_sec, actions, note}\n"
            "- openclaw_message_send: {target, message, channel?, account?}\n"
            f"system_exec allowlist: {allowlist}\n"
            f"script_run allowlist: {script_allowlist}\n"
            "If no action is needed, return {actions:[]}"
        )


    def _build_cache_key(self, req: BrainRequest) -> str:
        image_keys = self._image_fingerprints(req.images)
        payload = {
            "text": req.text,
            "context": req.context,
            "images": image_keys,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _image_fingerprints(images: Iterable[Any]) -> List[str]:
        out: List[str] = []
        for item in images:
            if isinstance(item, dict):
                if isinstance(item.get("url"), str) and item.get("url"):
                    out.append(item["url"])
                    continue
                if isinstance(item.get("base64"), str) and item.get("base64"):
                    out.append(BrainPlanner._hash_string(item["base64"]))
                    continue
            if isinstance(item, str):
                if item.startswith("http"):
                    out.append(item)
                else:
                    out.append(BrainPlanner._hash_string(item))
            else:
                out.append(str(item))
        return out

    @staticmethod
    def _hash_string(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _get_cache(self, key: str) -> Optional[BrainPlanResult]:
        if not key:
            return None
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() - entry.ts > self.config.cache_ttl_sec:
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return BrainPlanResult(
            plan=entry.result.plan,
            raw=entry.result.raw,
            vision=entry.result.vision,
            cached=True,
        )

    def _set_cache(self, key: str, result: BrainPlanResult) -> None:
        if not key or self.config.cache_ttl_sec <= 0 or self.config.cache_size <= 0:
            return
        self._cache[key] = _CacheEntry(ts=time.time(), result=result)
        self._cache.move_to_end(key)
        while len(self._cache) > self.config.cache_size:
            self._cache.popitem(last=False)


def build_planner_from_config(
    config: GLMConfig, planner_config: Optional[BrainPlannerConfig] = None
) -> BrainPlanner:
    return BrainPlanner(GLMClient(config), planner_config)
