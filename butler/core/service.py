from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import paho.mqtt.client as mqtt

from .config import ButlerConfig
from ..brain import BrainPlanner, BrainPlanResult, BrainRequest, BrainRuleEngine
from ..brain.planner import BrainPlannerConfig
from ..brain.glm_client import GLMClient, GLMConfig
from .scheduler import ScheduleRunner
from .db import Database
from .models import ActionPlan, Event
from .policy import PolicyEngine
from .tool_runner import ToolRunner
from .utils import new_uuid, utc_ts
from ..devices import DaShanAdapter, DaShanConfig

logger = logging.getLogger(__name__)


class ButlerService:
    def __init__(self, config: ButlerConfig) -> None:
        self.config = config
        self.db = Database(config.db_path)
        self.policy = PolicyEngine(self.db, config)
        self.tool_runner = ToolRunner(config, db=self.db)
        self.mqtt_host = config.mqtt_host
        self.mqtt_port = config.mqtt_port
        self.topic_in_event = self._normalize_topics(config.topic_in_event)
        self.topic_in_command = self._normalize_topics(config.topic_in_command)
        self.topic_out_event = self._normalize_topics(config.topic_out_event)
        self.topic_out_action_plan = self._normalize_topics(config.topic_out_action_plan)
        self.topic_out_action_result = self._normalize_topics(config.topic_out_action_result)
        self.client = mqtt.Client(client_id=f"butler-core-{new_uuid()}")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.brain_allowed_actions = [
            "notify",
            "ha_call_service",
            "ptz_goto_preset",
            "ptz_patrol",
            "ptz_stop",
            "snapshot",
            "store_event",
            "email_read",
            "email_send",
            "image_generate",
            "vision_detect",
            "face_enroll",
            "face_verify",
            "voice_transcribe",
            "voice_enroll",
            "voice_verify",
            "wakeword_detect",
            "web_search",
            "gateway_request",
            "system_exec",
            "script_run",
            "schedule_task",
            "openclaw_message_send",
            "device_turn_on",
            "device_turn_off",
            "device_toggle",
            "set_brightness",
            "set_temperature",
            "set_hvac_mode",
            "open_cover",
            "close_cover",
            "play_media",
            "pause_media",
            "stop_media",
            "ir_send_command",
            "ir_learn_command",
            "get_device_state",
            "list_devices",
            "sync_ha_devices",
            "activate_scene",
            "execute_goal",
            "get_goals",
            "get_scenes",
        ]
        self.brain_client = GLMClient(
            GLMConfig(
                api_key=config.llm_api_key,
                base_url=config.llm_base_url,
                model_text=config.llm_model_text,
                model_vision=config.llm_model_vision,
                timeout_sec=config.llm_timeout_sec,
                temperature=config.llm_temperature,
                max_tokens=config.llm_max_tokens,
                top_p=config.llm_top_p,
            )
        )
        self.brain = BrainPlanner(
            self.brain_client,
            BrainPlannerConfig(
                max_actions=config.brain_max_actions,
                cache_ttl_sec=config.brain_cache_ttl_sec,
                cache_size=config.brain_cache_size,
                retry_attempts=config.brain_retry_attempts,
                allowed_actions=self.brain_allowed_actions,
                system_exec_allowlist=config.system_exec_allowlist,
                script_allowlist=config.script_allowlist,
            ),
        )
        self.rule_engine = BrainRuleEngine.from_config(config.brain_rules)
        self.scheduler = None
        if config.scheduler_enabled:
            self.scheduler = ScheduleRunner(
                db=self.db,
                tool_runner=self.tool_runner,
                get_privacy_mode=lambda: bool(
                    self.db.get_state("privacy_mode", self.config.privacy_mode_default)
                ),
                on_plan=self._record_plan,
                on_result=self._record_result,
                interval_sec=config.scheduler_interval_sec,
            )
            self.tool_runner.attach_scheduler(self.scheduler)
        if self.db.get_state("privacy_mode", None) is None:
            self.db.set_state("privacy_mode", bool(self.config.privacy_mode_default))
        if self.db.get_state("mode", None) is None:
            self.db.set_state("mode", self.config.mode_default)
        self.sub_topics = self._normalize_topics(config.sub_topics)
        self.publish_topics = self._normalize_topics(config.publish_topics)
        
        self.dashan_adapter: Optional[DaShanAdapter] = None
        if config.dashan_enabled:
            dashan_config = DaShanConfig(
                mqtt_host=config.dashan_mqtt_host,
                mqtt_port=config.dashan_mqtt_port,
                mqtt_username=config.dashan_mqtt_username,
                mqtt_password=config.dashan_mqtt_password,
                client_id=f"butler-dashan-{new_uuid()}"
            )
            self.dashan_adapter = DaShanAdapter(dashan_config)
            self.dashan_adapter.on_status_update(self._on_dashan_status)
            self.dashan_adapter.on_log_entry(self._on_dashan_log)
            self.dashan_adapter.on_image_data(self._on_dashan_image)
            logger.info("DaShan adapter initialized")

    def start(self) -> None:
        logger.info("Connecting to MQTT %s:%s", self.mqtt_host, self.mqtt_port)
        self.client.reconnect_delay_set(
            min_delay=self.config.mqtt_reconnect_min_sec,
            max_delay=self.config.mqtt_reconnect_max_sec,
        )
        self.client.connect_async(
            self.mqtt_host,
            self.mqtt_port,
            keepalive=self.config.mqtt_keepalive_sec,
        )
        self.client.loop_start()
        if self.scheduler:
            self.scheduler.start()
        if self.dashan_adapter:
            self.dashan_adapter.connect()

    def stop(self) -> None:
        self.brain_client.close()
        if self.scheduler:
            self.scheduler.stop()
        if self.dashan_adapter:
            self.dashan_adapter.disconnect()
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, topics: List[str], payload: Dict[str, Any]) -> None:
        data = json.dumps(payload)
        for topic in self._normalize_topics(topics + self.publish_topics):
            if topic:
                self.client.publish(topic, data, qos=0)

    def publish_command(self, command: Dict[str, Any]) -> None:
        self.publish(self.topic_in_command, command)

    def _record_plan(self, plan_dict: Dict[str, Any]) -> None:
        self.db.insert_plan(plan_dict)
        self.publish(self.topic_out_action_plan, plan_dict)

    def _record_result(self, result_dict: Dict[str, Any]) -> None:
        self.db.insert_result(result_dict)
        self.publish(self.topic_out_action_result, result_dict)

    def update_brain_rules(self, rules: List[Dict[str, Any]], persist: bool = False) -> Dict[str, Any]:
        self.config.brain_rules = rules
        self.rule_engine = BrainRuleEngine.from_config(rules)
        updated = {"rules_count": len(self.rule_engine.rules)}
        if persist and self.config.config_path:
            try:
                with open(self.config.config_path, "r", encoding="utf-8") as handle:
                    cfg = json.load(handle)
                cfg.setdefault("brain", {})
                cfg["brain"]["rules"] = rules
                with open(self.config.config_path, "w", encoding="utf-8") as handle:
                    json.dump(cfg, handle, ensure_ascii=False, indent=2)
                updated["persisted"] = True
            except Exception as exc:
                updated["persisted"] = False
                updated["error"] = str(exc)
        return updated

    def handle_brain_request(
        self,
        text: str,
        images: Optional[List[Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        execute: bool = False,
        cache: bool = True,
    ) -> Dict[str, Any]:
        images = images or []
        context = context or {}
        context.setdefault("system_exec_allowlist", self.config.system_exec_allowlist)
        context.setdefault("script_allowlist", self.config.script_allowlist)
        decision_trace = []
        event = Event(
            event_id=new_uuid(),
            ts=utc_ts(),
            source="brain",
            type="brain_request",
            payload={
                "text": text,
                "context": context,
                "image_count": len(images),
            },
            severity=1,
        )
        event_dict = event.to_dict()
        self.db.insert_event(event_dict)
        self.publish(self.topic_out_event, event_dict)

        plan_result: BrainPlanResult
        rule_used = False
        if images and not self.config.brain_rules_allow_images:
            decision_trace.append({"step": "rules_skipped_images"})
        else:
            plan, rule_trace = self.rule_engine.match(text)
            decision_trace.append({"step": "rules_checked", **rule_trace})
            if plan:
                rule_used = True
                plan_result = BrainPlanResult(
                    plan=plan,
                    raw={"source": "rules", "rule_id": rule_trace.get("rule_id")},
                    vision=None,
                    cached=False,
                )
        if not rule_used:
            try:
                plan_result = self.brain.plan(
                    BrainRequest(text=text, images=images, context=context), use_cache=cache
                )
                decision_trace.append(
                    {
                        "step": "llm_plan",
                        "cached": bool(plan_result.cached),
                    }
                )
            except ValueError as e:
                logger.warning("Brain plan failed, returning empty plan: %s", e)
                plan_result = BrainPlanResult(
                    plan=None,
                    raw={"error": str(e)},
                    vision=None,
                    cached=False,
                )
                decision_trace.append({"step": "llm_plan", "error": str(e)})
        
        plan_dict = plan_result.plan.to_dict() if plan_result.plan else None
        if plan_dict:
            self._record_plan(plan_dict)

        results = []
        if execute and plan_result.plan:
            privacy_mode = bool(
                self.db.get_state("privacy_mode", self.config.privacy_mode_default)
            )
            results = self.tool_runner.execute_plan(
                plan_result.plan.plan_id, plan_result.plan.actions, privacy_mode
            )
            for result in results:
                self._record_result(result.to_dict())

        return {
            "event": event_dict,
            "plan": plan_dict,
            "results": [result.to_dict() for result in results],
            "vision": plan_result.vision,
            "raw": plan_result.raw,
            "decision_trace": decision_trace,
        }

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: int, rc: int) -> None:
        if rc == 0:
            logger.info("MQTT connected")
            topics = [(topic, 0) for topic in self._subscribe_topics()]
            if topics:
                client.subscribe(topics)
        else:
            logger.error("MQTT connection failed: %s", rc)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        logger.warning("MQTT disconnected: %s", rc)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError:
            logger.warning("Invalid JSON on topic %s", msg.topic)
            return

        if msg.topic in self.topic_in_event:
            event = self._normalize_event(payload, source_default="sim")
        elif msg.topic in self.topic_in_command:
            event = self._command_to_event(payload)
        else:
            logger.info("Ignoring message on %s", msg.topic)
            return

        if event is None:
            return

        self._process_event(event)

    def _normalize_event(self, raw: Dict[str, Any], source_default: str) -> Optional[Event]:
        event_type = raw.get("type") or raw.get("event_type")
        if not event_type:
            logger.warning("Event missing type: %s", raw)
            return None

        return Event(
            event_id=raw.get("event_id") or new_uuid(),
            ts=int(raw.get("ts") or utc_ts()),
            source=raw.get("source") or source_default,
            type=event_type,
            payload=raw.get("payload") or {},
            severity=int(raw.get("severity", 1)),
            correlation_id=raw.get("correlation_id"),
        )

    def _command_to_event(self, command: Dict[str, Any]) -> Optional[Event]:
        command_type = command.get("command_type")
        payload = command.get("payload") or {}
        source = command.get("source", "ui")

        ptz_action_types = {"ptz_goto_preset", "ptz_patrol", "ptz_stop", "snapshot"}
        if command_type in ptz_action_types:
            raw_event = {
                "type": "ptz_command",
                "payload": {"action_type": command_type, "params": payload},
                "severity": 0,
                "source": source,
                "correlation_id": command.get("correlation_id"),
            }
            return self._normalize_event(raw_event, source_default=source)

        if command_type == "start_patrol":
            raw_event = {
                "type": "ptz_command",
                "payload": {"action_type": "ptz_patrol", "params": payload},
                "severity": 0,
                "source": source,
                "correlation_id": command.get("correlation_id"),
            }
            return self._normalize_event(raw_event, source_default=source)

        if command_type == "stop_patrol":
            raw_event = {
                "type": "ptz_command",
                "payload": {"action_type": "ptz_stop", "params": payload},
                "severity": 0,
                "source": source,
                "correlation_id": command.get("correlation_id"),
            }
            return self._normalize_event(raw_event, source_default=source)

        mapping: Dict[str, Dict[str, Any]] = {
            "simulate_entry": {
                "type": "zone_person_detected",
                "payload": {
                    "zone": self.config.arrival_zone,
                    "camera": self.config.entry_camera_default,
                },
                "severity": 1,
            },
            "find_keys": {
                "type": "find_object_request",
                "payload": {
                    "object": "keys",
                    "cameras": self.config.find_keys_cameras,
                },
                "severity": 1,
            },
            "simulate_fall": {
                "type": "fall_suspect",
                "payload": {
                    "zone": self.config.fall_zone_default,
                    "camera": self.config.fall_camera_default,
                },
                "severity": 2,
            },
            "start_patrol": {
                "type": "patrol_request",
                "payload": {"mode": "start", "presets": self.config.patrol_presets},
                "severity": 1,
            },
            "stop_patrol": {
                "type": "patrol_request",
                "payload": {"mode": "stop"},
                "severity": 1,
            },
            "privacy_toggle": {
                "type": "privacy_toggle",
                "payload": {},
                "severity": 0,
            },
            "simulate_intrusion": {
                "type": "intrusion",
                "payload": {
                    "person": self.config.intrusion_unknown_person_value,
                    "mode": self.config.intrusion_mode_required,
                    "camera": self.config.intrusion_camera_default,
                },
                "severity": 3,
            },
        }

        base = mapping.get(command_type)
        if not base:
            logger.warning("Unknown command_type: %s", command_type)
            return None

        merged_payload = {**base.get("payload", {}), **payload}
        raw_event = {
            "type": base["type"],
            "payload": merged_payload,
            "severity": base.get("severity", 1),
            "source": source,
            "correlation_id": command.get("correlation_id"),
        }
        return self._normalize_event(raw_event, source_default=source)

    def _process_event(self, event: Event) -> None:
        event_dict = event.to_dict()
        self.db.insert_event(event_dict)
        self.publish(self.topic_out_event, event_dict)

        if event.type == "ptz_command":
            plan = self._plan_from_ptz_command(event)
            if plan:
                plan_dict = plan.to_dict()
                self.db.insert_plan(plan_dict)
                self.publish(self.topic_out_action_plan, plan_dict)

                privacy_mode = bool(
                    self.db.get_state("privacy_mode", self.config.privacy_mode_default)
                )
                results = self.tool_runner.execute_plan(plan.plan_id, plan.actions, privacy_mode)
                for result in results:
                    result_dict = result.to_dict()
                    self.db.insert_result(result_dict)
                    self.publish(self.topic_out_action_result, result_dict)
            return

        if event.type == "privacy_toggle":
            self._handle_privacy_toggle(event)

        plans = self.policy.evaluate(event)
        if not plans:
            return

        privacy_mode = bool(self.db.get_state("privacy_mode", self.config.privacy_mode_default))
        for plan in plans:
            filtered_actions = self._filter_actions(plan.actions, privacy_mode)
            if not filtered_actions:
                continue
            plan.actions = filtered_actions
            plan_dict = plan.to_dict()
            self.db.insert_plan(plan_dict)
            self.publish(self.topic_out_action_plan, plan_dict)

            results = self.tool_runner.execute_plan(plan.plan_id, plan.actions, privacy_mode)
            for result in results:
                result_dict = result.to_dict()
                self.db.insert_result(result_dict)
                self.publish(self.topic_out_action_result, result_dict)

    def _plan_from_ptz_command(self, event: Event) -> Optional[ActionPlan]:
        payload = event.payload or {}
        action_type = payload.get("action_type")
        params = payload.get("params") or {}
        if not action_type:
            return None

        if action_type == "ptz_goto_preset":
            params = {"name": params.get("name") or self.config.ptz_entry_preset}
        elif action_type == "ptz_patrol":
            params = {
                "presets": params.get("presets") or self.config.patrol_presets,
                "dwell_s": params.get("dwell_s") or self.config.ptz_patrol_dwell_sec,
            }
        elif action_type == "ptz_stop":
            params = {}

        reason = f"command={action_type}"
        if params:
            reason = f"{reason}, params={params}"

        return ActionPlan(
            plan_id=new_uuid(),
            triggered_by_event_id=event.event_id,
            actions=[{"action_type": action_type, "params": params}],
            policy=f"CMD_{action_type}",
            reason=reason,
            created_ts=utc_ts(),
        )

    def _handle_privacy_toggle(self, event: Event) -> None:
        desired = event.payload.get("enabled")
        if desired is None:
            current = bool(self.db.get_state("privacy_mode", False))
            desired = not current
        self.db.set_state("privacy_mode", bool(desired))

    def _filter_actions(self, actions: list[Dict[str, Any]], privacy_mode: bool) -> list[Dict[str, Any]]:
        if not privacy_mode:
            return actions
        filtered = []
        for action in actions:
            action_type = action.get("action_type", "")
            if action_type == "store_event":
                kind = (action.get("params") or {}).get("kind")
                if kind in self.config.privacy_block_store_kinds:
                    continue
                filtered.append(action)
                continue
            if action_type in self.config.camera_action_types:
                continue
            filtered.append(action)
        return filtered

    def _normalize_topics(self, topics: list[str]) -> list[str]:
        seen = set()
        result = []
        for topic in topics:
            if not topic or topic in seen:
                continue
            seen.add(topic)
            result.append(topic)
        return result

    def _subscribe_topics(self) -> list[str]:
        return self._normalize_topics(
            self.topic_in_event + self.topic_in_command + self.sub_topics
        )

    def _on_dashan_status(self, state) -> None:
        event = Event(
            event_id=new_uuid(),
            ts=utc_ts(),
            source="dashan",
            type="dashan_status",
            payload={
                "state": state.state,
                "expression": state.expression_name,
                "emotion": state.emotion_type,
                "servo": {
                    "horizontal": state.servo_horizontal,
                    "vertical": state.servo_vertical
                },
                "battery": state.battery,
                "proximity": state.proximity,
                "distance": state.distance,
                "light": state.light
            },
            severity=0
        )
        self._process_event(event)

    def _on_dashan_log(self, log_entry) -> None:
        event = Event(
            event_id=new_uuid(),
            ts=log_entry.timestamp,
            source="dashan",
            type=f"dashan_{log_entry.type}",
            payload={
                "level": log_entry.level,
                "message": log_entry.message,
                "context": log_entry.context
            },
            severity=0 if log_entry.level == "INFO" else 1 if log_entry.level == "WARNING" else 2
        )
        self._process_event(event)

    def _on_dashan_image(self, image_data: str) -> None:
        event = Event(
            event_id=new_uuid(),
            ts=utc_ts(),
            source="dashan",
            type="dashan_image",
            payload={
                "image": image_data[:100],
                "face_detected": True
            },
            severity=0
        )
        self._process_event(event)
