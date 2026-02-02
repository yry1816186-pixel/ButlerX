from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import time
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class UserProfile:
    user_id: str
    name: str
    voice_id: Optional[str] = None
    face_id: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    routines: Dict[str, Any] = field(default_factory=dict)
    is_home: bool = False
    last_seen: Optional[float] = None

    def set_preference(self, key: str, value: Any) -> None:
        self.preferences[key] = value

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self.preferences.get(key, default)

    def get_routine(self, routine_name: str) -> Optional[Dict[str, Any]]:
        return self.routines.get(routine_name)

    def set_routine(self, routine_name: str, routine_data: Dict[str, Any]) -> None:
        self.routines[routine_name] = routine_data

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "voice_id": self.voice_id,
            "face_id": self.face_id,
            "preferences": self.preferences,
            "routines": self.routines,
            "is_home": self.is_home,
            "last_seen": self.last_seen,
        }


@dataclass
class EnvironmentPreference:
    preference_id: str
    user_id: str
    room_id: Optional[str] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    brightness: Optional[int] = None
    color_temp: Optional[int] = None
    time_of_day: Optional[str] = None
    activity: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preference_id": self.preference_id,
            "user_id": self.user_id,
            "room_id": self.room_id,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "brightness": self.brightness,
            "color_temp": self.color_temp,
            "time_of_day": self.time_of_day,
            "activity": self.activity,
        }


@dataclass
class SchedulePreference:
    schedule_id: str
    user_id: str
    name: str
    start_time: str
    end_time: Optional[str] = None
    days: List[int] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "user_id": self.user_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "days": self.days,
            "actions": self.actions,
            "enabled": self.enabled,
        }


class UserPreferences:
    def __init__(self) -> None:
        self.users: Dict[str, UserProfile] = {}
        self.environment_prefs: Dict[str, EnvironmentPreference] = {}
        self.schedule_prefs: Dict[str, SchedulePreference] = {}
        self.global_defaults: Dict[str, Any] = {}

    def add_user(self, user: UserProfile) -> None:
        self.users[user.user_id] = user
        logger.info(f"Added user: {user.name} ({user.user_id})")

    def remove_user(self, user_id: str) -> None:
        if user_id in self.users:
            del self.users[user_id]
            logger.info(f"Removed user: {user_id}")

    def get_user(self, user_id: str) -> Optional[UserProfile]:
        return self.users.get(user_id)

    def find_user_by_voice_id(self, voice_id: str) -> Optional[UserProfile]:
        for user in self.users.values():
            if user.voice_id == voice_id:
                return user
        return None

    def find_user_by_face_id(self, face_id: str) -> Optional[UserProfile]:
        for user in self.users.values():
            if user.face_id == face_id:
                return user
        return None

    def get_users_at_home(self) -> List[UserProfile]:
        return [user for user in self.users.values() if user.is_home]

    def set_user_presence(self, user_id: str, is_home: bool, timestamp: Optional[float] = None) -> bool:
        user = self.users.get(user_id)
        if not user:
            return False
        user.is_home = is_home
        user.last_seen = timestamp
        return True

    def add_environment_preference(self, pref: EnvironmentPreference) -> None:
        self.environment_prefs[pref.preference_id] = pref

    def get_environment_preferences(self, user_id: str, room_id: Optional[str] = None) -> List[EnvironmentPreference]:
        result = []
        for pref in self.environment_prefs.values():
            if pref.user_id == user_id:
                if room_id is None or pref.room_id is None or pref.room_id == room_id:
                    result.append(pref)
        return result

    def find_matching_environment_preference(
        self, 
        user_id: str, 
        room_id: Optional[str] = None,
        time_of_day: Optional[str] = None,
        activity: Optional[str] = None
    ) -> Optional[EnvironmentPreference]:
        for pref in self.environment_prefs.values():
            if pref.user_id != user_id:
                continue
            if room_id and pref.room_id and pref.room_id != room_id:
                continue
            if time_of_day and pref.time_of_day and pref.time_of_day != time_of_day:
                continue
            if activity and pref.activity and pref.activity != activity:
                continue
            return pref
        return None

    def add_schedule_preference(self, schedule: SchedulePreference) -> None:
        self.schedule_prefs[schedule.schedule_id] = schedule

    def get_active_schedules(self, current_hour: int, current_minute: int, day_of_week: int) -> List[SchedulePreference]:
        current_time_minutes = current_hour * 60 + current_minute
        result = []
        for schedule in self.schedule_prefs.values():
            if not schedule.enabled:
                continue
            if schedule.days and day_of_week not in schedule.days:
                continue
            
            start_parts = schedule.start_time.split(":")
            start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
            
            if schedule.end_time:
                end_parts = schedule.end_time.split(":")
                end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])
                if not (start_minutes <= current_time_minutes <= end_minutes):
                    continue
            else:
                if current_time_minutes < start_minutes:
                    continue
            
            result.append(schedule)
        return result

    def set_global_default(self, key: str, value: Any) -> None:
        self.global_defaults[key] = value

    def get_global_default(self, key: str, default: Any = None) -> Any:
        return self.global_defaults.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "users": [user.to_dict() for user in self.users.values()],
            "environment_preferences": [pref.to_dict() for pref in self.environment_prefs.values()],
            "schedule_preferences": [sched.to_dict() for sched in self.schedule_prefs.values()],
            "global_defaults": self.global_defaults,
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"User preferences saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "UserPreferences":
        prefs = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for user_data in data.get("users", []):
            user = UserProfile(
                user_id=user_data["user_id"],
                name=user_data["name"],
                voice_id=user_data.get("voice_id"),
                face_id=user_data.get("face_id"),
                preferences=user_data.get("preferences", {}),
                routines=user_data.get("routines", {}),
                is_home=user_data.get("is_home", False),
                last_seen=user_data.get("last_seen"),
            )
            prefs.add_user(user)
        
        for env_data in data.get("environment_preferences", []):
            env_pref = EnvironmentPreference(
                preference_id=env_data["preference_id"],
                user_id=env_data["user_id"],
                room_id=env_data.get("room_id"),
                temperature=env_data.get("temperature"),
                humidity=env_data.get("humidity"),
                brightness=env_data.get("brightness"),
                color_temp=env_data.get("color_temp"),
                time_of_day=env_data.get("time_of_day"),
                activity=env_data.get("activity"),
            )
            prefs.add_environment_preference(env_pref)
        
        for sched_data in data.get("schedule_preferences", []):
            schedule = SchedulePreference(
                schedule_id=sched_data["schedule_id"],
                user_id=sched_data["user_id"],
                name=sched_data["name"],
                start_time=sched_data["start_time"],
                end_time=sched_data.get("end_time"),
                days=sched_data.get("days", []),
                actions=sched_data.get("actions", []),
                enabled=sched_data.get("enabled", True),
            )
            prefs.add_schedule_preference(schedule)
        
        prefs.global_defaults = data.get("global_defaults", {})
        logger.info(f"User preferences loaded from {filepath}")
        return prefs
