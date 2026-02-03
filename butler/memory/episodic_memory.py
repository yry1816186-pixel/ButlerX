from __future__ import annotations
import asyncio
import logging
import json
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from .long_term_memory import LongTermMemory
from .memory_types import MemoryItem, MemoryType

logger = logging.getLogger(__name__)

@dataclass
class Event:
    event_id: str
    event_type: str
    description: str
    timestamp: datetime = field(default_factory=datetime.now)
    participants: List[str] = field(default_factory=list)
    location: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
            "participants": self.participants,
            "location": self.location,
            "context": self.context,
            "importance": self.importance,
            "metadata": self.metadata
        }

@dataclass
class Episode:
    episode_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    participants: List[str] = field(default_factory=list)
    location: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "events": self.events,
            "participants": self.participants,
            "location": self.location,
            "context": self.context,
            "importance": self.importance,
            "tags": self.tags
        }

    def add_event(self, event):
        self.events.append(event.to_dict() if hasattr(event, 'to_dict') else event)

class EpisodicMemory(LongTermMemory):
    def __init__(self, storage_path: Optional[str] = None):
        super().__init__(storage_path)
        self._episodes: Dict[str, Episode] = {}
        self._episodes_by_date: Dict[str, List[str]] = {}
        self._episodes_by_participant: Dict[str, List[str]] = {}

    async def initialize(self) -> bool:
        if not await super().initialize():
            return False

        episodes_file = os.path.join(self._storage_path, "episodes.json")
        if os.path.exists(episodes_file):
            try:
                with open(episodes_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for episode_data in data.get("episodes", []):
                        episode = Episode(
                            episode_id=episode_data["episode_id"],
                            start_time=datetime.fromisoformat(episode_data["start_time"]),
                            end_time=datetime.fromisoformat(episode_data["end_time"]) if episode_data.get("end_time") else None,
                            events=episode_data.get("events", []),
                            participants=episode_data.get("participants", []),
                            location=episode_data.get("location"),
                            context=episode_data.get("context", {}),
                            importance=episode_data.get("importance", 0.5),
                            tags=episode_data.get("tags", [])
                        )
                        self._episodes[episode.episode_id] = episode
                        self._index_episode(episode)

                logger.info(f"Loaded {len(self._episodes)} episodes")

            except Exception as e:
                logger.error(f"Failed to load episodes: {e}")

        return True

    async def add_episode(self, episode: Episode) -> str:
        import uuid

        if not episode.episode_id:
            episode.episode_id = str(uuid.uuid4())

        self._episodes[episode.episode_id] = episode
        self._index_episode(episode)
        await self._save_episodes()

        return episode.episode_id

    def _index_episode(self, episode: Episode):
        date_key = episode.start_time.strftime("%Y-%m-%d")
        if date_key not in self._episodes_by_date:
            self._episodes_by_date[date_key] = []
        self._episodes_by_date[date_key].append(episode.episode_id)

        for participant in episode.participants:
            if participant not in self._episodes_by_participant:
                self._episodes_by_participant[participant] = []
            self._episodes_by_participant[participant].append(episode.episode_id)

    async def get_episode(self, episode_id: str) -> Optional[Episode]:
        return self._episodes.get(episode_id)

    async def get_episodes_by_date(
        self,
        date: datetime,
        include_adjacent: bool = False
    ) -> List[Episode]:
        date_key = date.strftime("%Y-%m-%d")
        episode_ids = self._episodes_by_date.get(date_key, [])

        if include_adjacent:
            from datetime import timedelta
            prev_day = (date - timedelta(days=1)).strftime("%Y-%m-%d")
            next_day = (date + timedelta(days=1)).strftime("%Y-%m-%d")
            episode_ids.extend(self._episodes_by_date.get(prev_day, []))
            episode_ids.extend(self._episodes_by_date.get(next_day, []))

        return [self._episodes[eid] for eid in episode_ids if eid in self._episodes]

    async def get_episodes_by_participant(
        self,
        participant: str,
        limit: int = 20
    ) -> List[Episode]:
        episode_ids = self._episodes_by_participant.get(participant, [])
        episodes = [self._episodes[eid] for eid in episode_ids if eid in self._episodes]
        episodes.sort(key=lambda e: e.start_time, reverse=True)
        return episodes[:limit]

    async def get_recent_episodes(
        self,
        hours: int = 24,
        limit: int = 50
    ) -> List[Episode]:
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=hours)

        episodes = [
            e for e in self._episodes.values()
            if e.start_time >= cutoff
        ]
        episodes.sort(key=lambda e: e.start_time, reverse=True)
        return episodes[:limit]

    async def search_episodes(
        self,
        keywords: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Episode]:
        results = []

        for episode in self._episodes.values():
            if start_date and episode.start_time < start_date:
                continue
            if end_date and episode.start_time > end_date:
                continue

            episode_text = " ".join([
                " ".join(e.values()) if isinstance(e, dict) else str(e)
                for e in episode.events
            ]).lower()

            if any(kw.lower() in episode_text for kw in keywords):
                results.append(episode)

        results.sort(key=lambda e: e.importance, reverse=True)
        return results[:limit]

    async def add_event_to_episode(
        self,
        episode_id: str,
        event: Dict[str, Any]
    ) -> bool:
        episode = self._episodes.get(episode_id)
        if not episode:
            return False

        episode.events.append(event)
        await self._save_episodes()
        return True

    async def end_episode(
        self,
        episode_id: str,
        end_time: Optional[datetime] = None
    ) -> bool:
        episode = self._episodes.get(episode_id)
        if not episode:
            return False

        episode.end_time = end_time or datetime.now()
        await self._save_episodes()
        return True

    async def add(self, item: MemoryItem):
        await super().add(item)

    async def query(self, query: Any) -> List[Any]:
        return await super().query(query)

    async def _save_episodes(self):
        try:
            episodes_file = os.path.join(self._storage_path, "episodes.json")
            data = {
                "episodes": [e.to_dict() for e in self._episodes.values()],
                "saved_at": datetime.now().isoformat()
            }

            with open(episodes_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to save episodes: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        base_stats = super().get_statistics()
        base_stats.update({
            "total_episodes": len(self._episodes),
            "total_events": sum(len(e.events) for e in self._episodes.values()),
            "unique_participants": len(self._episodes_by_participant),
            "date_range_days": len(self._episodes_by_date)
        })
        return base_stats
