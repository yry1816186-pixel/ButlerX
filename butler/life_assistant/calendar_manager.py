from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass
class CalendarEvent:
    id: str
    title: str
    description: str
    start_time: int
    end_time: int
    priority: int
    location: Optional[str] = None
    reminder_sent: bool = False
    created_at: int = 0
    tags: List[str] = None

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []
        if self.created_at == 0:
            from ..core.utils import utc_ts
            self.created_at = utc_ts()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalendarEvent":
        return cls(**data)


class CalendarManager:
    def __init__(self, storage_path: Optional[str] = None) -> None:
        self.storage_path = storage_path or "/app/butler/data/calendar.json"
        self.events: Dict[str, CalendarEvent] = {}
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        try:
            path = Path(self.storage_path)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for event_id, event_data in data.items():
                        self.events[event_id] = CalendarEvent.from_dict(event_data)
                logger.info(f"Loaded {len(self.events)} calendar events")
        except Exception as e:
            logger.error(f"Failed to load calendar events: {e}")

    def _save_to_disk(self) -> None:
        try:
            path = Path(self.storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                data = {event_id: event.to_dict() for event_id, event in self.events.items()}
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save calendar events: {e}")

    def add_event(
        self,
        title: str,
        description: str,
        start_time: int,
        end_time: int,
        priority: int = Priority.MEDIUM.value,
        location: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> CalendarEvent:
        from ..core.utils import new_uuid, utc_ts
        event_id = new_uuid()
        event = CalendarEvent(
            id=event_id,
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            priority=priority,
            location=location,
            tags=tags or [],
            created_at=utc_ts(),
        )
        self.events[event_id] = event
        self._save_to_disk()
        logger.info(f"Added calendar event: {title}")
        return event

    def update_event(
        self,
        event_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        priority: Optional[int] = None,
        location: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[CalendarEvent]:
        if event_id not in self.events:
            return None
        event = self.events[event_id]
        if title is not None:
            event.title = title
        if description is not None:
            event.description = description
        if start_time is not None:
            event.start_time = start_time
        if end_time is not None:
            event.end_time = end_time
        if priority is not None:
            event.priority = priority
        if location is not None:
            event.location = location
        if tags is not None:
            event.tags = tags
        self._save_to_disk()
        logger.info(f"Updated calendar event: {event.title}")
        return event

    def delete_event(self, event_id: str) -> bool:
        if event_id in self.events:
            title = self.events[event_id].title
            del self.events[event_id]
            self._save_to_disk()
            logger.info(f"Deleted calendar event: {title}")
            return True
        return False

    def get_event(self, event_id: str) -> Optional[CalendarEvent]:
        return self.events.get(event_id)

    def get_upcoming_events(self, hours_ahead: int = 24, limit: int = 10) -> List[CalendarEvent]:
        from ..core.utils import utc_ts
        now = utc_ts()
        future = now + (hours_ahead * 3600)
        events = [
            event for event in self.events.values()
            if now <= event.start_time < future
        ]
        events.sort(key=lambda e: (e.start_time, -e.priority))
        return events[:limit]

    def get_events_for_date(self, date_str: str) -> List[CalendarEvent]:
        from ..core.utils import utc_ts
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return []
        start_of_day = int(date.timestamp())
        start_of_next_day = int((date + timedelta(days=1)).timestamp())
        events = [
            event for event in self.events.values()
            if start_of_day <= event.start_time < start_of_next_day
        ]
        events.sort(key=lambda e: e.start_time)
        return events

    def get_events_by_tag(self, tag: str) -> List[CalendarEvent]:
        events = [
            event for event in self.events.values()
            if tag in event.tags
        ]
        events.sort(key=lambda e: e.start_time)
        return events

    def get_reminder_events(self) -> List[CalendarEvent]:
        from ..core.utils import utc_ts
        now = utc_ts()
        reminder_window = 3600
        events = [
            event for event in self.events.values()
            if not event.reminder_sent and
               now <= event.start_time <= now + reminder_window
        ]
        return events

    def mark_reminder_sent(self, event_id: str) -> bool:
        if event_id in self.events:
            self.events[event_id].reminder_sent = True
            self._save_to_disk()
            return True
        return False

    def list_all_events(self) -> List[CalendarEvent]:
        events = list(self.events.values())
        events.sort(key=lambda e: e.start_time)
        return events

    def search_events(self, query: str) -> List[CalendarEvent]:
        query_lower = query.lower()
        events = [
            event for event in self.events.values()
            if query_lower in event.title.lower() or
               query_lower in event.description.lower() or
               any(query_lower in tag.lower() for tag in event.tags)
        ]
        events.sort(key=lambda e: e.start_time)
        return events
