from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReplayEvent:
    timestamp: float
    event_type: str
    device_id: Optional[str] = None
    action: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "device_id": self.device_id,
            "action": self.action,
            "params": self.params,
            "metadata": self.metadata,
        }


@dataclass
class ReplaySession:
    session_id: str
    name: str
    description: str
    events: List[ReplayEvent] = field(default_factory=list)
    duration: float = 0.0
    created_at: float = field(default_factory=time.time)
    status: str = "ready"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "description": self.description,
            "events": [e.to_dict() for e in self.events],
            "duration": self.duration,
            "created_at": self.created_at,
            "status": self.status,
        }


class SceneReplayer:
    def __init__(self) -> None:
        self.sessions: Dict[str, ReplaySession] = {}
        self.active_session: Optional[ReplaySession] = None
        self.device_executor: Optional[Callable] = None
        self._init_default_sessions()

    def _init_default_sessions(self) -> None:
        default_sessions = [
            ReplaySession(
                session_id="session_morning_routine",
                name="晨间例行",
                description="模拟早晨起床后的典型操作",
                events=[
                    ReplayEvent(timestamp=0.0, event_type="voice_command", params={"text": "我要起床"}),
                    ReplayEvent(timestamp=1.0, event_type="device_action", device_id="bedroom_curtain", action="open", params={}),
                    ReplayEvent(timestamp=1.5, event_type="device_action", device_id="bedroom_light", action="turn_on", params={"brightness": 80}),
                    ReplayEvent(timestamp=2.0, event_type="device_action", device_id="living_room_curtain", action="open", params={}),
                    ReplayEvent(timestamp=2.5, event_type="device_action", device_id="living_room_light", action="turn_on", params={"brightness": 100}),
                    ReplayEvent(timestamp=3.0, event_type="device_action", device_id="temperature_sensor", action="simulate_value", params={"value": 22.5}),
                    ReplayEvent(timestamp=3.5, event_type="device_action", device_id="humidity_sensor", action="simulate_value", params={"value": 55.0}),
                ],
                duration=4.0,
            ),
            ReplaySession(
                session_id="session_evening_routine",
                name="晚间例行",
                description="模拟晚上的典型操作",
                events=[
                    ReplayEvent(timestamp=0.0, event_type="voice_command", params={"text": "我要看电影"}),
                    ReplayEvent(timestamp=1.0, event_type="device_action", device_id="living_room_curtain", action="close", params={}),
                    ReplayEvent(timestamp=1.5, event_type="device_action", device_id="living_room_light", action="set_brightness", params={"value": 20}),
                    ReplayEvent(timestamp=2.0, event_type="device_action", device_id="living_room_ac", action="set_temperature", params={"value": 23}),
                    ReplayEvent(timestamp=2.5, event_type="device_action", device_id="living_room_camera", action="start_recording", params={}),
                ],
                duration=3.0,
            ),
            ReplaySession(
                session_id="session_sleep_routine",
                name="睡眠例行",
                description="模拟睡前的操作",
                events=[
                    ReplayEvent(timestamp=0.0, event_type="voice_command", params={"text": "我要睡了"}),
                    ReplayEvent(timestamp=1.0, event_type="device_action", device_id="living_room_light", action="turn_off", params={}),
                    ReplayEvent(timestamp=1.5, event_type="device_action", device_id="bedroom_light", action="turn_off", params={}),
                    ReplayEvent(timestamp=2.0, event_type="device_action", device_id="living_room_curtain", action="close", params={}),
                    ReplayEvent(timestamp=2.5, event_type="device_action", device_id="bedroom_curtain", action="close", params={}),
                    ReplayEvent(timestamp=3.0, event_type="device_action", device_id="living_room_ac", action="set_temperature", params={"value": 22}),
                    ReplayEvent(timestamp=3.5, event_type="device_action", device_id="bedroom_ac", action="set_temperature", params={"value": 21}),
                ],
                duration=4.0,
            ),
            ReplaySession(
                session_id="session_away_routine",
                name="离家例行",
                description="模拟离家前的操作",
                events=[
                    ReplayEvent(timestamp=0.0, event_type="voice_command", params={"text": "我要出门"}),
                    ReplayEvent(timestamp=1.0, event_type="device_action", device_id="living_room_light", action="turn_off", params={}),
                    ReplayEvent(timestamp=1.5, event_type="device_action", device_id="bedroom_light", action="turn_off", params={}),
                    ReplayEvent(timestamp=2.0, event_type="device_action", device_id="living_room_ac", action="turn_off", params={}),
                    ReplayEvent(timestamp=2.5, event_type="device_action", device_id="front_door_lock", action="lock", params={}),
                ],
                duration=3.0,
            ),
        ]

        for session in default_sessions:
            self.add_session(session)

        logger.info(f"Initialized {len(default_sessions)} replay sessions")

    def add_session(self, session: ReplaySession) -> None:
        self.sessions[session.session_id] = session
        logger.info(f"Added replay session: {session.name}")

    def remove_session(self, session_id: str) -> bool:
        if session_id not in self.sessions:
            return False
        session = self.sessions.pop(session_id)
        logger.info(f"Removed replay session: {session.name}")
        return True

    def get_session(self, session_id: str) -> Optional[ReplaySession]:
        return self.sessions.get(session_id)

    def list_sessions(self) -> List[ReplaySession]:
        return list(self.sessions.values())

    def set_device_executor(self, executor: Callable) -> None:
        self.device_executor = executor

    def replay_session(
        self,
        session_id: str,
        speed: float = 1.0,
        stop_on_error: bool = False
    ) -> Dict[str, Any]:
        result = {
            "success": False,
            "message": "",
            "session_id": session_id,
            "events_executed": 0,
            "events_failed": 0,
            "start_time": time.time(),
            "end_time": None,
            "duration": 0.0,
        }

        session = self.sessions.get(session_id)
        if not session:
            result["message"] = f"回放会话不存在: {session_id}"
            return result

        self.active_session = session
        session.status = "running"

        try:
            logger.info(f"Starting replay session: {session.name}")

            start_time = time.time()
            events_executed = 0
            events_failed = 0

            for event in session.events:
                try:
                    self._execute_event(event, speed)
                    events_executed += 1
                    
                    if event.timestamp > 0:
                        delay = (event.timestamp / speed)
                        time.sleep(delay)
                except Exception as e:
                    logger.error(f"Event execution failed: {e}")
                    events_failed += 1
                    
                    if stop_on_error:
                        break

            end_time = time.time()
            result["end_time"] = end_time
            result["duration"] = end_time - start_time
            result["events_executed"] = events_executed
            result["events_failed"] = events_failed
            result["success"] = events_failed == 0
            result["message"] = f"成功回放 {events_executed}/{len(session.events)} 个事件"

            session.status = "completed" if events_failed == 0 else "partial"
            logger.info(f"Completed replay session: {session.name}")

        except Exception as e:
            logger.error(f"Replay session failed: {e}")
            result["message"] = f"回放失败: {str(e)}"
            session.status = "failed"
            result["end_time"] = time.time()
            result["duration"] = result["end_time"] - result["start_time"]

        self.active_session = None
        return result

    def _execute_event(
        self,
        event: ReplayEvent,
        speed: float
    ) -> None:
        if event.event_type == "voice_command":
            logger.info(f"Voice command: {event.params.get('text')}")
        elif event.event_type == "device_action":
            if self.device_executor and event.device_id and event.action:
                self.device_executor(
                    event.device_id,
                    event.action,
                    event.params
                )
            else:
                logger.warning(
                    f"Cannot execute device action: device_executor={self.device_executor is not None}, "
                    f"device_id={event.device_id}, action={event.action}"
                )
        elif event.event_type == "sensor_reading":
            logger.info(f"Sensor reading: {event.device_id} = {event.params}")
        else:
            logger.info(f"Unknown event type: {event.event_type}")

    def create_session_from_events(
        self,
        name: str,
        description: str,
        events: List[ReplayEvent]
    ) -> ReplaySession:
        import uuid
        if events:
            duration = max(e.timestamp for e in events)
        else:
            duration = 0.0

        session = ReplaySession(
            session_id=str(uuid.uuid4()),
            name=name,
            description=description,
            events=events,
            duration=duration,
        )
        self.add_session(session)
        return session

    def record_event(
        self,
        session_id: str,
        event: ReplayEvent
    ) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.events.append(event)
        session.duration = max(e.timestamp for e in session.events)
        logger.debug(f"Recorded event to session {session_id}")
        return True

    def stop_replay(self) -> bool:
        if not self.active_session:
            return False

        self.active_session.status = "stopped"
        self.active_session = None
        logger.info("Stopped active replay session")
        return True

    def get_active_session(self) -> Optional[ReplaySession]:
        return self.active_session

    def search_sessions(self, query: str) -> List[ReplaySession]:
        query_lower = query.lower()
        return [
            session for session in self.sessions.values()
            if (query_lower in session.name.lower() or 
                query_lower in session.description.lower())
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sessions": [session.to_dict() for session in self.sessions.values()],
            "session_count": len(self.sessions),
            "active_session": self.active_session.to_dict() if self.active_session else None,
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Replay sessions saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "SceneReplayer":
        replayer = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for session_data in data.get("sessions", []):
            events = []
            for event_data in session_data.get("events", []):
                event = ReplayEvent(
                    timestamp=event_data["timestamp"],
                    event_type=event_data["event_type"],
                    device_id=event_data.get("device_id"),
                    action=event_data.get("action"),
                    params=event_data.get("params", {}),
                    metadata=event_data.get("metadata", {}),
                )
                events.append(event)

            session = ReplaySession(
                session_id=session_data["session_id"],
                name=session_data["name"],
                description=session_data["description"],
                events=events,
                duration=session_data.get("duration", 0.0),
                created_at=session_data.get("created_at", time.time()),
                status=session_data.get("status", "ready"),
            )
            replayer.add_session(session)

        logger.info(f"Replay sessions loaded from {filepath}")
        return replayer
