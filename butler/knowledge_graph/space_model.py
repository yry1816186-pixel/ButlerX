from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class SpaceType(Enum):
    ROOM = "room"
    ZONE = "zone"
    AREA = "area"


@dataclass
class Room:
    room_id: str
    name: str
    room_type: str
    zone_id: Optional[str] = None
    area_id: Optional[str] = None
    devices: Set[str] = field(default_factory=set)
    properties: Dict[str, Any] = field(default_factory=dict)

    def add_device(self, device_id: str) -> None:
        self.devices.add(device_id)

    def remove_device(self, device_id: str) -> None:
        self.devices.discard(device_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "room_id": self.room_id,
            "name": self.name,
            "room_type": self.room_type,
            "zone_id": self.zone_id,
            "area_id": self.area_id,
            "devices": list(self.devices),
            "properties": self.properties,
        }


@dataclass
class Zone:
    zone_id: str
    name: str
    area_id: Optional[str] = None
    rooms: Set[str] = field(default_factory=set)
    devices: Set[str] = field(default_factory=set)
    properties: Dict[str, Any] = field(default_factory=dict)

    def add_room(self, room_id: str) -> None:
        self.rooms.add(room_id)

    def remove_room(self, room_id: str) -> None:
        self.rooms.discard(room_id)

    def add_device(self, device_id: str) -> None:
        self.devices.add(device_id)

    def remove_device(self, device_id: str) -> None:
        self.devices.discard(device_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "area_id": self.area_id,
            "rooms": list(self.rooms),
            "devices": list(self.devices),
            "properties": self.properties,
        }


@dataclass
class Area:
    area_id: str
    name: str
    zones: Set[str] = field(default_factory=set)
    devices: Set[str] = field(default_factory=set)
    properties: Dict[str, Any] = field(default_factory=dict)

    def add_zone(self, zone_id: str) -> None:
        self.zones.add(zone_id)

    def remove_zone(self, zone_id: str) -> None:
        self.zones.discard(zone_id)

    def add_device(self, device_id: str) -> None:
        self.devices.add(device_id)

    def remove_device(self, device_id: str) -> None:
        self.devices.discard(device_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "area_id": self.area_id,
            "name": self.name,
            "zones": list(self.zones),
            "devices": list(self.devices),
            "properties": self.properties,
        }


class SpaceModel:
    def __init__(self) -> None:
        self.areas: Dict[str, Area] = {}
        self.zones: Dict[str, Zone] = {}
        self.rooms: Dict[str, Room] = {}

    def add_area(self, area: Area) -> None:
        self.areas[area.area_id] = area
        logger.info(f"Added area: {area.name} ({area.area_id})")

    def add_zone(self, zone: Zone) -> None:
        self.zones[zone.zone_id] = zone
        if zone.area_id and zone.area_id in self.areas:
            self.areas[zone.area_id].add_zone(zone.zone_id)
        logger.info(f"Added zone: {zone.name} ({zone.zone_id})")

    def add_room(self, room: Room) -> None:
        self.rooms[room.room_id] = room
        if room.zone_id and room.zone_id in self.zones:
            self.zones[room.zone_id].add_room(room.room_id)
        logger.info(f"Added room: {room.name} ({room.room_id})")

    def get_room(self, room_id: str) -> Optional[Room]:
        return self.rooms.get(room_id)

    def get_zone(self, zone_id: str) -> Optional[Zone]:
        return self.zones.get(zone_id)

    def get_area(self, area_id: str) -> Optional[Area]:
        return self.areas.get(area_id)

    def find_rooms_by_type(self, room_type: str) -> List[Room]:
        return [room for room in self.rooms.values() if room.room_type == room_type]

    def find_devices_in_room(self, room_id: str) -> Set[str]:
        room = self.rooms.get(room_id)
        if not room:
            return set()
        return room.devices.copy()

    def find_devices_in_zone(self, zone_id: str) -> Set[str]:
        zone = self.zones.get(zone_id)
        if not zone:
            return set()
        devices = zone.devices.copy()
        for room_id in zone.rooms:
            room = self.rooms.get(room_id)
            if room:
                devices.update(room.devices)
        return devices

    def find_devices_in_area(self, area_id: str) -> Set[str]:
        area = self.areas.get(area_id)
        if not area:
            return set()
        devices = area.devices.copy()
        for zone_id in area.zones:
            devices.update(self.find_devices_in_zone(zone_id))
        return devices

    def get_parent_zone(self, room_id: str) -> Optional[Zone]:
        room = self.rooms.get(room_id)
        if not room or not room.zone_id:
            return None
        return self.zones.get(room.zone_id)

    def get_parent_area(self, room_id: str) -> Optional[Area]:
        room = self.rooms.get(room_id)
        if not room or not room.zone_id:
            return None
        zone = self.zones.get(room.zone_id)
        if not zone or not zone.area_id:
            return None
        return self.areas.get(zone.area_id)

    def get_all_devices(self) -> Set[str]:
        devices = set()
        for area in self.areas.values():
            devices.update(area.devices)
        for zone in self.zones.values():
            devices.update(zone.devices)
        for room in self.rooms.values():
            devices.update(room.devices)
        return devices

    def to_dict(self) -> Dict[str, Any]:
        return {
            "areas": [area.to_dict() for area in self.areas.values()],
            "zones": [zone.to_dict() for zone in self.zones.values()],
            "rooms": [room.to_dict() for room in self.rooms.values()],
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Space model saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "SpaceModel":
        model = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for area_data in data.get("areas", []):
            area = Area(
                area_id=area_data["area_id"],
                name=area_data["name"],
                devices=set(area_data.get("devices", [])),
                properties=area_data.get("properties", {}),
            )
            model.add_area(area)
        
        for zone_data in data.get("zones", []):
            zone = Zone(
                zone_id=zone_data["zone_id"],
                name=zone_data["name"],
                area_id=zone_data.get("area_id"),
                devices=set(zone_data.get("devices", [])),
                properties=zone_data.get("properties", {}),
            )
            model.add_zone(zone)
        
        for room_data in data.get("rooms", []):
            room = Room(
                room_id=room_data["room_id"],
                name=room_data["name"],
                room_type=room_data["room_type"],
                zone_id=room_data.get("zone_id"),
                area_id=room_data.get("area_id"),
                devices=set(room_data.get("devices", [])),
                properties=room_data.get("properties", {}),
            )
            model.add_room(room)
        
        logger.info(f"Space model loaded from {filepath}")
        return model
