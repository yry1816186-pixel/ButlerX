from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Callable
from datetime import datetime
import json
import asyncio
from collections import deque

class EntityType(Enum):
    DEVICE = "device"
    SENSOR = "sensor"
    USER = "user"
    LOCATION = "location"
    SERVICE = "service"
    AUTOMATION = "automation"
    SCENARIO = "scenario"

class EntityDomain(Enum):
    LIGHT = "light"
    SWITCH = "switch"
    CLIMATE = "climate"
    COVER = "cover"
    MEDIA_PLAYER = "media_player"
    CAMERA = "camera"
    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    LOCK = "lock"
    VACUUM = "vacuum"
    PERSON = "person"
    ZONE = "zone"
    SCRIPT = "script"
    AUTOMATION = "automation"
    SCENARIO = "scenario"

class EntityState(Enum):
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    OFF = "off"
    ON = "on"
    IDLE = "idle"
    ACTIVE = "active"
    OPEN = "open"
    CLOSED = "closed"
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    PLAYING = "playing"
    PAUSED = "paused"
    HOME = "home"
    NOT_HOME = "not_home"
    DETECTED = "detected"
    CLEAR = "clear"

class EntityStatus(Enum):
    CREATED = "created"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNAVAILABLE = "unavailable"
    DELETED = "deleted"

@dataclass
class EntityStateHistory:
    state: str
    attributes: Dict[str, Any]
    timestamp: datetime
    last_changed: datetime
    last_updated: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "attributes": self.attributes,
            "timestamp": self.timestamp.isoformat(),
            "last_changed": self.last_changed.isoformat(),
            "last_updated": self.last_updated.isoformat()
        }

@dataclass
class EntityCapability:
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    supported_values: Optional[List[Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "supported_values": self.supported_values
        }

@dataclass
class EntityAttribute:
    name: str
    value: Any
    unit: Optional[str] = None
    device_class: Optional[str] = None
    state_class: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "device_class": self.device_class,
            "state_class": self.state_class
        }

class Entity:
    _registry: Dict[str, Entity] = {}
    _by_type: Dict[EntityType, Set[str]] = {t: set() for t in EntityType}
    _by_domain: Dict[EntityDomain, Set[str]] = {d: set() for d in EntityDomain}
    _by_location: Dict[str, Set[str]] = {}
    _change_listeners: List[Callable[[Entity], None]] = []

    def __init__(
        self,
        entity_id: str,
        name: str,
        entity_type: EntityType,
        domain: EntityDomain,
        location: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        capabilities: Optional[List[EntityCapability]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.entity_id = entity_id
        self.name = name
        self.entity_type = entity_type
        self.domain = domain
        self.location = location
        self.attributes = attributes or {}
        self.capabilities = capabilities or []
        self.metadata = metadata or {}
        
        self._state = EntityState.UNKNOWN.value
        self._status = EntityStatus.CREATED
        self._created_at = datetime.now()
        self._last_changed = datetime.now()
        self._last_updated = datetime.now()
        self._history: deque = deque(maxlen=100)
        self._state_callbacks: List[Callable[[str, str], None]] = []

    @property
    def state(self) -> str:
        return self._state

    @state.setter
    def state(self, value: str):
        old_state = self._state
        self._state = value
        now = datetime.now()
        
        if old_state != value:
            self._last_changed = now
            self._add_history(value)
            for callback in self._state_callbacks:
                try:
                    callback(old_state, value)
                except (RuntimeError, ValueError, TypeError):
                    pass
        
        self._last_updated = now
        self._notify_listeners()

    @property
    def status(self) -> EntityStatus:
        return self._status

    @status.setter
    def status(self, value: EntityStatus):
        self._status = value
        self._notify_listeners()

    @property
    def last_changed(self) -> datetime:
        return self._last_changed

    @property
    def last_updated(self) -> datetime:
        return self._last_updated

    @property
    def age(self) -> float:
        return (datetime.now() - self._created_at).total_seconds()

    @property
    def available(self) -> bool:
        return self._status in [EntityStatus.INITIALIZED, EntityStatus.ACTIVE]

    def register(self):
        if self.entity_id in Entity._registry:
            raise ValueError(f"Entity {self.entity_id} already registered")
        
        Entity._registry[self.entity_id] = self
        Entity._by_type[self.entity_type].add(self.entity_id)
        Entity._by_domain[self.domain].add(self.entity_id)
        
        if self.location:
            if self.location not in Entity._by_location:
                Entity._by_location[self.location] = set()
            Entity._by_location[self.location].add(self.entity_id)
        
        self.status = EntityStatus.INITIALIZED

    def unregister(self):
        if self.entity_id not in Entity._registry:
            return
        
        del Entity._registry[self.entity_id]
        Entity._by_type[self.entity_type].discard(self.entity_id)
        Entity._by_domain[self.domain].discard(self.entity_id)
        
        if self.location and self.location in Entity._by_location:
            Entity._by_location[self.location].discard(self.entity_id)
        
        self.status = EntityStatus.DELETED

    def initialize(self):
        self.status = EntityStatus.ACTIVE

    def set_unavailable(self):
        self.status = EntityStatus.UNAVAILABLE

    def update_attributes(self, attributes: Dict[str, Any]):
        old_attrs = self.attributes.copy()
        self.attributes.update(attributes)
        if old_attrs != self.attributes:
            self._last_updated = datetime.now()
        self._notify_listeners()

    def add_capability(self, capability: EntityCapability):
        if capability not in self.capabilities:
            self.capabilities.append(capability)

    def remove_capability(self, capability_name: str):
        self.capabilities = [c for c in self.capabilities if c.name != capability_name]

    def has_capability(self, capability_name: str) -> bool:
        return any(c.name == capability_name for c in self.capabilities)

    def get_capability(self, capability_name: str) -> Optional[EntityCapability]:
        for cap in self.capabilities:
            if cap.name == capability_name:
                return cap
        return None

    def add_state_callback(self, callback: Callable[[str, str], None]):
        if callback not in self._state_callbacks:
            self._state_callbacks.append(callback)

    def remove_state_callback(self, callback: Callable[[str, str], None]):
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)

    def get_history(self, limit: int = 10) -> List[EntityStateHistory]:
        return list(self._history)[-limit:]

    def _add_history(self, state: str):
        history = EntityStateHistory(
            state=state,
            attributes=self.attributes.copy(),
            timestamp=datetime.now(),
            last_changed=self._last_changed,
            last_updated=self._last_updated
        )
        self._history.append(history)

    def _notify_listeners(self):
        for listener in Entity._change_listeners:
            try:
                listener(self)
            except Exception as e:
                pass

    def to_dict(self, include_history: bool = False) -> Dict[str, Any]:
        data = {
            "entity_id": self.entity_id,
            "name": self.name,
            "entity_type": self.entity_type.value,
            "domain": self.domain.value,
            "location": self.location,
            "state": self.state,
            "status": self.status.value,
            "attributes": self.attributes,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "metadata": self.metadata,
            "created_at": self._created_at.isoformat(),
            "last_changed": self._last_changed.isoformat(),
            "last_updated": self._last_updated.isoformat(),
            "age": self.age,
            "available": self.available
        }
        
        if include_history:
            data["history"] = [h.to_dict() for h in self.get_history()]
        
        return data

    def to_json(self, include_history: bool = False) -> str:
        return json.dumps(self.to_dict(include_history), ensure_ascii=False, indent=2)

    @classmethod
    def get(cls, entity_id: str) -> Optional[Entity]:
        return cls._registry.get(entity_id)

    @classmethod
    def get_all(cls) -> List[Entity]:
        return list(cls._registry.values())

    @classmethod
    def get_by_type(cls, entity_type: EntityType) -> List[Entity]:
        return [cls._registry[eid] for eid in cls._by_type[entity_type] if eid in cls._registry]

    @classmethod
    def get_by_domain(cls, domain: EntityDomain) -> List[Entity]:
        return [cls._registry[eid] for eid in cls._by_domain[domain] if eid in cls._registry]

    @classmethod
    def get_by_location(cls, location: str) -> List[Entity]:
        if location not in cls._by_location:
            return []
        return [cls._registry[eid] for eid in cls._by_location[location] if eid in cls._registry]

    @classmethod
    def search(cls, **filters) -> List[Entity]:
        results = list(cls._registry.values())
        
        for key, value in filters.items():
            if key == "entity_type" and isinstance(value, EntityType):
                results = [e for e in results if e.entity_type == value]
            elif key == "domain" and isinstance(value, EntityDomain):
                results = [e for e in results if e.domain == value]
            elif key == "location" and isinstance(value, str):
                results = [e for e in results if e.location == value]
            elif key == "state" and isinstance(value, str):
                results = [e for e in results if e.state == value]
            elif key == "available" and isinstance(value, bool):
                results = [e for e in results if e.available == value]
            elif key in ["name", "entity_id"] and isinstance(value, str):
                results = [e for e in results if value.lower() in getattr(e, key).lower()]
            elif hasattr(results[0], key) if results else False:
                results = [e for e in results if getattr(e, key) == value]
        
        return results

    @classmethod
    def register_change_listener(cls, listener: Callable[[Entity], None]):
        if listener not in cls._change_listeners:
            cls._change_listeners.append(listener)

    @classmethod
    def unregister_change_listener(cls, listener: Callable[[Entity], None]):
        if listener in cls._change_listeners:
            cls._change_listeners.remove(listener)

    @classmethod
    def clear_registry(cls):
        cls._registry.clear()
        for t in cls._by_type:
            cls._by_type[t].clear()
        for d in cls._by_domain:
            cls._by_domain[d].clear()
        for loc in cls._by_location:
            cls._by_location[loc].clear()
        cls._by_location.clear()
        cls._change_listeners.clear()

    @classmethod
    def get_statistics(cls) -> Dict[str, Any]:
        return {
            "total_entities": len(cls._registry),
            "by_type": {t.value: len(cls._by_type[t]) for t in EntityType},
            "by_domain": {d.value: len(cls._by_domain[d]) for d in EntityDomain},
            "by_location": {loc: len(eids) for loc, eids in cls._by_location.items()},
            "available": sum(1 for e in cls._registry.values() if e.available),
            "unavailable": sum(1 for e in cls._registry.values() if not e.available)
        }

class Device(Entity):
    def __init__(
        self,
        entity_id: str,
        name: str,
        domain: EntityDomain,
        manufacturer: Optional[str] = None,
        model: Optional[str] = None,
        sw_version: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            entity_id=entity_id,
            name=name,
            entity_type=EntityType.DEVICE,
            domain=domain,
            **kwargs
        )
        self.manufacturer = manufacturer
        self.model = model
        self.sw_version = sw_version
        self._last_command: Optional[str] = None
        self._command_history: deque = deque(maxlen=50)

    async def call_service(self, service: str, **kwargs) -> bool:
        raise NotImplementedError

    def record_command(self, service: str, params: Dict[str, Any]):
        self._last_command = service
        self._command_history.append({
            "service": service,
            "params": params,
            "timestamp": datetime.now().isoformat()
        })

class Sensor(Entity):
    def __init__(
        self,
        entity_id: str,
        name: str,
        domain: EntityDomain,
        unit_of_measurement: Optional[str] = None,
        device_class: Optional[str] = None,
        state_class: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            entity_id=entity_id,
            name=name,
            entity_type=EntityType.SENSOR,
            domain=domain,
            **kwargs
        )
        self.unit_of_measurement = unit_of_measurement
        self.device_class = device_class
        self.state_class = state_class

    def set_state(self, value: Any):
        self.state = str(value)
        if self.unit_of_measurement:
            self.attributes["unit_of_measurement"] = self.unit_of_measurement
        if self.device_class:
            self.attributes["device_class"] = self.device_class
        if self.state_class:
            self.attributes["state_class"] = self.state_class

class User(Entity):
    def __init__(
        self,
        entity_id: str,
        name: str,
        user_id: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            entity_id=entity_id,
            name=name,
            entity_type=EntityType.USER,
            domain=EntityDomain.PERSON,
            **kwargs
        )
        self.user_id = user_id
        self.email = email
        self.phone = phone
        self.preferences: Dict[str, Any] = {}
        self.activities: List[Dict[str, Any]] = []

    def set_home(self):
        self.state = EntityState.HOME.value
        self.attributes["location"] = "home"

    def set_away(self):
        self.state = EntityState.NOT_HOME.value
        self.attributes["location"] = "not_home"

    def update_preference(self, key: str, value: Any):
        self.preferences[key] = value
        self.attributes["preferences"] = self.preferences

    def record_activity(self, activity_type: str, details: Optional[Dict[str, Any]] = None):
        self.activities.append({
            "type": activity_type,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        })

class Location(Entity):
    def __init__(
        self,
        entity_id: str,
        name: str,
        location_type: str,
        parent: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            entity_id=entity_id,
            name=name,
            entity_type=EntityType.LOCATION,
            domain=EntityDomain.ZONE,
            **kwargs
        )
        self.location_type = location_type
        self.parent = parent
        self.sub_locations: List[str] = []

    def add_sub_location(self, location_id: str):
        if location_id not in self.sub_locations:
            self.sub_locations.append(location_id)

    def remove_sub_location(self, location_id: str):
        if location_id in self.sub_locations:
            self.sub_locations.remove(location_id)

class Service(Entity):
    def __init__(
        self,
        entity_id: str,
        name: str,
        service_name: str,
        target_domain: EntityDomain,
        **kwargs
    ):
        super().__init__(
            entity_id=entity_id,
            name=name,
            entity_type=EntityType.SERVICE,
            domain=EntityDomain.SCRIPT,
            **kwargs
        )
        self.service_name = service_name
        self.target_domain = target_domain

class Automation(Entity):
    def __init__(
        self,
        entity_id: str,
        name: str,
        triggers: List[Dict[str, Any]],
        conditions: List[Dict[str, Any]],
        actions: List[Dict[str, Any]],
        **kwargs
    ):
        super().__init__(
            entity_id=entity_id,
            name=name,
            entity_type=EntityType.AUTOMATION,
            domain=EntityDomain.AUTOMATION,
            **kwargs
        )
        self.triggers = triggers
        self.conditions = conditions
        self.actions = actions
        self._enabled = True
        self._last_triggered: Optional[datetime] = None
        self._trigger_count = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self):
        self._enabled = True
        self.status = EntityStatus.ACTIVE

    def disable(self):
        self._enabled = False
        self.status = EntityStatus.INACTIVE

    def trigger(self):
        if not self._enabled:
            return False
        
        self._last_triggered = datetime.now()
        self._trigger_count += 1
        self.attributes["last_triggered"] = self._last_triggered.isoformat()
        self.attributes["trigger_count"] = self._trigger_count
        self.state = EntityState.ACTIVE.value
        
        return True

class Scenario(Entity):
    def __init__(
        self,
        entity_id: str,
        name: str,
        description: str,
        actions: List[Dict[str, Any]],
        icon: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            entity_id=entity_id,
            name=name,
            entity_type=EntityType.SCENARIO,
            domain=EntityDomain.SCRIPT,
            **kwargs
        )
        self.description = description
        self.actions = actions
        self.icon = icon
        self._execution_count = 0

    async def execute(self) -> bool:
        raise NotImplementedError

    def increment_execution(self):
        self._execution_count += 1
        self.attributes["execution_count"] = self._execution_count
