from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _load_json(path: str) -> Dict[str, Any]:
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        logger.warning("Config file not found: %s", path)
    except json.JSONDecodeError as exc:
        logger.error("Invalid config JSON %s: %s", path, exc)
    return {}


def _get_nested(cfg: Dict[str, Any], path: str) -> Any:
    current: Any = cfg
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _parse_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return None


def _parse_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_list(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",")]
        return [item for item in items if item]
    return [str(value)]


def _parse_list_of_dicts(value: Any) -> Optional[List[Dict[str, Any]]]:
    if value is None:
        return None
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
            if isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            return None
    return None


def _parse_dict(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _env_or_cfg(
    env_key: str,
    cfg: Dict[str, Any],
    cfg_path: str,
    parser,
    default: Any,
) -> Any:
    if env_key in os.environ:
        parsed = parser(os.environ.get(env_key))
        return default if parsed is None else parsed
    cfg_value = _get_nested(cfg, cfg_path)
    parsed = parser(cfg_value)
    return default if parsed is None else parsed


def _parse_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _resolve_db_path(db_path: Optional[str], config_path: str) -> str:
    """解析数据库路径，支持多种方式指定"""
    if db_path and os.path.isabs(db_path):
        # 绝对路径直接返回
        return db_path
    
    # 尝试相对于config_path的路径
    if db_path and config_path:
        config_dir = os.path.dirname(os.path.abspath(config_path))
        candidate = os.path.join(config_dir, db_path)
        return candidate
    
    # 尝试相对于当前工作目录
    if db_path:
        candidate = os.path.join(os.getcwd(), db_path)
        return candidate
    
    # 默认路径，考虑Docker和本地环境
    if os.path.exists("/app/butler"):
        # Docker环境
        return "/app/butler/data/butler.db"
    else:
        # 本地环境
        return os.path.join(os.getcwd(), "butler/data/butler.db")


@dataclass
class ButlerConfig:
    config_path: str = ""
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_keepalive_sec: int = 60
    mqtt_reconnect_min_sec: int = 1
    mqtt_reconnect_max_sec: int = 10
    db_path: str = ""  # 将在load_config中初始化
    topic_in_event: List[str] = field(default_factory=lambda: ["butler/in/event"])
    topic_in_command: List[str] = field(default_factory=lambda: ["butler/in/command"])
    topic_out_event: List[str] = field(default_factory=lambda: ["butler/out/event"])
    topic_out_action_plan: List[str] = field(default_factory=lambda: ["butler/out/action_plan"])
    topic_out_action_result: List[str] = field(default_factory=lambda: ["butler/out/action_result"])
    sub_topics: List[str] = field(default_factory=list)
    publish_topics: List[str] = field(default_factory=list)
    ui_poll_interval_ms: int = 5000
    mode_default: str = "home"
    arrival_zone: str = "entry"
    arrival_notify_title: str = "Welcome home"
    arrival_notify_message: str = "Entry zone activity detected."
    r1_cooldown_sec: int = 300
    patrol_presets: List[str] = field(
        default_factory=lambda: ["entry", "living_room", "hallway"]
    )
    ptz_entry_preset: str = "entry"
    ptz_patrol_dwell_sec: int = 5
    find_keys_cameras: List[str] = field(
        default_factory=lambda: ["entry_cam", "kitchen_cam", "living_cam"]
    )
    intrusion_mode_required: str = "away"
    intrusion_unknown_person_value: str = "unknown"
    intrusion_camera_default: str = "backyard_cam"
    intrusion_record_duration_sec: int = 15
    intrusion_window_sec: int = 120
    intrusion_count_threshold: int = 3
    entry_camera_default: str = "entry_cam"
    fall_zone_default: str = "living_room"
    fall_camera_default: str = "living_cam"
    privacy_mode_default: bool = False
    camera_action_types: List[str] = field(
        default_factory=lambda: [
            "ptz_goto_preset",
            "ptz_patrol",
            "snapshot",
            "store_event",
            "vision_detect",
            "face_enroll",
            "face_verify",
        ]
    )
    privacy_block_store_kinds: List[str] = field(default_factory=lambda: ["record"])
    frigate_topic: str = ""
    frigate_sub_topic: str = "frigate/#"
    frigate_mode: str = "OBSERVE"
    frigate_debug_raw: bool = False
    frigate_raw_log_path: str = "logs/frigate_raw.log"
    frigate_event_type: str = "frigate_event"
    frigate_payload_map: Dict[str, Any] = field(default_factory=dict)
    frigate_passthrough_raw: bool = True
    frigate_severity_default: int = 1
    frigate_severity_path: str = ""
    llm_api_key: str = ""
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_model_text: str = "glm-4.7"
    llm_model_vision: str = "glm-4.6v"
    llm_timeout_sec: int = 60
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1024
    llm_top_p: float = 0.8
    brain_cache_ttl_sec: int = 30
    brain_cache_size: int = 128
    brain_max_actions: int = 6
    brain_retry_attempts: int = 1
    brain_rules: List[Dict[str, Any]] = field(default_factory=list)
    brain_rules_allow_images: bool = False
    system_exec_allowlist: List[str] = field(default_factory=list)
    system_exec_timeout_sec: int = 20
    script_dir: str = "butler/scripts"
    script_allowlist: List[str] = field(default_factory=list)
    openclaw_cli_path: str = "openclaw"
    openclaw_env: Dict[str, Any] = field(default_factory=dict)
    scheduler_enabled: bool = True
    scheduler_interval_sec: int = 5
    email_imap_host: str = ""
    email_imap_port: int = 993
    email_imap_ssl: bool = True
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_smtp_ssl: bool = False
    email_smtp_starttls: bool = True
    email_username: str = ""
    email_password: str = ""
    email_from: str = ""
    image_api_url: str = ""
    image_api_key: str = ""
    image_model: str = ""
    image_timeout_sec: int = 60
    vision_enabled: bool = True
    vision_device: str = "cpu"
    vision_face_model_path: str = "yolov11m-face.pt"
    vision_object_model_path: str = "yolov8n.pt"
    vision_face_backend: str = "auto"
    vision_face_match_threshold: float = 0.35
    vision_face_min_confidence: float = 0.5
    vision_object_min_confidence: float = 0.25
    vision_max_faces: int = 5
    asr_api_url: str = ""
    asr_api_key: str = ""
    asr_model: str = "whisper-1"
    asr_timeout_sec: int = 60
    asr_provider: str = "auto"
    asr_model_local: str = "small"
    asr_language: str = ""
    asr_device: str = "cpu"
    asr_compute_type: str = "int8"
    asr_download_dir: str = ""
    asr_beam_size: int = 5
    asr_vosk_model_path: str = ""
    wake_words: List[str] = field(default_factory=lambda: ["hello", "butler"])
    search_api_url: str = ""
    search_api_key: str = ""
    search_query_param: str = "q"
    search_key_param: str = "api_key"
    search_provider: str = ""
    search_timeout_sec: int = 20
    gateway_base_url: str = ""
    gateway_token: str = ""
    gateway_token_header: str = "Authorization"
    gateway_timeout_sec: int = 20
    gateway_allowlist: List[str] = field(default_factory=list)
    ha_url: str = "http://localhost:8123"
    ha_token: Optional[str] = None
    ha_mock: bool = True
    ha_timeout_sec: int = 10
    devices_backend_default: str = "auto"
    dialogue_enabled: bool = True
    dialogue_max_history: int = 20
    dialogue_context_ttl_sec: int = 300
    goal_enabled: bool = True
    goal_suggestions_enabled: bool = True
    scene_enabled: bool = True
    automation_enabled: bool = True
    habit_learning_enabled: bool = True
    anomaly_detection_enabled: bool = True
    energy_optimization_enabled: bool = True
    predictive_service_enabled: bool = True
    ir_enabled: bool = True
    ir_device: str = "default"
    ir_learning_timeout_sec: int = 30
    dashan_enabled: bool = True
    dashan_mqtt_host: str = "localhost"
    dashan_mqtt_port: int = 1883
    dashan_mqtt_username: Optional[str] = None
    dashan_mqtt_password: Optional[str] = None


def load_config(path: Optional[str] = None) -> ButlerConfig:
    config_path = path or os.getenv("BUTLER_CONFIG", "")
    cfg = _load_json(config_path)

    mqtt_host = _first_non_none(
        _parse_str(os.getenv("MQTT_HOST")),
        _parse_str(os.getenv("MQTT_BROKER_HOST")),
        _parse_str(_get_nested(cfg, "mqtt.host")),
        "localhost",
    )
    mqtt_port = _first_non_none(
        _parse_int(os.getenv("MQTT_PORT")),
        _parse_int(os.getenv("MQTT_BROKER_PORT")),
        _parse_int(_get_nested(cfg, "mqtt.port")),
        1883,
    )
    cooldown_minutes = _env_or_cfg(
        "COOLDOWN_MINUTES",
        cfg,
        "policy.arrival.cooldown_minutes",
        _parse_int,
        None,
    )
    if cooldown_minutes is not None:
        cooldown_sec = max(cooldown_minutes, 0) * 60
    else:
        cooldown_sec = _env_or_cfg(
            "R1_COOLDOWN_SEC",
            cfg,
            "policy.arrival.cooldown_sec",
            _parse_int,
            300,
        )
    mode_default = _first_non_none(
        _parse_str(os.getenv("MODE_DEFAULT")),
        _parse_str(_get_nested(cfg, "mode.default")),
        "home",
    )
    privacy_default = _first_non_none(
        _parse_bool(os.getenv("PRIVACY_DEFAULT")),
        _parse_bool(os.getenv("PRIVACY_MODE_DEFAULT")),
        _parse_bool(_get_nested(cfg, "privacy.mode_default")),
        False,
    )
    intrusion_window_minutes = _env_or_cfg(
        "INTRUSION_WINDOW_MINUTES",
        cfg,
        "policy.intrusion.window_minutes",
        _parse_int,
        None,
    )
    if intrusion_window_minutes is not None:
        intrusion_window_sec = max(intrusion_window_minutes, 0) * 60
    else:
        intrusion_window_sec = _env_or_cfg(
            "INTRUSION_WINDOW_SEC",
            cfg,
            "policy.intrusion.window_sec",
            _parse_int,
            120,
        )
    intrusion_count_threshold = _env_or_cfg(
        "INTRUSION_COUNT_THRESHOLD",
        cfg,
        "policy.intrusion.count_threshold",
        _parse_int,
        3,
    )
    frigate_sub_topic = _first_non_none(
        _parse_str(os.getenv("FRIGATE_SUB_TOPIC")),
        _parse_str(os.getenv("FRIGATE_TOPIC")),
        _parse_str(_get_nested(cfg, "frigate.sub_topic")),
        _parse_str(_get_nested(cfg, "frigate.topic")),
        "frigate/#",
    )
    frigate_mode = _first_non_none(
        _parse_str(os.getenv("FRIGATE_MODE")),
        _parse_str(_get_nested(cfg, "frigate.mode")),
        "OBSERVE",
    )
    frigate_mode = frigate_mode.upper()

    return ButlerConfig(
        config_path=config_path,
        mqtt_host=mqtt_host,
        mqtt_port=mqtt_port,
        mqtt_keepalive_sec=_env_or_cfg(
            "MQTT_KEEPALIVE_SEC", cfg, "mqtt.keepalive_sec", _parse_int, 60
        ),
        mqtt_reconnect_min_sec=_env_or_cfg(
            "MQTT_RECONNECT_MIN_SEC", cfg, "mqtt.reconnect_min_sec", _parse_int, 1
        ),
        mqtt_reconnect_max_sec=_env_or_cfg(
            "MQTT_RECONNECT_MAX_SEC", cfg, "mqtt.reconnect_max_sec", _parse_int, 10
        ),
        db_path=_resolve_db_path(
            _env_or_cfg("DB_PATH", cfg, "db.path", _parse_str, None),
            config_path
        ),
        topic_in_event=_env_or_cfg(
            "MQTT_TOPIC_IN_EVENT",
            cfg,
            "topics.in_event",
            _parse_list,
            ["butler/in/event"],
        ),
        topic_in_command=_env_or_cfg(
            "MQTT_TOPIC_IN_COMMAND",
            cfg,
            "topics.in_command",
            _parse_list,
            ["butler/in/command"],
        ),
        topic_out_event=_env_or_cfg(
            "MQTT_TOPIC_OUT_EVENT",
            cfg,
            "topics.out_event",
            _parse_list,
            ["butler/out/event"],
        ),
        topic_out_action_plan=_env_or_cfg(
            "MQTT_TOPIC_OUT_ACTION_PLAN",
            cfg,
            "topics.out_action_plan",
            _parse_list,
            ["butler/out/action_plan"],
        ),
        topic_out_action_result=_env_or_cfg(
            "MQTT_TOPIC_OUT_ACTION_RESULT",
            cfg,
            "topics.out_action_result",
            _parse_list,
            ["butler/out/action_result"],
        ),
        sub_topics=_env_or_cfg(
            "SUB_TOPICS",
            cfg,
            "topics.sub_topics",
            _parse_list,
            [],
        ),
        publish_topics=_env_or_cfg(
            "PUBLISH_TOPICS",
            cfg,
            "topics.publish_topics",
            _parse_list,
            [],
        ),
        ui_poll_interval_ms=_env_or_cfg(
            "UI_POLL_INTERVAL_MS", cfg, "ui.poll_interval_ms", _parse_int, 5000
        ),
        mode_default=mode_default,
        arrival_zone=_env_or_cfg(
            "ARRIVAL_ZONE", cfg, "policy.arrival.zone", _parse_str, "entry"
        ),
        arrival_notify_title=_env_or_cfg(
            "ARRIVAL_NOTIFY_TITLE",
            cfg,
            "policy.arrival.notify_title",
            _parse_str,
            "Welcome home",
        ),
        arrival_notify_message=_env_or_cfg(
            "ARRIVAL_NOTIFY_MESSAGE",
            cfg,
            "policy.arrival.notify_message",
            _parse_str,
            "Entry zone activity detected.",
        ),
        r1_cooldown_sec=cooldown_sec,
        patrol_presets=_env_or_cfg(
            "PATROL_PRESETS",
            cfg,
            "policy.patrol_presets",
            _parse_list,
            ["entry", "living_room", "hallway"],
        ),
        ptz_entry_preset=_env_or_cfg(
            "PTZ_ENTRY_PRESET",
            cfg,
            "ptz.entry_preset",
            _parse_str,
            "entry",
        ),
        ptz_patrol_dwell_sec=_env_or_cfg(
            "PTZ_PATROL_DWELL_SEC",
            cfg,
            "ptz.patrol_dwell_sec",
            _parse_int,
            5,
        ),
        find_keys_cameras=_env_or_cfg(
            "FIND_KEYS_CAMERAS",
            cfg,
            "policy.find_keys_cameras",
            _parse_list,
            ["entry_cam", "kitchen_cam", "living_cam"],
        ),
        intrusion_mode_required=_env_or_cfg(
            "INTRUSION_MODE_REQUIRED",
            cfg,
            "policy.intrusion.mode_required",
            _parse_str,
            "away",
        ),
        intrusion_unknown_person_value=_env_or_cfg(
            "INTRUSION_UNKNOWN_PERSON_VALUE",
            cfg,
            "policy.intrusion.unknown_person_value",
            _parse_str,
            "unknown",
        ),
        intrusion_camera_default=_env_or_cfg(
            "INTRUSION_CAMERA_DEFAULT",
            cfg,
            "policy.intrusion.camera_default",
            _parse_str,
            "backyard_cam",
        ),
        intrusion_record_duration_sec=_env_or_cfg(
            "INTRUSION_RECORD_DURATION_SEC",
            cfg,
            "policy.intrusion.record_duration_sec",
            _parse_int,
            15,
        ),
        intrusion_window_sec=intrusion_window_sec,
        intrusion_count_threshold=intrusion_count_threshold,
        entry_camera_default=_env_or_cfg(
            "ENTRY_CAMERA_DEFAULT", cfg, "sim.entry_camera", _parse_str, "entry_cam"
        ),
        fall_zone_default=_env_or_cfg(
            "FALL_ZONE_DEFAULT", cfg, "sim.fall_zone", _parse_str, "living_room"
        ),
        fall_camera_default=_env_or_cfg(
            "FALL_CAMERA_DEFAULT", cfg, "sim.fall_camera", _parse_str, "living_cam"
        ),
        privacy_mode_default=privacy_default,
        camera_action_types=_env_or_cfg(
            "PRIVACY_CAMERA_ACTION_TYPES",
            cfg,
            "privacy.camera_action_types",
            _parse_list,
            [
                "ptz_goto_preset",
                "ptz_patrol",
                "snapshot",
                "store_event",
                "vision_detect",
                "face_enroll",
                "face_verify",
            ],
        ),
        privacy_block_store_kinds=_env_or_cfg(
            "PRIVACY_BLOCK_STORE_KINDS",
            cfg,
            "privacy.block_store_kinds",
            _parse_list,
            ["record"],
        ),
        frigate_topic=_env_or_cfg("FRIGATE_TOPIC", cfg, "frigate.topic", _parse_str, ""),
        frigate_sub_topic=frigate_sub_topic,
        frigate_mode=frigate_mode,
        frigate_debug_raw=_env_or_cfg(
            "FRIGATE_DEBUG_RAW", cfg, "frigate.debug_raw", _parse_bool, False
        ),
        frigate_raw_log_path=_env_or_cfg(
            "FRIGATE_RAW_LOG_PATH",
            cfg,
            "frigate.raw_log_path",
            _parse_str,
            "logs/frigate_raw.log",
        ),
        frigate_event_type=_env_or_cfg(
            "FRIGATE_EVENT_TYPE",
            cfg,
            "frigate.event_type",
            _parse_str,
            "frigate_event",
        ),
        frigate_payload_map=_env_or_cfg(
            "FRIGATE_PAYLOAD_MAP",
            cfg,
            "frigate.payload_map",
            _parse_dict,
            {},
        ),
        frigate_passthrough_raw=_env_or_cfg(
            "FRIGATE_PASSTHROUGH_RAW",
            cfg,
            "frigate.passthrough_raw",
            _parse_bool,
            True,
        ),
        frigate_severity_default=_env_or_cfg(
            "FRIGATE_SEVERITY_DEFAULT",
            cfg,
            "frigate.severity_default",
            _parse_int,
            1,
        ),
        frigate_severity_path=_env_or_cfg(
            "FRIGATE_SEVERITY_PATH",
            cfg,
            "frigate.severity_path",
            _parse_str,
            "",
        ),
        llm_api_key=_env_or_cfg("GLM_API_KEY", cfg, "llm.api_key", _parse_str, ""),
        llm_base_url=_env_or_cfg(
            "GLM_BASE_URL", cfg, "llm.base_url", _parse_str, "https://open.bigmodel.cn/api/paas/v4"
        ),
        llm_model_text=_env_or_cfg(
            "GLM_MODEL_TEXT", cfg, "llm.model_text", _parse_str, "glm-4.7"
        ),
        llm_model_vision=_env_or_cfg(
            "GLM_MODEL_VISION", cfg, "llm.model_vision", _parse_str, "glm-4.6v"
        ),
        llm_timeout_sec=_env_or_cfg(
            "GLM_TIMEOUT_SEC", cfg, "llm.timeout_sec", _parse_int, 60
        ),
        llm_temperature=_env_or_cfg(
            "GLM_TEMPERATURE", cfg, "llm.temperature", _parse_float, 0.2
        ),
        llm_max_tokens=_env_or_cfg(
            "GLM_MAX_TOKENS", cfg, "llm.max_tokens", _parse_int, 1024
        ),
        llm_top_p=_env_or_cfg(
            "GLM_TOP_P", cfg, "llm.top_p", _parse_float, 0.8
        ),
        brain_cache_ttl_sec=_env_or_cfg(
            "BRAIN_CACHE_TTL_SEC", cfg, "brain.cache_ttl_sec", _parse_int, 30
        ),
        brain_cache_size=_env_or_cfg(
            "BRAIN_CACHE_SIZE", cfg, "brain.cache_size", _parse_int, 128
        ),
        brain_max_actions=_env_or_cfg(
            "BRAIN_MAX_ACTIONS", cfg, "brain.max_actions", _parse_int, 6
        ),
        brain_retry_attempts=_env_or_cfg(
            "BRAIN_RETRY_ATTEMPTS", cfg, "brain.retry_attempts", _parse_int, 1
        ),
        brain_rules=_env_or_cfg(
            "BRAIN_RULES", cfg, "brain.rules", _parse_list_of_dicts, []
        ),
        brain_rules_allow_images=_env_or_cfg(
            "BRAIN_RULES_ALLOW_IMAGES", cfg, "brain.rules_allow_images", _parse_bool, False
        ),
        system_exec_allowlist=_env_or_cfg(
            "SYSTEM_EXEC_ALLOWLIST", cfg, "system_exec.allowlist", _parse_list, []
        ),
        system_exec_timeout_sec=_env_or_cfg(
            "SYSTEM_EXEC_TIMEOUT_SEC", cfg, "system_exec.timeout_sec", _parse_int, 20
        ),
        script_dir=_env_or_cfg(
            "SCRIPT_DIR", cfg, "scripts.dir", _parse_str, "butler/scripts"
        ),
        script_allowlist=_env_or_cfg(
            "SCRIPT_ALLOWLIST", cfg, "scripts.allowlist", _parse_list, []
        ),
        openclaw_cli_path=_env_or_cfg(
            "OPENCLAW_CLI_PATH", cfg, "openclaw.cli_path", _parse_str, "openclaw"
        ),
        openclaw_env=_env_or_cfg(
            "OPENCLAW_ENV", cfg, "openclaw.env", _parse_dict, {}
        ),
        scheduler_enabled=_env_or_cfg(
            "SCHEDULER_ENABLED", cfg, "scheduler.enabled", _parse_bool, True
        ),
        scheduler_interval_sec=_env_or_cfg(
            "SCHEDULER_INTERVAL_SEC", cfg, "scheduler.interval_sec", _parse_int, 5
        ),
        email_imap_host=_env_or_cfg(
            "EMAIL_IMAP_HOST", cfg, "email.imap.host", _parse_str, ""
        ),
        email_imap_port=_env_or_cfg(
            "EMAIL_IMAP_PORT", cfg, "email.imap.port", _parse_int, 993
        ),
        email_imap_ssl=_env_or_cfg(
            "EMAIL_IMAP_SSL", cfg, "email.imap.ssl", _parse_bool, True
        ),
        email_smtp_host=_env_or_cfg(
            "EMAIL_SMTP_HOST", cfg, "email.smtp.host", _parse_str, ""
        ),
        email_smtp_port=_env_or_cfg(
            "EMAIL_SMTP_PORT", cfg, "email.smtp.port", _parse_int, 587
        ),
        email_smtp_ssl=_env_or_cfg(
            "EMAIL_SMTP_SSL", cfg, "email.smtp.ssl", _parse_bool, False
        ),
        email_smtp_starttls=_env_or_cfg(
            "EMAIL_SMTP_STARTTLS", cfg, "email.smtp.starttls", _parse_bool, True
        ),
        email_username=_env_or_cfg(
            "EMAIL_USERNAME", cfg, "email.username", _parse_str, ""
        ),
        email_password=_env_or_cfg(
            "EMAIL_PASSWORD", cfg, "email.password", _parse_str, ""
        ),
        email_from=_env_or_cfg(
            "EMAIL_FROM", cfg, "email.from", _parse_str, ""
        ),
        image_api_url=_env_or_cfg(
            "IMAGE_API_URL", cfg, "image.api_url", _parse_str, ""
        ),
        image_api_key=_env_or_cfg(
            "IMAGE_API_KEY", cfg, "image.api_key", _parse_str, ""
        ),
        image_model=_env_or_cfg(
            "IMAGE_MODEL", cfg, "image.model", _parse_str, ""
        ),
        image_timeout_sec=_env_or_cfg(
            "IMAGE_TIMEOUT_SEC", cfg, "image.timeout_sec", _parse_int, 60
        ),
        vision_enabled=_env_or_cfg(
            "VISION_ENABLED", cfg, "vision.enabled", _parse_bool, True
        ),
        vision_device=_env_or_cfg(
            "VISION_DEVICE", cfg, "vision.device", _parse_str, "cpu"
        ),
        vision_face_model_path=_env_or_cfg(
            "VISION_FACE_MODEL_PATH",
            cfg,
            "vision.face_model_path",
            _parse_str,
            "yolov11m-face.pt",
        ),
        vision_object_model_path=_env_or_cfg(
            "VISION_OBJECT_MODEL_PATH",
            cfg,
            "vision.object_model_path",
            _parse_str,
            "yolov8n.pt",
        ),
        vision_face_backend=_env_or_cfg(
            "VISION_FACE_BACKEND", cfg, "vision.face_backend", _parse_str, "auto"
        ),
        vision_face_match_threshold=_env_or_cfg(
            "VISION_FACE_MATCH_THRESHOLD",
            cfg,
            "vision.face_match_threshold",
            _parse_float,
            0.35,
        ),
        vision_face_min_confidence=_env_or_cfg(
            "VISION_FACE_MIN_CONFIDENCE",
            cfg,
            "vision.face_min_confidence",
            _parse_float,
            0.5,
        ),
        vision_object_min_confidence=_env_or_cfg(
            "VISION_OBJECT_MIN_CONFIDENCE",
            cfg,
            "vision.object_min_confidence",
            _parse_float,
            0.25,
        ),
        vision_max_faces=_env_or_cfg(
            "VISION_MAX_FACES", cfg, "vision.max_faces", _parse_int, 5
        ),
        asr_api_url=_env_or_cfg(
            "ASR_API_URL", cfg, "asr.api_url", _parse_str, ""
        ),
        asr_api_key=_env_or_cfg(
            "ASR_API_KEY", cfg, "asr.api_key", _parse_str, ""
        ),
        asr_model=_env_or_cfg(
            "ASR_MODEL", cfg, "asr.model", _parse_str, "whisper-1"
        ),
        asr_timeout_sec=_env_or_cfg(
            "ASR_TIMEOUT_SEC", cfg, "asr.timeout_sec", _parse_int, 60
        ),
        asr_provider=_env_or_cfg(
            "ASR_PROVIDER", cfg, "asr.provider", _parse_str, "auto"
        ),
        asr_model_local=_env_or_cfg(
            "ASR_MODEL_LOCAL", cfg, "asr.model_local", _parse_str, "small"
        ),
        asr_language=_env_or_cfg(
            "ASR_LANGUAGE", cfg, "asr.language", _parse_str, ""
        ),
        asr_device=_env_or_cfg(
            "ASR_DEVICE", cfg, "asr.device", _parse_str, "cpu"
        ),
        asr_compute_type=_env_or_cfg(
            "ASR_COMPUTE_TYPE", cfg, "asr.compute_type", _parse_str, "int8"
        ),
        asr_download_dir=_env_or_cfg(
            "ASR_DOWNLOAD_DIR", cfg, "asr.download_dir", _parse_str, ""
        ),
        asr_beam_size=_env_or_cfg(
            "ASR_BEAM_SIZE", cfg, "asr.beam_size", _parse_int, 5
        ),
        asr_vosk_model_path=_env_or_cfg(
            "ASR_VOSK_MODEL_PATH", cfg, "asr.vosk_model_path", _parse_str, ""
        ),
        wake_words=_env_or_cfg(
            "WAKE_WORDS", cfg, "voice.wake_words", _parse_list, ["hello", "butler"]
        ),
        search_api_url=_env_or_cfg(
            "SEARCH_API_URL", cfg, "search.api_url", _parse_str, ""
        ),
        search_api_key=_env_or_cfg(
            "SEARCH_API_KEY", cfg, "search.api_key", _parse_str, ""
        ),
        search_query_param=_env_or_cfg(
            "SEARCH_QUERY_PARAM", cfg, "search.query_param", _parse_str, "q"
        ),
        search_key_param=_env_or_cfg(
            "SEARCH_KEY_PARAM", cfg, "search.key_param", _parse_str, "api_key"
        ),
        search_provider=_env_or_cfg(
            "SEARCH_PROVIDER", cfg, "search.provider", _parse_str, ""
        ),
        search_timeout_sec=_env_or_cfg(
            "SEARCH_TIMEOUT_SEC", cfg, "search.timeout_sec", _parse_int, 20
        ),
        gateway_base_url=_env_or_cfg(
            "GATEWAY_BASE_URL", cfg, "gateway.base_url", _parse_str, ""
        ),
        gateway_token=_env_or_cfg(
            "GATEWAY_TOKEN", cfg, "gateway.token", _parse_str, ""
        ),
        gateway_token_header=_env_or_cfg(
            "GATEWAY_TOKEN_HEADER", cfg, "gateway.token_header", _parse_str, "Authorization"
        ),
        gateway_timeout_sec=_env_or_cfg(
            "GATEWAY_TIMEOUT_SEC", cfg, "gateway.timeout_sec", _parse_int, 20
        ),
        gateway_allowlist=_env_or_cfg(
            "GATEWAY_ALLOWLIST", cfg, "gateway.allowlist", _parse_list, []
        ),
        ha_url=_env_or_cfg(
            "HA_URL", cfg, "ha.url", _parse_str, "http://localhost:8123"
        ),
        ha_token=_env_or_cfg(
            "HA_TOKEN", cfg, "ha.token", _parse_str, None
        ),
        ha_mock=_env_or_cfg(
            "HA_MOCK", cfg, "ha.mock", _parse_bool, True
        ),
        ha_timeout_sec=_env_or_cfg(
            "HA_TIMEOUT_SEC", cfg, "ha.timeout_sec", _parse_int, 10
        ),
        devices_backend_default=_env_or_cfg(
            "DEVICES_BACKEND_DEFAULT", cfg, "devices.backend_default", _parse_str, "auto"
        ),
        dialogue_enabled=_env_or_cfg(
            "DIALOGUE_ENABLED", cfg, "dialogue.enabled", _parse_bool, True
        ),
        dialogue_max_history=_env_or_cfg(
            "DIALOGUE_MAX_HISTORY", cfg, "dialogue.max_history", _parse_int, 20
        ),
        dialogue_context_ttl_sec=_env_or_cfg(
            "DIALOGUE_CONTEXT_TTL_SEC", cfg, "dialogue.context_ttl_sec", _parse_int, 300
        ),
        goal_enabled=_env_or_cfg(
            "GOAL_ENABLED", cfg, "goal.enabled", _parse_bool, True
        ),
        goal_suggestions_enabled=_env_or_cfg(
            "GOAL_SUGGESTIONS_ENABLED", cfg, "goal.suggestions_enabled", _parse_bool, True
        ),
        scene_enabled=_env_or_cfg(
            "SCENE_ENABLED", cfg, "scene.enabled", _parse_bool, True
        ),
        automation_enabled=_env_or_cfg(
            "AUTOMATION_ENABLED", cfg, "automation.enabled", _parse_bool, True
        ),
        habit_learning_enabled=_env_or_cfg(
            "HABIT_LEARNING_ENABLED", cfg, "automation.habit_learning_enabled", _parse_bool, True
        ),
        anomaly_detection_enabled=_env_or_cfg(
            "ANOMALY_DETECTION_ENABLED", cfg, "proactive.anomaly_detection_enabled", _parse_bool, True
        ),
        energy_optimization_enabled=_env_or_cfg(
            "ENERGY_OPTIMIZATION_ENABLED", cfg, "proactive.energy_optimization_enabled", _parse_bool, True
        ),
        predictive_service_enabled=_env_or_cfg(
            "PREDICTIVE_SERVICE_ENABLED", cfg, "proactive.predictive_service_enabled", _parse_bool, True
        ),
        ir_enabled=_env_or_cfg(
            "IR_ENABLED", cfg, "ir.enabled", _parse_bool, True
        ),
        ir_device=_env_or_cfg(
            "IR_DEVICE", cfg, "ir.device", _parse_str, "default"
        ),
        ir_learning_timeout_sec=_env_or_cfg(
            "IR_LEARNING_TIMEOUT_SEC", cfg, "ir.learning_timeout_sec", _parse_int, 30
        ),
        dashan_enabled=_env_or_cfg(
            "DASHAN_ENABLED", cfg, "dashan.enabled", _parse_bool, True
        ),
        dashan_mqtt_host=_env_or_cfg(
            "DASHAN_MQTT_HOST", cfg, "dashan.mqtt_host", _parse_str, "localhost"
        ),
        dashan_mqtt_port=_env_or_cfg(
            "DASHAN_MQTT_PORT", cfg, "dashan.mqtt_port", _parse_int, 1883
        ),
        dashan_mqtt_username=_env_or_cfg(
            "DASHAN_MQTT_USERNAME", cfg, "dashan.mqtt_username", _parse_str, None
        ),
        dashan_mqtt_password=_env_or_cfg(
            "DASHAN_MQTT_PASSWORD", cfg, "dashan.mqtt_password", _parse_str, None
        ),
    )
