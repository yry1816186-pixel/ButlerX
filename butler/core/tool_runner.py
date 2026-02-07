from __future__ import annotations

from typing import Any, Dict, List

from .config import ButlerConfig
from .exceptions import (
    ActionExecutionError,
    DeviceError,
    HomeAssistantError,
    ImageGenerationError,
    OpenClawError,
    PrivacyModeError,
    PTZError,
    ScriptExecutionError,
    SystemExecutionError,
    ValidationError,
    VisionError,
    VoiceError,
    WebSearchError,
)
from .models import ActionResult
from .utils import new_uuid, utc_ts
from ..tools.email_client import EmailClient
from ..tools.gateway_client import GatewayClient
from ..tools.ha_api import HomeAssistantAPI
from ..tools.image_gen import ImageGenerator
from ..tools.media_store import store_event
from ..tools.notify import send_notification
from ..tools.openclaw_cli import OpenClawCLI
from ..tools.openclaw_gateway import OpenClawGatewaySync
from ..tools.ptz_onvif import PTZOnvif
from ..tools.script_runner import ScriptRunner
from ..tools.system_exec import SystemExec
from ..tools.vision import VisionClient, VisionConfig
from ..tools.voice import VoiceClient, decode_audio_input, fingerprint_audio
from ..tools.web_search import WebSearchClient
from .device_hub import DeviceControlHub, DeviceBackend
from ..simulator import VirtualDeviceManager
from ..ir_control import IRController
from ..automation import SceneEngine
from ..goal_engine import GoalEngine


class ToolRunner:
    """Executes actions and manages tool integrations.

    Coordinates all tool subsystems including PTZ cameras,
    Home Assistant, email, image generation, voice, vision,
    web search, OpenClaw, system execution, scripts, and devices.

    Attributes:
        config: Butler configuration instance
        db: Database instance for persistence
        ptz: PTZOnvif for camera control
        ha: HomeAssistantAPI for smart home integration
        email: EmailClient for email operations
        image_gen: ImageGenerator for AI image creation
        voice: VoiceClient for speech recognition
        vision: VisionClient for computer vision
        search: WebSearchClient for web queries
        gateway: GatewayClient for HTTP gateway requests
        sys_exec: SystemExec for command execution
        openclaw: OpenClawCLI for OpenClaw integration
        openclaw_gateway: Optional OpenClawGatewaySync for gateway mode
        scripts: ScriptRunner for script execution
        scheduler: Optional ScheduleRunner for task scheduling
        device_hub: DeviceControlHub for unified device control
        ir_controller: IRController for infrared control
        scene_engine: SceneEngine for scene automation
        goal_engine: GoalEngine for goal execution
    """

    def __init__(self, config: ButlerConfig, scheduler: object = None, db: object = None) -> None:
        self.config = config
        self.db = db
        self.ptz = PTZOnvif()
        self.ha = HomeAssistantAPI(
            url=config.ha_url if hasattr(config, "ha_url") else "http://localhost:8123",
            token=config.ha_token if hasattr(config, "ha_token") else None,
            mock=config.ha_mock if hasattr(config, "ha_mock") else True,
        )
        self.email = EmailClient(
            imap_host=config.email_imap_host,
            imap_port=config.email_imap_port,
            imap_ssl=config.email_imap_ssl,
            smtp_host=config.email_smtp_host,
            smtp_port=config.email_smtp_port,
            smtp_ssl=config.email_smtp_ssl,
            smtp_starttls=config.email_smtp_starttls,
            username=config.email_username,
            password=config.email_password,
            default_from=config.email_from,
        )
        self.image_gen = ImageGenerator(
            api_url=config.image_api_url,
            api_key=config.image_api_key,
            model=config.image_model,
            timeout_sec=config.image_timeout_sec,
        )
        self.voice = VoiceClient(
            api_url=config.asr_api_url,
            api_key=config.asr_api_key,
            model=config.asr_model,
            timeout_sec=config.asr_timeout_sec,
            provider=config.asr_provider,
            local_model=config.asr_model_local,
            local_language=config.asr_language,
            local_device=config.asr_device,
            local_compute_type=config.asr_compute_type,
            local_download_dir=config.asr_download_dir,
            local_beam_size=config.asr_beam_size,
            vosk_model_path=config.asr_vosk_model_path,
        )
        self.vision = VisionClient(
            VisionConfig(
                face_model_path=config.vision_face_model_path,
                object_model_path=config.vision_object_model_path,
                device=config.vision_device,
                face_backend=config.vision_face_backend,
                face_match_threshold=config.vision_face_match_threshold,
                face_min_confidence=config.vision_face_min_confidence,
                object_min_confidence=config.vision_object_min_confidence,
                max_faces=config.vision_max_faces,
            ),
            db=db,
        )
        self.search = WebSearchClient(
            api_url=config.search_api_url,
            api_key=config.search_api_key,
            query_param=config.search_query_param,
            key_param=config.search_key_param,
            provider=config.search_provider,
            timeout_sec=config.search_timeout_sec,
        )
        self.gateway = GatewayClient(
            base_url=config.gateway_base_url,
            token=config.gateway_token,
            token_header=config.gateway_token_header,
            timeout_sec=config.gateway_timeout_sec,
            allowlist=config.gateway_allowlist,
        )
        self.sys_exec = SystemExec(config.system_exec_allowlist, config.system_exec_timeout_sec)
        self.openclaw = OpenClawCLI(config.openclaw_cli_path, config.openclaw_env)
        self.openclaw_gateway = None
        if config.openclaw_gateway_enabled:
            self.openclaw_gateway = OpenClawGatewaySync(
                url=config.openclaw_gateway_url,
                token=config.openclaw_gateway_token,
                password=config.openclaw_gateway_password,
            )
        self.scripts = ScriptRunner(
            config.script_dir, config.script_allowlist, config.system_exec_timeout_sec
        )
        self.scheduler = scheduler
        
        self.device_hub = DeviceControlHub(ha_api=self.ha)
        self.ir_controller = IRController()
        self.scene_engine = SceneEngine()
        self.goal_engine = GoalEngine()

    def attach_scheduler(self, scheduler: object) -> None:
        """Attach a scheduler instance for task scheduling.

        Args:
            scheduler: ScheduleRunner instance
        """
        self.scheduler = scheduler

    def execute_plan(
        self, plan_id: str, actions: List[Dict[str, Any]], privacy_mode: bool
    ) -> List[ActionResult]:
        """Execute a list of actions and return results.

        Args:
            plan_id: ID of the plan being executed
            actions: List of action dictionaries with 'action_type' and 'params'
            privacy_mode: Whether privacy mode is enabled

        Returns:
            List of ActionResult objects containing execution status and output
        """
        results: List[ActionResult] = []
        for action in actions:
            if self._blocked_by_privacy(action, privacy_mode):
                results.append(
                    ActionResult(
                        plan_id=plan_id,
                        action_type=action.get("action_type", "unknown"),
                        status="error",
                        output={"error": "privacy_mode_blocked"},
                        ts=utc_ts(),
                    )
                )
                continue
            results.append(self._execute_action(plan_id, action))
        return results

    def _execute_action(self, plan_id: str, action: Dict[str, Any]) -> ActionResult:
        """Execute a single action and return its result.

        Args:
            plan_id: ID of the plan being executed
            action: Action dictionary with 'action_type' and 'params'

        Returns:
            ActionResult containing execution status and output
        """
        action_type = action.get("action_type", "unknown")
        params = action.get("params", {}) or {}
        status = "ok"
        output: Dict[str, Any] = {}

        try:
            if action_type == "ptz_goto_preset":
                name = params.get("name") or params.get("preset") or self.config.ptz_entry_preset
                if not name:
                    raise ValidationError("name parameter is required", field="name")
                output = self.ptz.goto_preset(name)
            elif action_type == "ptz_patrol":
                presets = params.get("presets") or self.config.patrol_presets
                dwell_s = int(params.get("dwell_s") or self.config.ptz_patrol_dwell_sec)
                output = self.ptz.patrol(presets, dwell_s)
            elif action_type == "ptz_stop":
                output = self.ptz.stop()
            elif action_type == "snapshot":
                output = self.ptz.snapshot()
            elif action_type == "notify":
                output = send_notification(
                    params.get("title", "Notification"),
                    params.get("message", ""),
                    params.get("level", "info"),
                )
            elif action_type == "ha_call_service":
                output = self.ha.call_service(
                    params.get("domain", "light"),
                    params.get("service", "turn_on"),
                    params.get("data", {}),
                )
            elif action_type == "email_read":
                output = self.email.read_latest(
                    limit=int(params.get("limit") or 5),
                    folder=str(params.get("folder") or "INBOX"),
                    unread_only=bool(params.get("unread_only", False)),
                )
            elif action_type == "email_send":
                to_value = params.get("to") or []
                if isinstance(to_value, str):
                    to_list = [addr.strip() for addr in to_value.split(",") if addr.strip()]
                else:
                    to_list = [str(addr) for addr in to_value if str(addr).strip()]
                if not to_list:
                    raise ValidationError("to parameter is required", field="to")
                subject = str(params.get("subject") or "")
                if not subject:
                    raise ValidationError("subject parameter is required", field="subject")
                output = self.email.send(
                    to_addrs=to_list,
                    subject=subject,
                    body=str(params.get("body") or ""),
                    from_addr=params.get("from"),
                )
            elif action_type == "image_generate":
                prompt = str(params.get("prompt") or "")
                if not prompt:
                    raise ValidationError("prompt parameter is required", field="prompt")
                output = self.image_gen.generate(
                    prompt=prompt,
                    size=str(params.get("size") or "1024x1024"),
                    n=int(params.get("n") or 1),
                )
            elif action_type == "voice_transcribe":
                output = self.voice.transcribe(
                    audio=params.get("audio"),
                    language=params.get("language"),
                    prompt=params.get("prompt"),
                )
            elif action_type == "voice_enroll":
                if self.db is None:
                    output = {"error": "db_not_available"}
                else:
                    label = str(params.get("label") or "").strip()
                    if not label:
                        output = {"error": "label_required"}
                    else:
                        audio_bytes = decode_audio_input(params.get("audio"))
                        if not audio_bytes:
                            output = {"error": "audio_invalid"}
                        else:
                            fp = fingerprint_audio(audio_bytes)
                            record = {
                                "voiceprint_id": new_uuid(),
                                "label": label,
                                "fingerprint": fp,
                                "created_ts": utc_ts(),
                                "meta": {"source": "voice_enroll"},
                            }
                            self.db.insert_voiceprint(record)
                            output = {"voiceprint_id": record["voiceprint_id"], "label": label}
            elif action_type == "voice_verify":
                if self.db is None:
                    output = {"error": "db_not_available"}
                else:
                    label = params.get("label")
                    voiceprint_id = params.get("voiceprint_id")
                    audio_bytes = decode_audio_input(params.get("audio"))
                    if not audio_bytes:
                        output = {"error": "audio_invalid"}
                    else:
                        fp = fingerprint_audio(audio_bytes)
                        record = self.db.find_voiceprint(
                            voiceprint_id=voiceprint_id, label=label
                        )
                        if not record:
                            output = {"error": "voiceprint_not_found"}
                        else:
                            output = {
                                "match": record["fingerprint"] == fp,
                                "voiceprint_id": record["voiceprint_id"],
                                "label": record["label"],
                            }
            elif action_type == "vision_detect":
                if not self.config.vision_enabled:
                    output = {"error": "vision_disabled"}
                else:
                    images = params.get("images") or params.get("image")
                    if images is None:
                        output = {"error": "image_required"}
                    else:
                        if not isinstance(images, list):
                            images = [images]
                        results = [
                            self.vision.detect(
                                image=item,
                                model=params.get("model", "object"),
                                min_conf=params.get("min_conf"),
                                max_det=params.get("max_det"),
                                match_faces=bool(params.get("match_faces", False)),
                                top_k=int(params.get("top_k") or 3),
                            )
                            for item in images
                        ]
                        output = {"results": results}
            elif action_type == "face_enroll":
                if not self.config.vision_enabled:
                    output = {"error": "vision_disabled"}
                else:
                    label = str(params.get("label") or "").strip()
                    if not label:
                        output = {"error": "label_required"}
                    else:
                        output = self.vision.enroll_face(
                            label=label,
                            image=params.get("image") or params.get("face"),
                            face_index=int(params.get("face_index") or 0),
                        )
            elif action_type == "face_verify":
                if not self.config.vision_enabled:
                    output = {"error": "vision_disabled"}
                else:
                    output = self.vision.verify_face(
                        image=params.get("image") or params.get("face"),
                        label=params.get("label"),
                        faceprint_id=params.get("faceprint_id"),
                    )
            elif action_type == "wakeword_detect":
                text = str(params.get("text") or "")
                if not text:
                    trans = self.voice.transcribe(audio=params.get("audio"))
                    text = str(trans.get("text") or "")
                wake_words = [w.lower() for w in self.config.wake_words]
                matched = None
                for word in wake_words:
                    if word and word in text.lower():
                        matched = word
                        break
                output = {"text": text, "matched": matched, "triggered": bool(matched)}
            elif action_type == "web_search":
                output = self.search.search(
                    query=str(params.get("query") or params.get("q") or ""),
                    limit=int(params.get("limit") or 5),
                )
            elif action_type == "gateway_request":
                output = self.gateway.request(
                    method=str(params.get("method") or "GET"),
                    path=str(params.get("path") or ""),
                    body=params.get("body") if isinstance(params.get("body"), dict) else None,
                )
            elif action_type == "system_exec":
                command = str(params.get("command") or "")
                if not command:
                    raise ValidationError("command parameter is required", field="command")
                args = params.get("args") or []
                if not isinstance(args, list):
                    args = [str(args)]
                output = self.sys_exec.run(command, [str(item) for item in args])
            elif action_type == "script_run":
                script = str(params.get("script") or params.get("name") or "")
                if not script:
                    raise ValidationError("script parameter is required", field="script")
                args = params.get("args") or []
                if not isinstance(args, list):
                    args = [str(args)]
                output = self.scripts.run(script, [str(item) for item in args])
            elif action_type == "schedule_task":
                if self.scheduler is None:
                    output = {"error": "scheduler_not_available"}
                else:
                    run_at = params.get("run_at")
                    delay_sec = params.get("delay_sec")
                    if run_at is None:
                        try:
                            run_at = utc_ts() + int(delay_sec or 0)
                        except (TypeError, ValueError):
                            run_at = utc_ts()
                    actions = params.get("actions") or params.get("action") or []
                    if isinstance(actions, dict):
                        actions = [actions]
                    if not isinstance(actions, list):
                        actions = []
                    note = str(params.get("note") or "Scheduled task")
                    output = self.scheduler.schedule_actions(actions, int(run_at), note)
            elif action_type == "openclaw_message_send":
                target = str(params.get("target") or "")
                message = str(params.get("message") or "")
                if not target:
                    raise ValidationError("target parameter is required", field="target")
                if not message:
                    raise ValidationError("message parameter is required", field="message")
                output = self.openclaw.send_message(
                    target=target,
                    message=message,
                    channel=params.get("channel"),
                    account=params.get("account"),
                )
            elif action_type == "openclaw_send_media":
                output = self.openclaw.send_with_media(
                    target=str(params.get("target") or ""),
                    media=str(params.get("media") or ""),
                    message=str(params.get("message") or ""),
                    channel=params.get("channel"),
                    account=params.get("account"),
                )
            elif action_type == "openclaw_send_buttons":
                buttons = params.get("buttons")
                if buttons and isinstance(buttons, list):
                    output = self.openclaw.send_with_buttons(
                        target=str(params.get("target") or ""),
                        message=str(params.get("message") or ""),
                        buttons=buttons,
                        channel=params.get("channel"),
                        account=params.get("account"),
                    )
                else:
                    status = "error"
                    output = {"error": "buttons_must_be_array"}
            elif action_type == "openclaw_reply_message":
                output = self.openclaw.reply_to_message(
                    target=str(params.get("target") or ""),
                    message_id=str(params.get("message_id") or ""),
                    message=str(params.get("message") or ""),
                    channel=params.get("channel"),
                    account=params.get("account"),
                )
            elif action_type == "openclaw_send_to_thread":
                output = self.openclaw.send_to_thread(
                    target=str(params.get("target") or ""),
                    thread_id=str(params.get("thread_id") or ""),
                    message=str(params.get("message") or ""),
                    channel=params.get("channel"),
                    account=params.get("account"),
                )
            elif action_type == "store_event":
                output = store_event(params.get("kind", "event"), params)
            elif action_type == "device_turn_on":
                device_id = str(params.get("device_id") or params.get("target") or "")
                if not device_id:
                    raise ValidationError("device_id parameter is required", field="device_id")
                output = self.device_hub.turn_on(device_id, **{k: v for k, v in params.items() if k not in ["device_id", "target"]})
            elif action_type == "device_turn_off":
                device_id = str(params.get("device_id") or params.get("target") or "")
                if not device_id:
                    raise ValidationError("device_id parameter is required", field="device_id")
                output = self.device_hub.turn_off(device_id)
            elif action_type == "device_toggle":
                device_id = str(params.get("device_id") or params.get("target") or "")
                if not device_id:
                    raise ValidationError("device_id parameter is required", field="device_id")
                output = self.device_hub.toggle(device_id)
            elif action_type == "set_brightness":
                device_id = str(params.get("device_id") or params.get("target") or "")
                if not device_id:
                    raise ValidationError("device_id parameter is required", field="device_id")
                brightness = int(params.get("brightness") or 255)
                output = self.device_hub.set_brightness(device_id, brightness)
            elif action_type == "set_temperature":
                device_id = str(params.get("device_id") or params.get("target") or "")
                if not device_id:
                    raise ValidationError("device_id parameter is required", field="device_id")
                temperature = float(params.get("temperature") or 22.0)
                output = self.device_hub.set_temperature(device_id, temperature)
            elif action_type == "set_hvac_mode":
                device_id = str(params.get("device_id") or params.get("target") or "")
                if not device_id:
                    raise ValidationError("device_id parameter is required", field="device_id")
                mode = str(params.get("mode") or "auto")
                output = self.device_hub.set_hvac_mode(device_id, mode)
            elif action_type == "open_cover":
                device_id = str(params.get("device_id") or params.get("target") or "")
                if not device_id:
                    raise ValidationError("device_id parameter is required", field="device_id")
                output = self.device_hub.open_cover(device_id)
            elif action_type == "close_cover":
                device_id = str(params.get("device_id") or params.get("target") or "")
                if not device_id:
                    raise ValidationError("device_id parameter is required", field="device_id")
                output = self.device_hub.close_cover(device_id)
            elif action_type == "play_media":
                device_id = str(params.get("device_id") or params.get("target") or "")
                if not device_id:
                    raise ValidationError("device_id parameter is required", field="device_id")
                media_content_id = str(params.get("media_content_id") or "")
                if not media_content_id:
                    raise ValidationError("media_content_id parameter is required", field="media_content_id")
                media_content_type = str(params.get("media_content_type") or "music")
                output = self.device_hub.play_media(device_id, media_content_id, media_content_type)
            elif action_type == "pause_media":
                device_id = str(params.get("device_id") or params.get("target") or "")
                if not device_id:
                    raise ValidationError("device_id parameter is required", field="device_id")
                output = self.device_hub.pause(device_id)
            elif action_type == "stop_media":
                device_id = str(params.get("device_id") or params.get("target") or "")
                if not device_id:
                    raise ValidationError("device_id parameter is required", field="device_id")
                output = self.device_hub.stop(device_id)
            elif action_type == "ir_send_command":
                device_id = str(params.get("device_id") or "")
                command = str(params.get("command") or "")
                if not device_id:
                    raise ValidationError("device_id parameter is required", field="device_id")
                if not command:
                    raise ValidationError("command parameter is required", field="command")
                repeat = int(params.get("repeat") or 1)
                output = self.device_hub.send_ir_command(device_id, command, repeat)
            elif action_type == "ir_learn_command":
                device_id = str(params.get("device_id") or "")
                command_name = str(params.get("command_name") or "")
                if not device_id:
                    raise ValidationError("device_id parameter is required", field="device_id")
                if not command_name:
                    raise ValidationError("command_name parameter is required", field="command_name")
                duration = float(params.get("duration") or 5.0)
                output = self.device_hub.learn_ir_command(device_id, command_name, duration)
            elif action_type == "get_device_state":
                device_id = str(params.get("device_id") or params.get("target") or "")
                if not device_id:
                    raise ValidationError("device_id parameter is required", field="device_id")
                output = self.device_hub.get_device_state(device_id)
            elif action_type == "list_devices":
                backend_filter = params.get("backend")
                output = {"devices": self.device_hub.list_devices(backend_filter)}
            elif action_type == "sync_ha_devices":
                output = self.device_hub.sync_from_homeassistant()
            elif action_type == "activate_scene":
                scene_id = str(params.get("scene_id") or params.get("target") or "")
                output = self.scene_engine.activate_scene(scene_id, lambda action: self._execute_action(plan_id, action))
            elif action_type == "execute_goal":
                goal_text = str(params.get("text") or params.get("goal") or "")
                from ..goal_engine import GoalContext
                goal = self.goal_engine.parse_goal(goal_text)
                if goal:
                    output = self.goal_engine.execute_goal(
                        goal,
                        lambda action, ctx: self._execute_action(plan_id, action)
                    )
                else:
                    status = "error"
                    output = {"error": f"Failed to parse goal: {goal_text}"}
            elif action_type == "get_goals":
                output = {"goals": self.goal_engine.list_goals()}
            elif action_type == "get_scenes":
                output = {"scenes": self.scene_engine.list_scenes()}
            else:
                status = "error"
                output = {"error": f"Unsupported action_type: {action_type}"}
        except ButlerError as exc:
            status = "error"
            output = exc.to_dict()
        except ValueError as exc:
            status = "error"
            output = ValidationError(str(exc)).to_dict()
        except ConnectionError as exc:
            status = "error"
            output = ActionExecutionError(str(exc)).to_dict()
        except TimeoutError as exc:
            status = "error"
            output = ActionExecutionError(str(exc)).to_dict()
        except Exception as exc:
            status = "error"
            output = ActionExecutionError(str(exc)).to_dict()

        return ActionResult(
            plan_id=plan_id,
            action_type=action_type,
            status=status,
            output=output,
            ts=utc_ts(),
        )

    def _blocked_by_privacy(self, action: Dict[str, Any], privacy_mode: bool) -> bool:
        """Check if an action is blocked by privacy mode.

        Args:
            action: Action dictionary with 'action_type' and optional 'params'
            privacy_mode: Whether privacy mode is enabled

        Returns:
            True if the action should be blocked, False otherwise
        """
        if not privacy_mode:
            return False
        action_type = action.get("action_type", "")
        if action_type == "store_event":
            kind = (action.get("params") or {}).get("kind")
            return kind in self.config.privacy_block_store_kinds
        return action_type in self.config.camera_action_types
