from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class Prediction:
    prediction_id: str
    prediction_type: str
    confidence: float
    predicted_value: Any
    predicted_time: float
    reason: str
    suggested_actions: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "prediction_type": self.prediction_type,
            "confidence": self.confidence,
            "predicted_value": self.predicted_value,
            "predicted_time": self.predicted_time,
            "reason": self.reason,
            "suggested_actions": self.suggested_actions,
            "created_at": self.created_at,
        }


class PredictiveService:
    def __init__(self) -> None:
        self.predictions: Dict[str, Prediction] = {}
        self.prediction_history: List[Prediction] = []
        self.user_patterns: Dict[str, Dict[str, Any]] = {}
        self.device_usage: Dict[str, deque] = {}
        self._init_patterns()

    def _init_patterns(self) -> None:
        self.user_patterns = {
            "arrival_times": {"morning": [], "evening": []},
            "departure_times": {"morning": [], "evening": []},
            "activity_times": {},
        }
        logger.info("Initialized predictive service patterns")

    def record_user_activity(
        self,
        user_id: str,
        activity_type: str,
        timestamp: Optional[float] = None
    ) -> None:
        timestamp = timestamp or time.time()
        dt = datetime.fromtimestamp(timestamp)
        hour = dt.hour
        day_of_week = dt.weekday()

        key = f"{user_id}_{activity_type}_{day_of_week}_{hour}"
        if key not in self.user_patterns["activity_times"]:
            self.user_patterns["activity_times"][key] = []
        self.user_patterns["activity_times"][key].append(timestamp)

        if activity_type == "arrival":
            if 6 <= hour < 12:
                self.user_patterns["arrival_times"]["morning"].append(timestamp)
            elif 17 <= hour < 23:
                self.user_patterns["arrival_times"]["evening"].append(timestamp)
        elif activity_type == "departure":
            if 6 <= hour < 12:
                self.user_patterns["departure_times"]["morning"].append(timestamp)
            elif 17 <= hour < 23:
                self.user_patterns["departure_times"]["evening"].append(timestamp)

    def record_device_usage(
        self,
        device_id: str,
        state: str,
        timestamp: Optional[float] = None
    ) -> None:
        timestamp = timestamp or time.time()

        if device_id not in self.device_usage:
            self.device_usage[device_id] = deque(maxlen=100)

        self.device_usage[device_id].append({
            "timestamp": timestamp,
            "state": state,
        })

    def predict_user_arrival(
        self,
        user_id: str,
        time_period: str = "evening"
    ) -> Optional[Prediction]:
        arrivals = self.user_patterns["arrival_times"].get(time_period, [])
        if len(arrivals) < 3:
            return None

        arrival_times = [datetime.fromtimestamp(t) for t in arrivals[-10:]]
        hours = [dt.hour + dt.minute / 60 for dt in arrival_times]
        avg_hour = sum(hours) / len(hours)

        predicted_dt = datetime.now().replace(
            hour=int(avg_hour),
            minute=int((avg_hour % 1) * 60),
            second=0,
            microsecond=0
        )

        if predicted_dt < datetime.now():
            predicted_dt += timedelta(days=1)

        confidence = min(len(arrivals) / 10, 0.9)

        import uuid
        prediction = Prediction(
            prediction_id=str(uuid.uuid4()),
            prediction_type="user_arrival",
            confidence=confidence,
            predicted_value=predicted_dt.isoformat(),
            predicted_time=predicted_dt.timestamp(),
            reason=f"基于历史数据，用户{user_id}通常在{int(avg_hour)}点回家",
            suggested_actions=[
                {
                    "action_type": "prepare_home",
                    "params": {
                        "user_id": user_id,
                        "expected_time": predicted_dt.isoformat(),
                    },
                }
            ],
        )

        self.predictions[prediction.prediction_id] = prediction
        return prediction

    def predict_temperature_preference(
        self,
        user_id: str,
        time_of_day: str
    ) -> Optional[Prediction]:
        key = f"{user_id}_temperature_{time_of_day}"
        preferences = self.user_patterns.get("activity_times", {}).get(key, [])

        if not preferences:
            return None

        import uuid
        prediction = Prediction(
            prediction_id=str(uuid.uuid4()),
            prediction_type="temperature_preference",
            confidence=0.7,
            predicted_value=24,
            predicted_time=time.time(),
            reason=f"根据{time_of_day}时段的使用模式，预测偏好温度",
            suggested_actions=[
                {
                    "action_type": "set_temperature",
                    "params": {"value": 24},
                }
            ],
        )

        self.predictions[prediction.prediction_id] = prediction
        return prediction

    def predict_energy_consumption(
        self,
        device_id: str,
        hours_ahead: int = 24
    ) -> Optional[Prediction]:
        usage_history = self.device_usage.get(device_id, deque())
        if len(usage_history) < 24:
            return None

        recent_usage = list(usage_history)[-24:]
        active_periods = sum(1 for u in recent_usage if u["state"] == "on")

        avg_daily_active = active_periods / len(recent_usage) * 24
        estimated_consumption = avg_daily_active * 0.1

        import uuid
        prediction = Prediction(
            prediction_id=str(uuid.uuid4()),
            prediction_type="energy_consumption",
            confidence=0.6,
            predicted_value=f"{estimated_consumption:.2f} kWh",
            predicted_time=time.time() + hours_ahead * 3600,
            reason=f"基于最近24小时的使用模式",
            suggested_actions=[
                {
                    "action_type": "notify",
                    "params": {
                        "message": f"预计{device_id}未来{hours_ahead}小时耗电约{estimated_consumption:.2f} kWh"
                    },
                }
            ],
        )

        self.predictions[prediction.prediction_id] = prediction
        return prediction

    def predict_device_need(
        self,
        device_id: str,
        context: Dict[str, Any]
    ) -> Optional[Prediction]:
        usage_history = self.device_usage.get(device_id, deque())
        if len(usage_history) < 5:
            return None

        current_time = datetime.now()
        current_hour = current_time.hour

        same_hour_usage = [
            u for u in usage_history
            if datetime.fromtimestamp(u["timestamp"]).hour == current_hour
        ]

        if len(same_hour_usage) >= 3:
            import uuid
            prediction = Prediction(
                prediction_id=str(uuid.uuid4()),
                prediction_type="device_need",
                confidence=0.7,
                predicted_value="likely_needed",
                predicted_time=time.time() + 300,
                reason=f"设备{device_id}通常在这个时间段被使用",
                suggested_actions=[
                    {
                        "action_type": "prepare_device",
                        "params": {"device_id": device_id},
                    }
                ],
            )

            self.predictions[prediction.prediction_id] = prediction
            return prediction

        return None

    def get_all_predictions(self, max_age_hours: int = 24) -> List[Prediction]:
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        return [
            pred for pred in self.predictions.values()
            if current_time - pred.created_at < max_age_seconds
        ]

    def get_prediction(self, prediction_id: str) -> Optional[Prediction]:
        return self.predictions.get(prediction_id)

    def clear_old_predictions(self, max_age_hours: int = 24) -> int:
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        old_ids = [
            pred_id for pred_id, pred in self.predictions.items()
            if current_time - pred.created_at > max_age_seconds
        ]

        for pred_id in old_ids:
            pred = self.predictions.pop(pred_id)
            self.prediction_history.append(pred)

        logger.info(f"Cleared {len(old_ids)} old predictions")
        return len(old_ids)

    def get_user_pattern_summary(self, user_id: str) -> Dict[str, Any]:
        return {
            "arrival_times": {
                period: [datetime.fromtimestamp(t).strftime("%H:%M") for t in times[-5:]]
                for period, times in self.user_patterns["arrival_times"].items()
            },
            "departure_times": {
                period: [datetime.fromtimestamp(t).strftime("%H:%M") for t in times[-5:]]
                for period, times in self.user_patterns["departure_times"].items()
            },
        }

    def get_device_usage_summary(self, device_id: str) -> Dict[str, Any]:
        usage_history = self.device_usage.get(device_id, deque())

        if not usage_history:
            return {"error": "No usage data"}

        recent_usage = list(usage_history)[-100:]
        active_count = sum(1 for u in recent_usage if u["state"] == "on")
        total_count = len(recent_usage)

        return {
            "device_id": device_id,
            "total_records": total_count,
            "active_percentage": (active_count / total_count * 100) if total_count > 0 else 0,
            "last_active": recent_usage[-1]["timestamp"] if recent_usage else None,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_predictions": [p.to_dict() for p in self.predictions.values()],
            "prediction_count": len(self.predictions),
            "user_patterns": self.user_patterns,
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Predictive service data saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "PredictiveService":
        service = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for pred_data in data.get("active_predictions", []):
            prediction = Prediction(
                prediction_id=pred_data["prediction_id"],
                prediction_type=pred_data["prediction_type"],
                confidence=pred_data["confidence"],
                predicted_value=pred_data["predicted_value"],
                predicted_time=pred_data["predicted_time"],
                reason=pred_data["reason"],
                suggested_actions=pred_data.get("suggested_actions", []),
                created_at=pred_data.get("created_at", time.time()),
            )
            service.predictions[prediction.prediction_id] = prediction

        if "user_patterns" in data:
            service.user_patterns = data["user_patterns"]

        logger.info(f"Predictive service loaded from {filepath}")
        return service
