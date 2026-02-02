from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from collections import deque

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    SECURITY = "security"
    SAFETY = "safety"
    HEALTH = "health"
    DEVICE = "device"
    ENVIRONMENT = "environment"
    ENERGY = "energy"
    BEHAVIOR = "behavior"


@dataclass
class Anomaly:
    anomaly_id: str
    anomaly_type: AnomalyType
    severity: int
    description: str
    detected_at: float
    source: str
    details: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[float] = None
    actions_taken: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_id": self.anomaly_id,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity,
            "description": self.description,
            "detected_at": self.detected_at,
            "source": self.source,
            "details": self.details,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
            "actions_taken": self.actions_taken,
        }


class AnomalyDetector:
    def __init__(self) -> None:
        self.active_anomalies: Dict[str, Anomaly] = {}
        self.anomaly_history: List[Anomaly] = []
        self.max_history_size = 1000
        self._sensor_data: Dict[str, deque] = {}
        self._thresholds: Dict[str, Tuple[float, float]] = {}
        self._init_default_thresholds()

    def _init_default_thresholds(self) -> None:
        self._thresholds = {
            "temperature": (15.0, 35.0),
            "humidity": (20.0, 80.0),
            "air_quality": (0, 150),
            "motion": (0, 10),
            "door_open_duration": (0, 300),
            "device_power": (0, 3000),
        }
        logger.info("Initialized default anomaly thresholds")

    def add_sensor_data(
        self,
        sensor_id: str,
        value: float,
        timestamp: Optional[float] = None
    ) -> Optional[Anomaly]:
        timestamp = timestamp or time.time()

        if sensor_id not in self._sensor_data:
            self._sensor_data[sensor_id] = deque(maxlen=100)

        self._sensor_data[sensor_id].append((timestamp, value))

        return self._check_sensor_anomaly(sensor_id, value, timestamp)

    def _check_sensor_anomaly(
        self,
        sensor_id: str,
        value: float,
        timestamp: float
    ) -> Optional[Anomaly]:
        if sensor_id not in self._thresholds:
            return None

        min_val, max_val = self._thresholds[sensor_id]

        if value < min_val:
            return self._create_anomaly(
                AnomalyType.ENVIRONMENT,
                2,
                f"{sensor_id} 值过低: {value} (阈值: {min_val})",
                sensor_id,
                {"sensor_id": sensor_id, "value": value, "threshold": min_val, "direction": "below"},
                timestamp
            )
        elif value > max_val:
            return self._create_anomaly(
                AnomalyType.ENVIRONMENT,
                3,
                f"{sensor_id} 值过高: {value} (阈值: {max_val})",
                sensor_id,
                {"sensor_id": sensor_id, "value": value, "threshold": max_val, "direction": "above"},
                timestamp
            )

        return None

    def detect_security_event(
        self,
        event_type: str,
        location: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Anomaly:
        severity = 3
        description = f"安全事件: {event_type} 在 {location}"

        if event_type in ["intrusion", "unauthorized_access"]:
            severity = 4
            description = f"检测到入侵: {location}"
        elif event_type in ["door_open", "window_open"]:
            mode = details.get("mode", "home")
            if mode == "away":
                severity = 3
                description = f"离家模式下检测到门窗开启: {location}"

        return self._create_anomaly(
            AnomalyType.SECURITY,
            severity,
            description,
            "security_system",
            {"event_type": event_type, "location": location, **(details or {})},
            time.time()
        )

    def detect_safety_event(
        self,
        event_type: str,
        location: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Anomaly:
        severity = 3

        if event_type in ["fall_detected", "motion_stopped"]:
            severity = 4
            description = f"检测到摔倒/异常: {location}"
        elif event_type in ["fire", "smoke"]:
            severity = 5
            description = f"检测到火灾/烟雾: {location}"
        elif event_type in ["water_leak"]:
            severity = 3
            description = f"检测到漏水: {location}"

        return self._create_anomaly(
            AnomalyType.SAFETY,
            severity,
            description,
            "safety_system",
            {"event_type": event_type, "location": location, **(details or {})},
            time.time()
        )

    def detect_device_anomaly(
        self,
        device_id: str,
        anomaly_type: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Anomaly:
        severity = 2
        description = f"设备异常: {device_id} - {anomaly_type}"

        if anomaly_type in ["offline", "unresponsive"]:
            severity = 3
            description = f"设备离线: {device_id}"
        elif anomaly_type in ["error", "malfunction"]:
            severity = 3
            description = f"设备故障: {device_id}"
        elif anomaly_type in ["high_power"]:
            severity = 2
            description = f"设备能耗异常: {device_id}"

        return self._create_anomaly(
            AnomalyType.DEVICE,
            severity,
            description,
            "device_monitor",
            {"device_id": device_id, "anomaly_type": anomaly_type, **(details or {})},
            time.time()
        )

    def detect_energy_anomaly(
        self,
        consumption: float,
        expected: float,
        threshold_percent: float = 30.0
    ) -> Optional[Anomaly]:
        diff_percent = abs(consumption - expected) / expected * 100

        if diff_percent > threshold_percent:
            direction = "高" if consumption > expected else "低"
            severity = 2 if diff_percent < 50 else 3

            return self._create_anomaly(
                AnomalyType.ENERGY,
                severity,
                f"能耗异常{direction}: 实际{consumption}kWh, 预期{expected}kWh (偏差{diff_percent:.1f}%)",
                "energy_monitor",
                {
                    "consumption": consumption,
                    "expected": expected,
                    "diff_percent": diff_percent,
                    "threshold": threshold_percent
                },
                time.time()
            )

        return None

    def detect_behavior_anomaly(
        self,
        user_id: str,
        behavior_type: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Optional[Anomaly]:
        severity = 1
        description = f"行为异常: {user_id} - {behavior_type}"

        if behavior_type in ["unusual_time", "unusual_location"]:
            severity = 2
            description = f"用户{user_id}在异常时间/地点活动"

        return self._create_anomaly(
            AnomalyType.BEHAVIOR,
            severity,
            description,
            "behavior_monitor",
            {"user_id": user_id, "behavior_type": behavior_type, **(details or {})},
            time.time()
        )

    def _create_anomaly(
        self,
        anomaly_type: AnomalyType,
        severity: int,
        description: str,
        source: str,
        details: Dict[str, Any],
        detected_at: float
    ) -> Anomaly:
        import uuid
        anomaly = Anomaly(
            anomaly_id=str(uuid.uuid4()),
            anomaly_type=anomaly_type,
            severity=severity,
            description=description,
            detected_at=detected_at,
            source=source,
            details=details
        )

        self.active_anomalies[anomaly.anomaly_id] = anomaly
        logger.warning(f"Detected anomaly: {description} (severity: {severity})")

        return anomaly

    def resolve_anomaly(
        self,
        anomaly_id: str,
        actions_taken: List[str]
    ) -> bool:
        anomaly = self.active_anomalies.get(anomaly_id)
        if not anomaly:
            return False

        anomaly.resolved = True
        anomaly.resolved_at = time.time()
        anomaly.actions_taken = actions_taken

        del self.active_anomalies[anomaly_id]
        self.anomaly_history.append(anomaly)

        if len(self.anomaly_history) > self.max_history_size:
            self.anomaly_history = self.anomaly_history[-self.max_history_size:]

        logger.info(f"Resolved anomaly: {anomaly_id}")
        return True

    def get_active_anomalies(
        self,
        min_severity: Optional[int] = None,
        anomaly_type: Optional[AnomalyType] = None
    ) -> List[Anomaly]:
        anomalies = list(self.active_anomalies.values())

        if min_severity is not None:
            anomalies = [a for a in anomalies if a.severity >= min_severity]

        if anomaly_type is not None:
            anomalies = [a for a in anomalies if a.anomaly_type == anomaly_type]

        return sorted(anomalies, key=lambda a: a.detected_at, reverse=True)

    def get_anomaly_history(
        self,
        limit: int = 50,
        resolved_only: bool = False
    ) -> List[Anomaly]:
        anomalies = self.anomaly_history

        if resolved_only:
            anomalies = [a for a in anomalies if a.resolved]

        return sorted(anomalies, key=lambda a: a.detected_at, reverse=True)[:limit]

    def set_threshold(
        self,
        sensor_type: str,
        min_value: float,
        max_value: float
    ) -> None:
        self._thresholds[sensor_type] = (min_value, max_value)
        logger.info(f"Set threshold for {sensor_type}: [{min_value}, {max_value}]")

    def get_statistics(self) -> Dict[str, Any]:
        active_by_type = {}
        for anomaly in self.active_anomalies.values():
            atype = anomaly.anomaly_type.value
            active_by_type[atype] = active_by_type.get(atype, 0) + 1

        history_by_type = {}
        for anomaly in self.anomaly_history:
            atype = anomaly.anomaly_type.value
            history_by_type[atype] = history_by_type.get(atype, 0) + 1

        return {
            "active_anomalies": len(self.active_anomalies),
            "active_by_type": active_by_type,
            "total_resolved": len(self.anomaly_history),
            "resolved_by_type": history_by_type,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_anomalies": [a.to_dict() for a in self.active_anomalies.values()],
            "anomaly_history": [a.to_dict() for a in self.anomaly_history[-100:]],
            "statistics": self.get_statistics(),
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Anomaly data saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "AnomalyDetector":
        detector = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for anomaly_data in data.get("anomaly_history", []):
            anomaly = Anomaly(
                anomaly_id=anomaly_data["anomaly_id"],
                anomaly_type=AnomalyType(anomaly_data["anomaly_type"]),
                severity=anomaly_data["severity"],
                description=anomaly_data["description"],
                detected_at=anomaly_data["detected_at"],
                source=anomaly_data["source"],
                details=anomaly_data.get("details", {}),
                resolved=anomaly_data.get("resolved", True),
                resolved_at=anomaly_data.get("resolved_at"),
                actions_taken=anomaly_data.get("actions_taken", []),
            )
            if anomaly.resolved:
                detector.anomaly_history.append(anomaly)
            else:
                detector.active_anomalies[anomaly.anomaly_id] = anomaly

        logger.info(f"Anomaly detector loaded from {filepath}")
        return detector
