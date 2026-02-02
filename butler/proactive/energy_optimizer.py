from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


@dataclass
class EnergyProfile:
    device_id: str
    device_name: str
    base_power: float
    avg_daily_consumption: float
    avg_hourly_consumption: Dict[int, float] = field(default_factory=dict)
    peak_hours: List[int] = field(default_factory=list)
    standby_power: float = 0.0
    efficiency_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "base_power": self.base_power,
            "avg_daily_consumption": self.avg_daily_consumption,
            "avg_hourly_consumption": self.avg_hourly_consumption,
            "peak_hours": self.peak_hours,
            "standby_power": self.standby_power,
            "efficiency_score": self.efficiency_score,
        }


@dataclass
class EnergySuggestion:
    suggestion_id: str
    title: str
    description: str
    potential_savings: float
    priority: int
    actions: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "title": self.title,
            "description": self.description,
            "potential_savings": self.potential_savings,
            "priority": self.priority,
            "actions": self.actions,
            "created_at": self.created_at,
        }


class EnergyOptimizer:
    def __init__(self) -> None:
        self.energy_profiles: Dict[str, EnergyProfile] = {}
        self.consumption_history: Dict[str, deque] = {}
        self.suggestions: Dict[str, EnergySuggestion] = {}
        self.total_daily_consumption: deque = deque(maxlen=365)
        self.optimization_rules: List[Dict[str, Any]] = []
        self._init_default_rules()

    def _init_default_rules(self) -> None:
        self.optimization_rules = [
            {
                "rule_id": "turn_off_standby",
                "name": "关闭待机设备",
                "description": "检测长时间待机的设备并建议关闭",
                "threshold_hours": 4,
                "enabled": True,
            },
            {
                "rule_id": "optimize_lighting",
                "name": "优化照明",
                "description": "根据自然光和使用模式调整照明亮度",
                "enabled": True,
            },
            {
                "rule_id": "shift_usage",
                "name": "错峰用电",
                "description": "将高耗能设备的使用时间调整到低谷时段",
                "enabled": True,
            },
            {
                "rule_id": "reduce_peak_load",
                "name": "降低峰值负荷",
                "description": "在用电高峰期减少非必要设备的使用",
                "enabled": True,
            },
        ]
        logger.info(f"Initialized {len(self.optimization_rules)} optimization rules")

    def record_consumption(
        self,
        device_id: str,
        power: float,
        timestamp: Optional[float] = None
    ) -> None:
        timestamp = timestamp or time.time()
        dt = datetime.fromtimestamp(timestamp)
        hour = dt.hour

        if device_id not in self.consumption_history:
            self.consumption_history[device_id] = deque(maxlen=24 * 7)

        self.consumption_history[device_id].append({
            "timestamp": timestamp,
            "power": power,
            "hour": hour,
        })

        self._update_energy_profile(device_id, power, hour)

    def _update_energy_profile(self, device_id: str, power: float, hour: int) -> None:
        if device_id not in self.energy_profiles:
            return

        profile = self.energy_profiles[device_id]

        if hour not in profile.avg_hourly_consumption:
            profile.avg_hourly_consumption[hour] = 0.0

        profile.avg_hourly_consumption[hour] = (
            profile.avg_hourly_consumption[hour] * 0.9 + power * 0.1
        )

        profile.avg_daily_consumption = sum(profile.avg_hourly_consumption.values())

        if power > profile.base_power * 1.5:
            if hour not in profile.peak_hours:
                profile.peak_hours.append(hour)
            if len(profile.peak_hours) > 5:
                profile.peak_hours = profile.peak_hours[-5:]

    def add_device_profile(
        self,
        device_id: str,
        device_name: str,
        base_power: float
    ) -> EnergyProfile:
        profile = EnergyProfile(
            device_id=device_id,
            device_name=device_name,
            base_power=base_power,
            avg_daily_consumption=0.0,
            avg_hourly_consumption={h: 0.0 for h in range(24)},
            peak_hours=[],
            standby_power=base_power * 0.1,
        )
        self.energy_profiles[device_id] = profile
        logger.info(f"Added energy profile for device: {device_name}")
        return profile

    def calculate_daily_consumption(self, date: Optional[datetime] = None) -> Dict[str, float]:
        date = date or datetime.now()
        date_str = date.strftime("%Y-%m-%d")

        consumption_by_device = {}
        total_consumption = 0.0

        for device_id, profile in self.energy_profiles.items():
            daily_consumption = profile.avg_daily_consumption
            consumption_by_device[device_id] = daily_consumption
            total_consumption += daily_consumption

        self.total_daily_consumption.append({
            "date": date_str,
            "total": total_consumption,
            "by_device": consumption_by_device,
        })

        return consumption_by_device

    def generate_suggestions(self) -> List[EnergySuggestion]:
        suggestions = []

        for rule in self.optimization_rules:
            if not rule.get("enabled"):
                continue

            rule_suggestions = self._apply_rule(rule)
            suggestions.extend(rule_suggestions)

        for suggestion in suggestions:
            self.suggestions[suggestion.suggestion_id] = suggestion

        return suggestions

    def _apply_rule(self, rule: Dict[str, Any]) -> List[EnergySuggestion]:
        rule_id = rule["rule_id"]
        suggestions = []

        if rule_id == "turn_off_standby":
            suggestions.extend(self._check_standby_devices(rule))
        elif rule_id == "optimize_lighting":
            suggestions.extend(self._optimize_lighting(rule))
        elif rule_id == "shift_usage":
            suggestions.extend(self._suggest_usage_shift(rule))
        elif rule_id == "reduce_peak_load":
            suggestions.extend(self._reduce_peak_load(rule))

        return suggestions

    def _check_standby_devices(self, rule: Dict[str, Any]) -> List[EnergySuggestion]:
        suggestions = []
        threshold_hours = rule.get("threshold_hours", 4)
        current_time = time.time()
        threshold_seconds = threshold_hours * 3600

        for device_id, profile in self.energy_profiles.items():
            history = self.consumption_history.get(device_id, deque())
            if len(history) < 10:
                continue

            recent_power = [r["power"] for r in list(history)[-10:]]
            avg_power = sum(recent_power) / len(recent_power)

            if avg_power <= profile.standby_power * 1.2:
                last_high_power = None
                for record in reversed(history):
                    if record["power"] > profile.base_power * 0.5:
                        last_high_power = record["timestamp"]
                        break

                if last_high_power and (current_time - last_high_power) > threshold_seconds:
                    import uuid
                    suggestion = EnergySuggestion(
                        suggestion_id=str(uuid.uuid4()),
                        title=f"关闭待机设备: {profile.device_name}",
                        description=f"{profile.device_name} 已待机超过 {threshold_hours} 小时",
                        potential_savings=profile.standby_power * 24 / 1000,
                        priority=2,
                        actions=[
                            {
                                "action_type": "turn_off",
                                "params": {"target": device_id},
                            }
                        ],
                    )
                    suggestions.append(suggestion)

        return suggestions

    def _optimize_lighting(self, rule: Dict[str, Any]) -> List[EnergySuggestion]:
        suggestions = []
        current_hour = datetime.now().hour

        lighting_profiles = [
            (did, p) for did, p in self.energy_profiles.items()
            if "light" in did.lower() or "灯" in p.device_name
        ]

        for device_id, profile in lighting_profiles:
            if current_hour in [6, 7, 8, 17, 18, 19]:
                import uuid
                suggestion = EnergySuggestion(
                    suggestion_id=str(uuid.uuid4()),
                    title=f"优化照明: {profile.device_name}",
                    description="根据当前时间段，建议调整照明亮度以节能",
                    potential_savings=profile.base_power * 0.3 * 6 / 1000,
                    priority=1,
                    actions=[
                        {
                            "action_type": "set_brightness",
                            "params": {"target": device_id, "value": 70},
                        }
                    ],
                )
                suggestions.append(suggestion)

        return suggestions

    def _suggest_usage_shift(self, rule: Dict[str, Any]) -> List[EnergySuggestion]:
        suggestions = []
        current_hour = datetime.now().hour
        peak_hours = [10, 11, 12, 18, 19, 20, 21]

        if current_hour in peak_hours:
            for device_id, profile in self.energy_profiles.items():
                if profile.base_power > 1000 and device_id in self.consumption_history:
                    history = list(self.consumption_history[device_id])
                    if history and history[-1]["power"] > profile.base_power * 0.8:
                        import uuid
                        suggestion = EnergySuggestion(
                            suggestion_id=str(uuid.uuid4()),
                            title=f"错峰使用: {profile.device_name}",
                            description="当前为用电高峰期，建议将此设备的使用时间调整到低谷期",
                            potential_savings=profile.base_power * 0.2 / 1000,
                            priority=2,
                            actions=[
                                {
                                    "action_type": "notify",
                                    "params": {
                                        "message": f"{profile.device_name} 在用电高峰期运行，建议延迟使用"
                                    },
                                }
                            ],
                        )
                        suggestions.append(suggestion)

        return suggestions

    def _reduce_peak_load(self, rule: Dict[str, Any]) -> List[EnergySuggestion]:
        suggestions = []
        current_hour = datetime.now().hour
        peak_hours = [18, 19, 20]

        if current_hour in peak_hours:
            total_power = 0.0
            for history in self.consumption_history.values():
                if history:
                    total_power += history[-1]["power"]

            if total_power > 5000:
                import uuid
                suggestion = EnergySuggestion(
                    suggestion_id=str(uuid.uuid4()),
                    title="降低峰值负荷",
                    description=f"当前总功率 {total_power}W 较高，建议关闭非必要设备",
                    potential_savings=(total_power - 3000) / 1000,
                    priority=3,
                    actions=[
                        {
                            "action_type": "reduce_load",
                            "params": {"target_power": 3000},
                        }
                    ],
                )
                suggestions.append(suggestion)

        return suggestions

    def get_energy_statistics(self) -> Dict[str, Any]:
        total_devices = len(self.energy_profiles)
        avg_daily = sum(p.avg_daily_consumption for p in self.energy_profiles.values())
        active_suggestions = len(self.suggestions)

        if self.total_daily_consumption:
            recent_consumption = list(self.total_daily_consumption)[-7:]
            avg_weekly = sum(c["total"] for c in recent_consumption) / len(recent_consumption)
        else:
            avg_weekly = 0.0

        return {
            "total_devices": total_devices,
            "avg_daily_consumption": avg_daily,
            "avg_weekly_consumption": avg_weekly,
            "active_suggestions": active_suggestions,
            "optimization_rules_enabled": sum(1 for r in self.optimization_rules if r.get("enabled")),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "energy_profiles": [p.to_dict() for p in self.energy_profiles.values()],
            "suggestions": [s.to_dict() for s in self.suggestions.values()],
            "statistics": self.get_energy_statistics(),
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Energy optimizer data saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "EnergyOptimizer":
        optimizer = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for profile_data in data.get("energy_profiles", []):
            profile = EnergyProfile(
                device_id=profile_data["device_id"],
                device_name=profile_data["device_name"],
                base_power=profile_data["base_power"],
                avg_daily_consumption=profile_data["avg_daily_consumption"],
                avg_hourly_consumption=profile_data.get("avg_hourly_consumption", {}),
                peak_hours=profile_data.get("peak_hours", []),
                standby_power=profile_data.get("standby_power", 0.0),
                efficiency_score=profile_data.get("efficiency_score", 1.0),
            )
            optimizer.energy_profiles[profile.device_id] = profile

        for suggestion_data in data.get("suggestions", []):
            suggestion = EnergySuggestion(
                suggestion_id=suggestion_data["suggestion_id"],
                title=suggestion_data["title"],
                description=suggestion_data["description"],
                potential_savings=suggestion_data["potential_savings"],
                priority=suggestion_data["priority"],
                actions=suggestion_data.get("actions", []),
                created_at=suggestion_data.get("created_at", time.time()),
            )
            optimizer.suggestions[suggestion.suggestion_id] = suggestion

        logger.info(f"Energy optimizer loaded from {filepath}")
        return optimizer
