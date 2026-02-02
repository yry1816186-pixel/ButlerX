from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.utils import utc_ts

logger = logging.getLogger(__name__)


@dataclass
class Habit:
    habit_id: str
    name: str
    description: str
    pattern_type: str
    pattern_data: Dict[str, Any]
    confidence: float
    occurrences: int
    last_occurrence: float
    suggested_actions: List[Dict[str, Any]] = field(default_factory=list)
    enabled: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "habit_id": self.habit_id,
            "name": self.name,
            "description": self.description,
            "pattern_type": self.pattern_type,
            "pattern_data": self.pattern_data,
            "confidence": self.confidence,
            "occurrences": self.occurrences,
            "last_occurrence": self.last_occurrence,
            "suggested_actions": self.suggested_actions,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


class HabitLearner:
    def __init__(self) -> None:
        self.habits: Dict[str, Habit] = {}
        self.action_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000
        self.min_occurrences = 3
        self.min_confidence = 0.7

    def record_action(
        self,
        action_type: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        context = context or {}
        record = {
            "timestamp": utc_ts(),  # 使用统一的时间戳格式（秒）
            "action_type": action_type,
            "params": params,
            "context": context,
        }
        self.action_history.append(record)

        if len(self.action_history) > self.max_history_size:
            self.action_history = self.action_history[-self.max_history_size:]

        self._analyze_patterns()

    def _analyze_patterns(self) -> None:
        time_patterns = defaultdict(list)
        device_patterns = defaultdict(list)
        sequence_patterns = defaultdict(list)

        for record in self.action_history:
            dt = datetime.fromtimestamp(record["timestamp"])
            hour = dt.hour
            day_of_week = dt.weekday()

            time_key = f"{day_of_week}_{hour}"
            time_patterns[time_key].append(record)

            device = record["params"].get("target", "unknown")
            device_patterns[device].append(record)

            if len(self.action_history) > 1:
                last_idx = self.action_history.index(record) - 1
                if last_idx >= 0:
                    last_action = self.action_history[last_idx]
                    seq_key = f"{last_action['action_type']}_{record['action_type']}"
                    sequence_patterns[seq_key].append(record)

        self._update_time_habits(time_patterns)
        self._update_device_habits(device_patterns)
        self._update_sequence_habits(sequence_patterns)

    def _update_time_habits(self, time_patterns: Dict[str, List[Dict[str, Any]]]) -> None:
        for time_key, records in time_patterns.items():
            if len(records) < self.min_occurrences:
                continue

            day_of_week, hour = map(int, time_key.split("_"))
            day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            day_name = day_names[day_of_week]

            action_counts = defaultdict(int)
            for record in records:
                action_counts[record["action_type"]] += 1

            most_common_action = max(action_counts.items(), key=lambda x: x[1])
            confidence = most_common_action[1] / len(records)

            if confidence >= self.min_confidence:
                habit_id = f"habit_time_{time_key}"
                habit_name = f"{day_name} {hour}点习惯"
                description = f"在{day_name}的{hour}点，经常执行{most_common_action[0]}操作"

                if habit_id in self.habits:
                    self.habits[habit_id].occurrences = len(records)
                    self.habits[habit_id].confidence = confidence
                    self.habits[habit_id].last_occurrence = records[-1]["timestamp"]
                else:
                    habit = Habit(
                        habit_id=habit_id,
                        name=habit_name,
                        description=description,
                        pattern_type="time",
                        pattern_data={
                            "day_of_week": day_of_week,
                            "hour": hour,
                            "day_name": day_name,
                        },
                        confidence=confidence,
                        occurrences=len(records),
                        last_occurrence=records[-1]["timestamp"],
                        suggested_actions=[
                            {
                                "action_type": most_common_action[0],
                                "params": records[-1]["params"],
                            }
                        ],
                    )
                    self.habits[habit_id] = habit
                    logger.info(f"Discovered time habit: {habit_name}")

    def _update_device_habits(self, device_patterns: Dict[str, List[Dict[str, Any]]]) -> None:
        for device, records in device_patterns.items():
            if len(records) < self.min_occurrences:
                continue

            action_counts = defaultdict(int)
            for record in records:
                action_counts[record["action_type"]] += 1

            most_common_action = max(action_counts.items(), key=lambda x: x[1])
            confidence = most_common_action[1] / len(records)

            if confidence >= self.min_confidence:
                habit_id = f"habit_device_{device}"
                habit_name = f"{device}设备习惯"
                description = f"对于{device}设备，经常执行{most_common_action[0]}操作"

                if habit_id in self.habits:
                    self.habits[habit_id].occurrences = len(records)
                    self.habits[habit_id].confidence = confidence
                    self.habits[habit_id].last_occurrence = records[-1]["timestamp"]
                else:
                    habit = Habit(
                        habit_id=habit_id,
                        name=habit_name,
                        description=description,
                        pattern_type="device",
                        pattern_data={"device": device},
                        confidence=confidence,
                        occurrences=len(records),
                        last_occurrence=records[-1]["timestamp"],
                        suggested_actions=[
                            {
                                "action_type": most_common_action[0],
                                "params": records[-1]["params"],
                            }
                        ],
                    )
                    self.habits[habit_id] = habit
                    logger.info(f"Discovered device habit: {habit_name}")

    def _update_sequence_habits(self, sequence_patterns: Dict[str, List[Dict[str, Any]]]) -> None:
        for seq_key, records in sequence_patterns.items():
            if len(records) < self.min_occurrences:
                continue

            confidence = len(records) / len(self.action_history)

            if confidence >= self.min_confidence:
                from_action, to_action = seq_key.split("_")
                habit_id = f"habit_seq_{seq_key}"
                habit_name = f"序列习惯: {from_action} -> {to_action}"
                description = f"经常在{from_action}之后执行{to_action}"

                if habit_id in self.habits:
                    self.habits[habit_id].occurrences = len(records)
                    self.habits[habit_id].confidence = confidence
                    self.habits[habit_id].last_occurrence = records[-1]["timestamp"]
                else:
                    habit = Habit(
                        habit_id=habit_id,
                        name=habit_name,
                        description=description,
                        pattern_type="sequence",
                        pattern_data={
                            "from_action": from_action,
                            "to_action": to_action,
                        },
                        confidence=confidence,
                        occurrences=len(records),
                        last_occurrence=records[-1]["timestamp"],
                        suggested_actions=[
                            {
                                "action_type": to_action,
                                "params": records[-1]["params"],
                            }
                        ],
                    )
                    self.habits[habit_id] = habit
                    logger.info(f"Discovered sequence habit: {habit_name}")

    def get_suggestions(
        self,
        current_time: Optional[float] = None,
        last_action: Optional[str] = None,
        current_device: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        suggestions = []

        if not current_time:
            current_time = time.time()

        dt = datetime.fromtimestamp(current_time)
        day_of_week = dt.weekday()
        hour = dt.hour
        time_key = f"{day_of_week}_{hour}"

        time_habit_id = f"habit_time_{time_key}"
        if time_habit_id in self.habits:
            habit = self.habits[time_habit_id]
            if habit.enabled:
                suggestions.append({
                    "type": "time_based",
                    "habit_id": habit.habit_id,
                    "name": habit.name,
                    "description": habit.description,
                    "confidence": habit.confidence,
                    "suggested_actions": habit.suggested_actions,
                })

        if last_action:
            seq_habit_id = f"habit_seq_{last_action}_{last_action}"
            for habit_id, habit in self.habits.items():
                if (habit.pattern_type == "sequence" and 
                    habit.pattern_data.get("from_action") == last_action and
                    habit.enabled):
                    suggestions.append({
                        "type": "sequence_based",
                        "habit_id": habit.habit_id,
                        "name": habit.name,
                        "description": habit.description,
                        "confidence": habit.confidence,
                        "suggested_actions": habit.suggested_actions,
                    })

        if current_device:
            device_habit_id = f"habit_device_{current_device}"
            if device_habit_id in self.habits:
                habit = self.habits[device_habit_id]
                if habit.enabled:
                    suggestions.append({
                        "type": "device_based",
                        "habit_id": habit.habit_id,
                        "name": habit.name,
                        "description": habit.description,
                        "confidence": habit.confidence,
                        "suggested_actions": habit.suggested_actions,
                    })

        suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        return suggestions[:5]

    def get_habit(self, habit_id: str) -> Optional[Habit]:
        return self.habits.get(habit_id)

    def list_habits(self, enabled_only: bool = False) -> List[Habit]:
        habits = list(self.habits.values())
        if enabled_only:
            habits = [h for h in habits if h.enabled]
        return habits

    def enable_habit(self, habit_id: str) -> bool:
        habit = self.habits.get(habit_id)
        if not habit:
            return False
        habit.enabled = True
        logger.info(f"Enabled habit: {habit.name}")
        return True

    def disable_habit(self, habit_id: str) -> bool:
        habit = self.habits.get(habit_id)
        if not habit:
            return False
        habit.enabled = False
        logger.info(f"Disabled habit: {habit.name}")
        return True

    def delete_habit(self, habit_id: str) -> bool:
        if habit_id not in self.habits:
            return False
        habit = self.habits.pop(habit_id)
        logger.info(f"Deleted habit: {habit.name}")
        return True

    def get_statistics(self) -> Dict[str, Any]:
        total_habits = len(self.habits)
        enabled_habits = sum(1 for h in self.habits.values() if h.enabled)

        by_type = defaultdict(int)
        for habit in self.habits.values():
            by_type[habit.pattern_type] += 1

        return {
            "total_habits": total_habits,
            "enabled_habits": enabled_habits,
            "habits_by_type": dict(by_type),
            "action_history_size": len(self.action_history),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "habits": [habit.to_dict() for habit in self.habits.values()],
            "statistics": self.get_statistics(),
        }

    def save_to_file(self, filepath: str) -> None:
        data = {
            "habits": [habit.to_dict() for habit in self.habits.values()],
            "action_history": self.action_history[-100:],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Habits saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "HabitLearner":
        learner = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for habit_data in data.get("habits", []):
            habit = Habit(
                habit_id=habit_data["habit_id"],
                name=habit_data["name"],
                description=habit_data["description"],
                pattern_type=habit_data["pattern_type"],
                pattern_data=habit_data.get("pattern_data", {}),
                confidence=habit_data["confidence"],
                occurrences=habit_data["occurrences"],
                last_occurrence=habit_data["last_occurrence"],
                suggested_actions=habit_data.get("suggested_actions", []),
                enabled=habit_data.get("enabled", True),
                created_at=habit_data.get("created_at", time.time()),
            )
            learner.habits[habit.habit_id] = habit

        learner.action_history = data.get("action_history", [])
        logger.info(f"Habits loaded from {filepath}")
        return learner
