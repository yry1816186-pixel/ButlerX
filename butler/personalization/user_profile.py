from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class UserRole(Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
    CHILD = "child"


class UserStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"


@dataclass
class UserBehavior:
    behavior_type: str
    value: Any
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "behavior_type": self.behavior_type,
            "value": self.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "context": self.context,
            "metadata": self.metadata,
        }


@dataclass
class UserPattern:
    pattern_id: str
    pattern_type: str
    description: str
    data: Dict[str, Any] = field(default_factory=dict)
    frequency: int = 0
    last_observed: float = field(default_factory=time.time)
    confidence: float = 1.0
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "description": self.description,
            "data": self.data,
            "frequency": self.frequency,
            "last_observed": self.last_observed,
            "confidence": self.confidence,
            "enabled": self.enabled,
        }


class UserProfile:
    def __init__(
        self,
        user_id: str,
        name: str,
        role: UserRole = UserRole.USER,
    ):
        self.user_id = user_id
        self.name = name
        self.role = role
        self.status = UserStatus.ACTIVE

        self.email: Optional[str] = None
        self.phone: Optional[str] = None
        self.avatar: Optional[str] = None
        self.birthday: Optional[str] = None
        self.gender: Optional[str] = None

        self.preferences: Dict[str, Any] = {}
        self.behaviors: List[UserBehavior] = []
        self.patterns: Dict[str, UserPattern] = {}
        self.favorite_devices: Set[str] = set()
        self.favorite_scenarios: Set[str] = set()

        self.created_at: float = time.time()
        self.updated_at: float = time.time()
        self.last_seen: Optional[float] = None

        self.metadata: Dict[str, Any] = {}

    def update_behavior(self, behavior: UserBehavior) -> None:
        self.behaviors.append(behavior)

        if len(self.behaviors) > 1000:
            self.behaviors = self.behaviors[-1000:]

        self.updated_at = time.time()

        self._update_patterns(behavior)

    def _update_patterns(self, behavior: UserBehavior) -> None:
        pattern_id = f"{behavior.behavior_type}_{int(behavior.timestamp / 3600)}"

        if pattern_id not in self.patterns:
            self.patterns[pattern_id] = UserPattern(
                pattern_id=pattern_id,
                pattern_type=behavior.behavior_type,
                description=f"Pattern for {behavior.behavior_type}",
                data=behavior.context.copy(),
                frequency=1,
                last_observed=behavior.timestamp,
                confidence=behavior.confidence,
            )
        else:
            pattern = self.patterns[pattern_id]
            pattern.frequency += 1
            pattern.last_observed = behavior.timestamp
            pattern.confidence = min(1.0, pattern.confidence * 0.9 + behavior.confidence * 0.1)

    def get_behavior(
        self,
        behavior_type: str,
        limit: int = 10
    ) -> List[UserBehavior]:
        return [
            b for b in self.behaviors
            if b.behavior_type == behavior_type
        ][-limit:]

    def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.0
    ) -> List[UserPattern]:
        patterns = list(self.patterns.values())

        if pattern_type:
            patterns = [p for p in patterns if p.pattern_type == pattern_type]

        patterns = [p for p in patterns if p.confidence >= min_confidence]

        patterns.sort(key=lambda p: p.frequency, reverse=True)

        return patterns

    def get_prediction(
        self,
        behavior_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        recent_behaviors = self.get_behavior(behavior_type, limit=20)

        if not recent_behaviors:
            return None

        value_counts: Dict[Any, int] = {}
        for behavior in recent_behaviors:
            value = behavior.value
            value_counts[value] = value_counts.get(value, 0) + 1

        if not value_counts:
            return None

        most_common = max(value_counts.items(), key=lambda x: x[1])
        total = sum(value_counts.values())

        patterns = self.get_patterns(behavior_type)
        pattern_confidence = patterns[0].confidence if patterns else 0.5

        return {
            "predicted_value": most_common[0],
            "confidence": (most_common[1] / total) * pattern_confidence,
            "sample_size": len(recent_behaviors),
            "data_points": value_counts,
        }

    def add_favorite_device(self, device_id: str) -> None:
        self.favorite_devices.add(device_id)
        self.updated_at = time.time()

    def remove_favorite_device(self, device_id: str) -> None:
        self.favorite_devices.discard(device_id)
        self.updated_at = time.time()

    def add_favorite_scenario(self, scenario_id: str) -> None:
        self.favorite_scenarios.add(scenario_id)
        self.updated_at = time.time()

    def remove_favorite_scenario(self, scenario_id: str) -> None:
        self.favorite_scenarios.discard(scenario_id)
        self.updated_at = time.time()

    def set_preference(self, key: str, value: Any) -> None:
        self.preferences[key] = value
        self.updated_at = time.time()

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self.preferences.get(key, default)

    def remove_preference(self, key: str) -> bool:
        if key in self.preferences:
            del self.preferences[key]
            self.updated_at = time.time()
            return True
        return False

    def update_last_seen(self) -> None:
        self.last_seen = time.time()
        self.updated_at = time.time()

    def to_dict(self, include_behaviors: bool = False) -> Dict[str, Any]:
        result = {
            "user_id": self.user_id,
            "name": self.name,
            "role": self.role.value,
            "status": self.status.value,
            "email": self.email,
            "phone": self.phone,
            "avatar": self.avatar,
            "birthday": self.birthday,
            "gender": self.gender,
            "preferences": self.preferences,
            "favorite_devices": list(self.favorite_devices),
            "favorite_scenarios": list(self.favorite_scenarios),
            "patterns_count": len(self.patterns),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_seen": self.last_seen,
            "metadata": self.metadata,
        }

        if include_behaviors:
            result["behaviors"] = [b.to_dict() for b in self.behaviors[-50:]]
            result["patterns"] = [p.to_dict() for p in self.patterns.values()]

        return result


class UserProfileManager:
    def __init__(self):
        self.profiles: Dict[str, UserProfile] = {}
        self._active_user_id: Optional[str] = None
        self._listeners: List[Callable[[UserProfile, str], None]] = []

    def create_profile(
        self,
        user_id: str,
        name: str,
        role: UserRole = UserRole.USER,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> UserProfile:
        profile = UserProfile(user_id, name, role)
        profile.email = email
        profile.phone = phone

        self.profiles[user_id] = profile

        logger.info(f"Created user profile: {name} ({user_id})")
        return profile

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        return self.profiles.get(user_id)

    def get_profiles(self, role: Optional[UserRole] = None) -> List[UserProfile]:
        profiles = list(self.profiles.values())

        if role:
            profiles = [p for p in profiles if p.role == role]

        return profiles

    def update_profile(
        self,
        user_id: str,
        **kwargs
    ) -> bool:
        profile = self.profiles.get(user_id)
        if not profile:
            return False

        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
                profile.updated_at = time.time()

        self._notify_listeners(profile, "updated")
        logger.info(f"Updated user profile: {user_id}")
        return True

    def delete_profile(self, user_id: str) -> bool:
        if user_id not in self.profiles:
            return False

        profile = self.profiles[user_id]
        profile.status = UserStatus.DELETED

        if self._active_user_id == user_id:
            self._active_user_id = None

        self._notify_listeners(profile, "deleted")
        logger.info(f"Deleted user profile: {user_id}")
        return True

    def set_active_user(self, user_id: str) -> bool:
        if user_id not in self.profiles:
            return False

        self._active_user_id = user_id
        profile = self.profiles[user_id]
        profile.update_last_seen()

        self._notify_listeners(profile, "activated")
        logger.info(f"Active user set to: {user_id}")
        return True

    def get_active_user(self) -> Optional[UserProfile]:
        if self._active_user_id:
            return self.profiles.get(self._active_user_id)
        return None

    def add_listener(self, listener: Callable[[UserProfile, str], None]) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[UserProfile, str], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_listeners(self, profile: UserProfile, event: str) -> None:
        for listener in self._listeners:
            try:
                listener(profile, event)
            except Exception as e:
                logger.error(f"Error in user profile listener: {e}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profiles": [
                profile.to_dict(include_behaviors=False)
                for profile in self.profiles.values()
            ],
            "active_user_id": self._active_user_id,
            "profile_count": len(self.profiles),
        }

    def save_to_file(self, filepath: str) -> None:
        data = {
            "profiles": [
                profile.to_dict(include_behaviors=True)
                for profile in self.profiles.values()
            ],
            "active_user_id": self._active_user_id,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"User profiles saved to {filepath}")

    def load_from_file(self, filepath: str) -> None:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            for profile_data in data.get("profiles", []):
                user_id = profile_data["user_id"]
                name = profile_data["name"]
                role = UserRole(profile_data["role"])
                status = UserStatus(profile_data["status"])

                if status == UserStatus.DELETED:
                    continue

                profile = UserProfile(user_id, name, role)
                profile.status = status
                profile.email = profile_data.get("email")
                profile.phone = profile_data.get("phone")
                profile.avatar = profile_data.get("avatar")
                profile.birthday = profile_data.get("birthday")
                profile.gender = profile_data.get("gender")
                profile.preferences = profile_data.get("preferences", {})
                profile.favorite_devices = set(profile_data.get("favorite_devices", []))
                profile.favorite_scenarios = set(profile_data.get("favorite_scenarios", []))
                profile.created_at = profile_data.get("created_at", time.time())
                profile.updated_at = profile_data.get("updated_at", time.time())
                profile.last_seen = profile_data.get("last_seen")
                profile.metadata = profile_data.get("metadata", {})

                for behavior_data in profile_data.get("behaviors", []):
                    behavior = UserBehavior(
                        behavior_type=behavior_data["behavior_type"],
                        value=behavior_data["value"],
                        confidence=behavior_data.get("confidence", 1.0),
                        timestamp=behavior_data.get("timestamp", time.time()),
                        context=behavior_data.get("context", {}),
                        metadata=behavior_data.get("metadata", {}),
                    )
                    profile.behaviors.append(behavior)

                for pattern_data in profile_data.get("patterns", []):
                    pattern = UserPattern(
                        pattern_id=pattern_data["pattern_id"],
                        pattern_type=pattern_data["pattern_type"],
                        description=pattern_data["description"],
                        data=pattern_data.get("data", {}),
                        frequency=pattern_data.get("frequency", 0),
                        last_observed=pattern_data.get("last_observed", time.time()),
                        confidence=pattern_data.get("confidence", 1.0),
                        enabled=pattern_data.get("enabled", True),
                    )
                    profile.patterns[pattern.pattern_id] = pattern

                self.profiles[user_id] = profile

            self._active_user_id = data.get("active_user_id")

            logger.info(f"User profiles loaded from {filepath}")
        except Exception as e:
            logger.error(f"Error loading user profiles from {filepath}: {e}")
