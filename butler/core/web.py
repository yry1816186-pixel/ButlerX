from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .capabilities import action_catalog
from .service import ButlerService
from .auth import get_auth_manager, get_current_user, get_admin_user, require_role
from .rate_limit import check_rate_limit_middleware
from .error_handler import butler_exception_handler, ValidationError, AuthenticationError, AuthorizationError
from .schemas import (
    CommandPayload,
    StateUpdatePayload,
    SystemExecPayload,
    ScriptRunPayload,
    ImageGenPayload,
    VoiceASRPayload,
    VoiceTTSPayload,
    SearchPayload,
    HomeAssistantPayload,
    EmailPayload,
    AutomationRulePayload,
    FaceEnrollPayload,
    FaceVerifyPayload,
    PTZPayload,
    SnapshotPayload,
    VisionDetectPayload,
    WebSearchPayload,
)


def create_app(service: ButlerService) -> FastAPI:
    app = FastAPI(title="Butler Control Panel")
    app.state.service = service
    app.state.config = service.config

    app.add_exception_handler(Exception, butler_exception_handler)

    allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:8000,http://localhost:3000").split(",")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        middleware = check_rate_limit_middleware(
            requests_per_minute=60,
            requests_per_hour=1000,
            burst_limit=10,
        )
        return await middleware(request, call_next)

    auth = get_auth_manager()
    admin_api_key = auth.generate_api_key("admin")
    user_api_key = auth.generate_api_key("user")
    print(f"Admin API Key: {admin_api_key}")
    print(f"User API Key: {user_api_key}")
    print(f"Default admin password: {os.getenv('BUTLER_ADMIN_PASSWORD', 'admin123')}")
    print(f"Default user password: {os.getenv('BUTLER_USER_PASSWORD', 'user123')}")

    ui_dir = Path(__file__).resolve().parents[1] / "ui"
    assets_dir = ui_dir / "assets"
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.on_event("startup")
    def _startup() -> None:
        service.start()

    @app.on_event("shutdown")
    def _shutdown() -> None:
        service.stop()

    @app.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url="/dashboard")

    @app.get("/dashboard")
    @app.get("/dashboard.html")
    def dashboard() -> FileResponse:
        return FileResponse(str(ui_dir / "dashboard.html"))

    @app.get("/controls")
    @app.get("/controls.html")
    def controls() -> FileResponse:
        return FileResponse(str(ui_dir / "controls.html"))

    @app.get("/ai")
    @app.get("/ai.html")
    def ai() -> FileResponse:
        return FileResponse(str(ui_dir / "ai.html"))

    @app.get("/alerts")
    @app.get("/alerts.html")
    def alerts() -> FileResponse:
        return FileResponse(str(ui_dir / "alerts.html"))

    @app.get("/devices")
    @app.get("/devices.html")
    def devices() -> FileResponse:
        return FileResponse(str(ui_dir / "devices.html"))

    @app.get("/health")
    @app.get("/health.html")
    def health() -> FileResponse:
        return FileResponse(str(ui_dir / "health.html"))

    @app.get("/logs")
    @app.get("/logs.html")
    def logs() -> FileResponse:
        return FileResponse(str(ui_dir / "logs.html"))

    @app.get("/scenes")
    @app.get("/scenes.html")
    def scenes() -> FileResponse:
        return FileResponse(str(ui_dir / "scenes.html"))

    @app.get("/security")
    @app.get("/security.html")
    def security() -> FileResponse:
        return FileResponse(str(ui_dir / "security.html"))

    @app.get("/settings")
    @app.get("/settings.html")
    def settings() -> FileResponse:
        return FileResponse(str(ui_dir / "settings.html"))

    @app.get("/vision")
    @app.get("/vision.html")
    def vision() -> FileResponse:
        return FileResponse(str(ui_dir / "vision.html"))

    @app.get("/evidence/{kind}/{ref_id}")
    def evidence(kind: str, ref_id: str) -> HTMLResponse:
        body = (
            "<html><head><title>Evidence</title></head>"
            "<body style='font-family:Arial,sans-serif;padding:24px;'>"
            f"<h2>Mock Evidence</h2><p>Kind: {kind}</p><p>Ref: {ref_id}</p>"
            "<p>This is a placeholder for evidence references.</p>"
            "</body></html>"
        )
        return HTMLResponse(content=body)

    @app.get("/api/dashboard")
    async def api_dashboard(request: Request) -> Dict[str, Any]:
        await get_current_user(request)
        privacy_mode = bool(
            service.db.get_state("privacy_mode", service.config.privacy_mode_default)
        )
        mode = service.db.get_state("mode", service.config.mode_default)
        return {
            "mode": mode,
            "privacy_mode": privacy_mode,
            "events": service.db.get_recent_events(10),
            "plans": service.db.get_recent_plans(10),
            "results": service.db.get_recent_results(10),
        }

    @app.get("/api/config")
    def api_config() -> Dict[str, Any]:
        return {
            "mqtt": {"host": service.config.mqtt_host, "port": service.config.mqtt_port},
            "topics": {
                "in_event": service.config.topic_in_event,
                "in_command": service.config.topic_in_command,
                "out_event": service.config.topic_out_event,
                "out_action_plan": service.config.topic_out_action_plan,
                "out_action_result": service.config.topic_out_action_result,
                "sub_topics": service.config.sub_topics,
                "publish_topics": service.config.publish_topics,
            },
            "defaults": {
                "mode": service.config.mode_default,
                "privacy": service.config.privacy_mode_default,
                "cooldown_minutes": int(service.config.r1_cooldown_sec / 60),
            },
            "ui": {"poll_interval_ms": service.config.ui_poll_interval_ms},
        }

    @app.get("/api/state")
    def api_state() -> Dict[str, Any]:
        return {
            "privacy_mode": bool(
                service.db.get_state("privacy_mode", service.config.privacy_mode_default)
            ),
            "mode": service.db.get_state("mode", service.config.mode_default),
        }

    @app.post("/api/command")
    async def api_command(payload: CommandPayload, request: Request) -> JSONResponse:
        await get_current_user(request)
        service.publish_command(payload.dict())
        return JSONResponse({"status": "ok"})

    @app.get("/api/brain/capabilities")
    def api_brain_capabilities() -> Dict[str, Any]:
        return {
            "actions": service.brain_allowed_actions,
            "action_catalog": action_catalog(),
            "system_exec_allowlist": service.config.system_exec_allowlist,
            "script_dir": service.config.script_dir,
            "script_allowlist": service.config.script_allowlist,
            "wake_words": service.config.wake_words,
            "llm": {
                "model_text": service.config.llm_model_text,
                "model_vision": service.config.llm_model_vision,
                "base_url": service.config.llm_base_url,
            },
            "brain": {
                "cache_ttl_sec": service.config.brain_cache_ttl_sec,
                "cache_size": service.config.brain_cache_size,
                "max_actions": service.config.brain_max_actions,
                "retry_attempts": service.config.brain_retry_attempts,
                "rules_count": len(service.rule_engine.rules),
                "rules_allow_images": service.config.brain_rules_allow_images,
            },
            "scheduler": {
                "enabled": service.config.scheduler_enabled,
                "interval_sec": service.config.scheduler_interval_sec,
            },
            "asr": {
                "api_url": service.config.asr_api_url,
                "model": service.config.asr_model,
                "provider": service.config.asr_provider,
                "model_local": service.config.asr_model_local,
                "language": service.config.asr_language,
                "device": service.config.asr_device,
                "compute_type": service.config.asr_compute_type,
                "download_dir": service.config.asr_download_dir,
                "beam_size": service.config.asr_beam_size,
                "vosk_model_path": service.config.asr_vosk_model_path,
            },
            "vision": {
                "enabled": service.config.vision_enabled,
                "device": service.config.vision_device,
                "face_model_path": service.config.vision_face_model_path,
                "object_model_path": service.config.vision_object_model_path,
                "face_backend": service.config.vision_face_backend,
                "face_match_threshold": service.config.vision_face_match_threshold,
            },
            "search": {
                "api_url": service.config.search_api_url,
                "provider": service.config.search_provider,
            },
            "gateway": {
                "base_url": service.config.gateway_base_url,
                "allowlist": service.config.gateway_allowlist,
            },
        }

    @app.get("/api/brain/rules")
    def api_brain_rules() -> Dict[str, Any]:
        return {"rules": service.config.brain_rules}

    @app.post("/api/brain/rules")
    async def api_brain_rules_update(request: Request) -> JSONResponse:
        payload = await request.json()
        rules = payload.get("rules")
        if not isinstance(rules, list):
            return JSONResponse({"status": "error", "error": "rules must be a list"}, status_code=400)
        persist = bool(payload.get("persist", False))
        result = service.update_brain_rules(rules, persist=persist)
        return JSONResponse({"status": "ok", **result})

    @app.get("/api/schedules")
    def api_schedules() -> Dict[str, Any]:
        now = int(time.time())
        due = service.db.get_due_schedules(now, limit=20)
        return {"due": due}

    @app.post("/api/voice/transcribe")
    async def api_voice_transcribe(payload: VoiceASRPayload, request: Request) -> JSONResponse:
        await get_current_user(request)
        output = service.tool_runner.voice.transcribe(
            audio=payload.audio_data,
            language=payload.format,
            prompt=payload.language,
        )
        return JSONResponse({"status": "ok", "output": output})

    @app.post("/api/voice/enroll")
    async def api_voice_enroll(payload: VoiceASRPayload, request: Request) -> JSONResponse:
        await get_current_user(request)
        results = service.tool_runner.execute_plan(
            "voice_enroll_api",
            [{"action_type": "voice_enroll", "params": {"label": payload.language, "audio": payload.audio_data}}],
            privacy_mode=False,
        )
        return JSONResponse({"status": "ok", "output": results[0].to_dict() if results else {}})

    @app.post("/api/voice/verify")
    async def api_voice_verify(payload: VoiceASRPayload, request: Request) -> JSONResponse:
        await get_current_user(request)
        results = service.tool_runner.execute_plan(
            "voice_verify_api",
            [
                {
                    "action_type": "voice_verify",
                    "params": {
                        "audio": payload.audio_data,
                        "label": payload.label,
                        "voiceprint_id": payload.voiceprint_id,
                    },
                }
            ],
            privacy_mode=False,
        )
        return JSONResponse({"status": "ok", "output": results[0].to_dict() if results else {}})

    @app.post("/api/voice/wake")
    async def api_voice_wake(payload: VoiceASRPayload, request: Request) -> JSONResponse:
        await get_current_user(request)
        results = service.tool_runner.execute_plan(
            "wakeword_api",
            [
                {
                    "action_type": "wakeword_detect",
                    "params": {"audio": payload.audio_data, "text": payload.prompt},
                }
            ],
            privacy_mode=False,
        )
        return JSONResponse({"status": "ok", "output": results[0].to_dict() if results else {}})

    @app.post("/api/vision/detect")
    async def api_vision_detect(payload: VisionDetectPayload, request: Request) -> JSONResponse:
        await get_current_user(request)
        results = service.tool_runner.execute_plan(
            "vision_detect_api",
            [
                {
                    "action_type": "vision_detect",
                    "params": {
                        "images": payload.images,
                        "model": payload.model,
                        "min_conf": payload.min_conf,
                        "max_det": payload.max_det,
                        "match_faces": payload.match_faces,
                        "top_k": payload.top_k,
                    },
                }
            ],
            privacy_mode=False,
        )
        return JSONResponse({"status": "ok", "output": results[0].to_dict() if results else {}})

    @app.post("/api/face/enroll")
    async def api_face_enroll(payload: FaceEnrollPayload, request: Request) -> JSONResponse:
        await get_current_user(request)
        results = service.tool_runner.execute_plan(
            "face_enroll_api",
            [
                {
                    "action_type": "face_enroll",
                    "params": {
                        "label": payload.name,
                        "image": payload.image_data,
                        "face_index": 0,
                    },
                }
            ],
            privacy_mode=False,
        )
        return JSONResponse({"status": "ok", "output": results[0].to_dict() if results else {}})

    @app.post("/api/face/verify")
    async def api_face_verify(payload: FaceVerifyPayload, request: Request) -> JSONResponse:
        await get_current_user(request)
        results = service.tool_runner.execute_plan(
            "face_verify_api",
            [
                {
                    "action_type": "face_verify",
                    "params": {
                        "image": payload.image_data,
                        "label": None,
                        "faceprint_id": None,
                    },
                }
            ],
            privacy_mode=False,
        )
        return JSONResponse({"status": "ok", "output": results[0].to_dict() if results else {}})

    @app.get("/api/voice/prints")
    def api_voiceprints() -> Dict[str, Any]:
        return {"prints": service.db.list_voiceprints()}

    @app.get("/api/face/prints")
    def api_faceprints() -> Dict[str, Any]:
        return {"prints": service.db.list_faceprints()}

    @app.post("/api/web/search")
    async def api_web_search(payload: WebSearchPayload, request: Request) -> JSONResponse:
        await get_current_user(request)
        results = service.tool_runner.execute_plan(
            "web_search_api",
            [
                {
                    "action_type": "web_search",
                    "params": {"query": payload.query, "limit": payload.limit},
                }
            ],
            privacy_mode=False,
        )
        return JSONResponse({"status": "ok", "output": results[0].to_dict() if results else {}})

    @app.post("/api/gateway/request")
    async def api_gateway_request(request: Request) -> JSONResponse:
        payload = await request.json()
        results = service.tool_runner.execute_plan(
            "gateway_api",
            [
                {
                    "action_type": "gateway_request",
                    "params": {
                        "method": payload.get("method", "GET"),
                        "path": payload.get("path"),
                        "body": payload.get("body"),
                    },
                }
            ],
            privacy_mode=False,
        )
        return JSONResponse({"status": "ok", "output": results[0].to_dict() if results else {}})

    @app.post("/api/brain/plan")
    async def api_brain_plan(request: Request) -> JSONResponse:
        payload = await request.json()
        text = payload.get("text") or payload.get("message")
        if not text:
            return JSONResponse({"status": "error", "error": "text required"}, status_code=400)
        cache = payload.get("cache")
        use_cache = True if cache is None else bool(cache)
        try:
            result = service.handle_brain_request(
                text=str(text),
                images=payload.get("images") or [],
                context=payload.get("context") or {},
                execute=False,
                cache=use_cache,
            )
            return JSONResponse({"status": "ok", **result})
        except Exception as exc:  # pragma: no cover - runtime error path
            return JSONResponse({"status": "error", "error": str(exc)}, status_code=500)

    @app.post("/api/brain/act")
    async def api_brain_act(request: Request) -> JSONResponse:
        payload = await request.json()
        text = payload.get("text") or payload.get("message")
        if not text:
            return JSONResponse({"status": "error", "error": "text required"}, status_code=400)
        cache = payload.get("cache")
        use_cache = True if cache is None else bool(cache)
        try:
            result = service.handle_brain_request(
                text=str(text),
                images=payload.get("images") or [],
                context=payload.get("context") or {},
                execute=True,
                cache=use_cache,
            )
            return JSONResponse({"status": "ok", **result})
        except Exception as exc:
            return JSONResponse({"status": "error", "error": str(exc)}, status_code=500)

    @app.get("/api/devices")
    async def api_devices_list() -> JSONResponse:
        devices = service.tool_runner.device_hub.list_devices()
        return JSONResponse({"status": "ok", "devices": devices})

    @app.post("/api/devices/sync")
    async def api_devices_sync() -> JSONResponse:
        result = service.tool_runner.device_hub.sync_from_homeassistant()
        return JSONResponse({"status": "ok", **result})

    @app.post("/api/devices/turn_on")
    async def api_device_turn_on(request: Request) -> JSONResponse:
        payload = await request.json()
        device_id = payload.get("device_id")
        if not device_id:
            return JSONResponse({"status": "error", "error": "device_id required"}, status_code=400)
        result = service.tool_runner.device_hub.turn_on(device_id)
        return JSONResponse({"status": "ok", **result})

    @app.post("/api/devices/turn_off")
    async def api_device_turn_off(request: Request) -> JSONResponse:
        payload = await request.json()
        device_id = payload.get("device_id")
        if not device_id:
            return JSONResponse({"status": "error", "error": "device_id required"}, status_code=400)
        result = service.tool_runner.device_hub.turn_off(device_id)
        return JSONResponse({"status": "ok", **result})

    @app.post("/api/devices/toggle")
    async def api_device_toggle(request: Request) -> JSONResponse:
        payload = await request.json()
        device_id = payload.get("device_id")
        if not device_id:
            return JSONResponse({"status": "error", "error": "device_id required"}, status_code=400)
        result = service.tool_runner.device_hub.toggle(device_id)
        return JSONResponse({"status": "ok", **result})

    @app.post("/api/devices/set_brightness")
    async def api_device_set_brightness(request: Request) -> JSONResponse:
        payload = await request.json()
        device_id = payload.get("device_id")
        brightness = payload.get("brightness")
        if not device_id or brightness is None:
            return JSONResponse({"status": "error", "error": "device_id and brightness required"}, status_code=400)
        result = service.tool_runner.device_hub.set_brightness(device_id, brightness)
        return JSONResponse({"status": "ok", **result})

    @app.post("/api/devices/set_temperature")
    async def api_device_set_temperature(request: Request) -> JSONResponse:
        payload = await request.json()
        device_id = payload.get("device_id")
        temperature = payload.get("temperature")
        if not device_id or temperature is None:
            return JSONResponse({"status": "error", "error": "device_id and temperature required"}, status_code=400)
        result = service.tool_runner.device_hub.set_temperature(device_id, temperature)
        return JSONResponse({"status": "ok", **result})

    @app.post("/api/devices/set_hvac_mode")
    async def api_device_set_hvac_mode(request: Request) -> JSONResponse:
        payload = await request.json()
        device_id = payload.get("device_id")
        mode = payload.get("mode")
        if not device_id or not mode:
            return JSONResponse({"status": "error", "error": "device_id and mode required"}, status_code=400)
        result = service.tool_runner.device_hub.set_hvac_mode(device_id, mode)
        return JSONResponse({"status": "ok", **result})

    @app.post("/api/devices/open_cover")
    async def api_device_open_cover(request: Request) -> JSONResponse:
        payload = await request.json()
        device_id = payload.get("device_id")
        if not device_id:
            return JSONResponse({"status": "error", "error": "device_id required"}, status_code=400)
        result = service.tool_runner.device_hub.open_cover(device_id)
        return JSONResponse({"status": "ok", **result})

    @app.post("/api/devices/close_cover")
    async def api_device_close_cover(request: Request) -> JSONResponse:
        payload = await request.json()
        device_id = payload.get("device_id")
        if not device_id:
            return JSONResponse({"status": "error", "error": "device_id required"}, status_code=400)
        result = service.tool_runner.device_hub.close_cover(device_id)
        return JSONResponse({"status": "ok", **result})

    @app.post("/api/devices/play_media")
    async def api_device_play_media(request: Request) -> JSONResponse:
        payload = await request.json()
        device_id = payload.get("device_id")
        media_content_id = payload.get("media_content_id")
        media_content_type = payload.get("media_content_type", "music")
        if not device_id or not media_content_id:
            return JSONResponse({"status": "error", "error": "device_id and media_content_id required"}, status_code=400)
        result = service.tool_runner.device_hub.play_media(device_id, media_content_id, media_content_type)
        return JSONResponse({"status": "ok", **result})

    @app.post("/api/devices/pause")
    async def api_device_pause(request: Request) -> JSONResponse:
        payload = await request.json()
        device_id = payload.get("device_id")
        if not device_id:
            return JSONResponse({"status": "error", "error": "device_id required"}, status_code=400)
        result = service.tool_runner.device_hub.pause(device_id)
        return JSONResponse({"status": "ok", **result})

    @app.post("/api/devices/play")
    async def api_device_play(request: Request) -> JSONResponse:
        payload = await request.json()
        device_id = payload.get("device_id")
        if not device_id:
            return JSONResponse({"status": "error", "error": "device_id required"}, status_code=400)
        result = service.tool_runner.device_hub.play(device_id)
        return JSONResponse({"status": "ok", **result})

    @app.post("/api/devices/stop")
    async def api_device_stop(request: Request) -> JSONResponse:
        payload = await request.json()
        device_id = payload.get("device_id")
        if not device_id:
            return JSONResponse({"status": "error", "error": "device_id required"}, status_code=400)
        result = service.tool_runner.device_hub.stop(device_id)
        return JSONResponse({"status": "ok", **result})

    @app.post("/api/devices/state")
    async def api_device_state(request: Request) -> JSONResponse:
        payload = await request.json()
        device_id = payload.get("device_id")
        if not device_id:
            return JSONResponse({"status": "error", "error": "device_id required"}, status_code=400)
        result = service.tool_runner.device_hub.get_device_state(device_id)
        return JSONResponse({"status": "ok", **result})

    @app.get("/api/scenes")
    async def api_scenes_list() -> JSONResponse:
        scenes = service.tool_runner.scene_engine.list_scenes()
        return JSONResponse({"status": "ok", "scenes": scenes})

    @app.post("/api/scenes/activate")
    async def api_scenes_activate(request: Request) -> JSONResponse:
        payload = await request.json()
        scene_id = payload.get("scene_id")
        if not scene_id:
            return JSONResponse({"status": "error", "error": "scene_id required"}, status_code=400)
        def execute_action(action):
            return service.tool_runner.execute_plan("scene_activation", [action], privacy_mode=False)
        result = service.tool_runner.scene_engine.activate_scene(scene_id, execute_action)
        return JSONResponse({"status": "ok", **result})

    @app.post("/api/ir/send")
    async def api_ir_send(request: Request) -> JSONResponse:
        payload = await request.json()
        device_id = payload.get("device_id")
        command = payload.get("command")
        repeat = payload.get("repeat", 1)
        if not device_id or not command:
            return JSONResponse({"status": "error", "error": "device_id and command required"}, status_code=400)
        result = service.tool_runner.ir_controller.send_command(device_id, command, repeat)
        return JSONResponse({"status": "ok", **result})

    @app.post("/api/ir/learn")
    async def api_ir_learn(request: Request) -> JSONResponse:
        payload = await request.json()
        device_id = payload.get("device_id")
        command_name = payload.get("command_name")
        duration = payload.get("duration", 5.0)
        if not device_id or not command_name:
            return JSONResponse({"status": "error", "error": "device_id and command_name required"}, status_code=400)
        session_id = service.tool_runner.ir_controller.start_learning_session(device_id)
        result = service.tool_runner.ir_controller.learn_command(session_id, duration)
        if result.get("success"):
            service.tool_runner.ir_controller.add_mapping(device_id, command_name, result.get("code"))
        return JSONResponse({"status": "ok", **result})

    @app.get("/api/goals")
    async def api_goals_list() -> JSONResponse:
        goals = service.tool_runner.goal_engine.list_goals()
        return JSONResponse({"status": "ok", "goals": goals})

    @app.post("/api/goals/execute")
    async def api_goals_execute(request: Request) -> JSONResponse:
        payload = await request.json()
        text = payload.get("text")
        if not text:
            return JSONResponse({"status": "error", "error": "text required"}, status_code=400)
        from ..goal_engine import GoalContext
        goal = service.tool_runner.goal_engine.parse_goal(text)
        if not goal:
            return JSONResponse({"status": "error", "error": "Failed to parse goal"}, status_code=400)
        def execute_action(action, ctx):
            return service.tool_runner.execute_plan("goal_execution", [action], privacy_mode=False)
        result = service.tool_runner.goal_engine.execute_goal(goal, execute_action)
        return JSONResponse({"status": "ok", **result})

    return app
