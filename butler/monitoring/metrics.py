from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class MetricUnit(Enum):
    NONE = ""
    SECONDS = "seconds"
    MILLISECONDS = "milliseconds"
    BYTES = "bytes"
    COUNT = "count"
    PERCENTAGE = "percentage"
    REQUESTS_PER_SECOND = "requests_per_second"
    CUSTOM = "custom"


@dataclass
class MetricLabel:
    name: str
    value: str

    def to_tuple(self) -> Tuple[str, str]:
        return (self.name, self.value)


@dataclass
class MetricValue:
    value: Union[int, float]
    timestamp: float = field(default_factory=time.time)
    labels: List[MetricLabel] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "timestamp": self.timestamp,
            "labels": {l.name: l.value for l in self.labels},
        }


class Metric(ABC):
    def __init__(
        self,
        name: str,
        description: str,
        unit: MetricUnit = MetricUnit.NONE,
        labels: Optional[List[str]] = None,
    ):
        self.name = name
        self.description = description
        self.unit = unit
        self.label_names = labels or []
        self._values: List[MetricValue] = []
        self._max_values = 10000

    @abstractmethod
    def record(self, value: Union[int, float], labels: Optional[Dict[str, str]] = None) -> None:
        pass

    @abstractmethod
    def get(self, labels: Optional[Dict[str, str]] = None) -> Union[int, float, Dict[str, Any]]:
        pass

    @abstractmethod
    def reset(self) -> None:
        pass

    def _create_labels(self, label_dict: Optional[Dict[str, str]] = None) -> List[MetricLabel]:
        if not label_dict:
            return []

        return [
            MetricLabel(name=name, value=str(label_dict[name]))
            for name in self.label_names
            if name in label_dict
        ]

    def _add_value(self, value: Union[int, float], labels: Optional[Dict[str, str]] = None) -> None:
        metric_value = MetricValue(
            value=value,
            labels=self._create_labels(labels),
        )
        self._values.append(metric_value)

        if len(self._values) > self._max_values:
            self._values = self._values[-self._max_values:]

    def get_values(self, limit: int = 100) -> List[MetricValue]:
        return self._values[-limit:]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "unit": self.unit.value,
            "label_names": self.label_names,
            "values": [v.to_dict() for v in self._values[-10:]],
        }


class Counter(Metric):
    def __init__(
        self,
        name: str,
        description: str,
        unit: MetricUnit = MetricUnit.COUNT,
        labels: Optional[List[str]] = None,
    ):
        super().__init__(name, description, unit, labels)
        self._counters: Dict[Tuple[Tuple[str, str], ...], float] = {}

    def record(self, value: Union[int, float] = 1, labels: Optional[Dict[str, str]] = None) -> None:
        label_key = tuple(sorted((k, str(v)) for k, v in (labels or {}).items()))

        if label_key not in self._counters:
            self._counters[label_key] = 0.0

        self._counters[label_key] += float(value)
        self._add_value(self._counters[label_key], labels)

    def increment(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.record(1, labels)

    def decrement(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.record(-1, labels)

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        if labels is None:
            return sum(self._counters.values())

        label_key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        return self._counters.get(label_key, 0.0)

    def reset(self) -> None:
        self._counters.clear()
        self._values.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "type": "counter",
            "counters": {str(k): v for k, v in self._counters.items()},
        }


class Gauge(Metric):
    def __init__(
        self,
        name: str,
        description: str,
        unit: MetricUnit = MetricUnit.NONE,
        labels: Optional[List[str]] = None,
    ):
        super().__init__(name, description, unit, labels)
        self._gauges: Dict[Tuple[Tuple[str, str], ...], float] = {}

    def record(self, value: Union[int, float], labels: Optional[Dict[str, str]] = None) -> None:
        label_key = tuple(sorted((k, str(v)) for k, v in (labels or {}).items()))
        self._gauges[label_key] = float(value)
        self._add_value(value, labels)

    def set(self, value: Union[int, float], labels: Optional[Dict[str, str]] = None) -> None:
        self.record(value, labels)

    def increment(self, delta: Union[int, float] = 1, labels: Optional[Dict[str, str]] = None) -> None:
        label_key = tuple(sorted((k, str(v)) for k, v in (labels or {}).items()))
        current = self._gauges.get(label_key, 0.0)
        self._gauges[label_key] = current + float(delta)
        self._add_value(self._gauges[label_key], labels)

    def decrement(self, delta: Union[int, float] = 1, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment(-delta, labels)

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        if labels is None:
            return sum(self._gauges.values()) / len(self._gauges) if self._gauges else 0.0

        label_key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        return self._gauges.get(label_key, 0.0)

    def reset(self) -> None:
        self._gauges.clear()
        self._values.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "type": "gauge",
            "gauges": {str(k): v for k, v in self._gauges.items()},
        }


class Histogram(Metric):
    def __init__(
        self,
        name: str,
        description: str,
        buckets: Optional[List[float]] = None,
        unit: MetricUnit = MetricUnit.NONE,
        labels: Optional[List[str]] = None,
    ):
        super().__init__(name, description, unit, labels)
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self._observations: Dict[Tuple[Tuple[str, str], ...], List[float]] = {}

    def record(self, value: Union[int, float], labels: Optional[Dict[str, str]] = None) -> None:
        label_key = tuple(sorted((k, str(v)) for k, v in (labels or {}).items()))

        if label_key not in self._observations:
            self._observations[label_key] = []

        self._observations[label_key].append(float(value))
        self._add_value(value, labels)

    def observe(self, value: Union[int, float], labels: Optional[Dict[str, str]] = None) -> None:
        self.record(value, labels)

    def get(self, labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        if labels is None:
            all_values = [v for obs in self._observations.values() for v in obs]
            return self._calculate_stats(all_values)

        label_key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        values = self._observations.get(label_key, [])
        return self._calculate_stats(values)

    def _calculate_stats(self, values: List[float]) -> Dict[str, Any]:
        if not values:
            return {
                "count": 0,
                "sum": 0.0,
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "buckets": {f"+{b}": 0 for b in self.buckets},
            }

        sorted_values = sorted(values)
        count = len(values)
        total = sum(values)

        buckets = {}
        for bucket in self.buckets:
            buckets[f"+{bucket}"] = sum(1 for v in values if v <= bucket)

        return {
            "count": count,
            "sum": total,
            "avg": total / count,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "buckets": buckets,
        }

    def reset(self) -> None:
        self._observations.clear()
        self._values.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "type": "histogram",
            "buckets": self.buckets,
            "observations": {str(k): len(v) for k, v in self._observations.items()},
        }


class Summary(Metric):
    def __init__(
        self,
        name: str,
        description: str,
        quantiles: Optional[List[float]] = None,
        max_age: float = 600.0,
        unit: MetricUnit = MetricUnit.NONE,
        labels: Optional[List[str]] = None,
    ):
        super().__init__(name, description, unit, labels)
        self.quantiles = quantiles or [0.5, 0.9, 0.95, 0.99]
        self.max_age = max_age
        self._observations: Dict[Tuple[Tuple[str, str], ...], List[Tuple[float, float]]] = {}

    def record(self, value: Union[int, float], labels: Optional[Dict[str, str]] = None) -> None:
        label_key = tuple(sorted((k, str(v)) for k, v in (labels or {}).items()))

        if label_key not in self._observations:
            self._observations[label_key] = []

        self._observations[label_key].append((float(value), time.time()))
        self._cleanup_old_observations(label_key)
        self._add_value(value, labels)

    def observe(self, value: Union[int, float], labels: Optional[Dict[str, str]] = None) -> None:
        self.record(value, labels)

    def _cleanup_old_observations(self, label_key: Tuple[Tuple[str, str], ...]) -> None:
        if label_key not in self._observations:
            return

        current_time = time.time()
        self._observations[label_key] = [
            (v, t) for v, t in self._observations[label_key]
            if current_time - t <= self.max_age
        ]

    def get(self, labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        if labels is None:
            all_values = [v for obs in self._observations.values() for v, t in obs]
            return self._calculate_summary(all_values)

        label_key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        observations = self._observations.get(label_key, [])
        values = [v for v, t in observations]
        return self._calculate_summary(values)

    def _calculate_summary(self, values: List[float]) -> Dict[str, Any]:
        if not values:
            return {
                "count": 0,
                "sum": 0.0,
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "quantiles": {q: 0.0 for q in self.quantiles},
            }

        sorted_values = sorted(values)
        count = len(values)
        total = sum(values)

        quantiles = {}
        for q in self.quantiles:
            index = int(q * (count - 1))
            quantiles[str(q)] = sorted_values[index]

        return {
            "count": count,
            "sum": total,
            "avg": total / count,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "quantiles": quantiles,
        }

    def reset(self) -> None:
        self._observations.clear()
        self._values.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "type": "summary",
            "quantiles": self.quantiles,
            "max_age": self.max_age,
            "observations": {str(k): len(v) for k, v in self._observations.items()},
        }


class MetricsRegistry:
    def __init__(self):
        self._metrics: Dict[str, Metric] = {}

    def register(self, metric: Metric) -> None:
        self._metrics[metric.name] = metric

    def unregister(self, name: str) -> bool:
        if name in self._metrics:
            del self._metrics[name]
            return True
        return False

    def get(self, name: str) -> Optional[Metric]:
        return self._metrics.get(name)

    def counter(
        self,
        name: str,
        description: str,
        unit: MetricUnit = MetricUnit.COUNT,
        labels: Optional[List[str]] = None,
    ) -> Counter:
        if name not in self._metrics:
            counter = Counter(name, description, unit, labels)
            self.register(counter)
        return self._metrics[name]

    def gauge(
        self,
        name: str,
        description: str,
        unit: MetricUnit = MetricUnit.NONE,
        labels: Optional[List[str]] = None,
    ) -> Gauge:
        if name not in self._metrics:
            gauge = Gauge(name, description, unit, labels)
            self.register(gauge)
        return self._metrics[name]

    def histogram(
        self,
        name: str,
        description: str,
        buckets: Optional[List[float]] = None,
        unit: MetricUnit = MetricUnit.NONE,
        labels: Optional[List[str]] = None,
    ) -> Histogram:
        if name not in self._metrics:
            histogram = Histogram(name, description, buckets, unit, labels)
            self.register(histogram)
        return self._metrics[name]

    def summary(
        self,
        name: str,
        description: str,
        quantiles: Optional[List[float]] = None,
        max_age: float = 600.0,
        unit: MetricUnit = MetricUnit.NONE,
        labels: Optional[List[str]] = None,
    ) -> Summary:
        if name not in self._metrics:
            summary = Summary(name, description, quantiles, max_age, unit, labels)
            self.register(summary)
        return self._metrics[name]

    def get_all(self) -> Dict[str, Metric]:
        return self._metrics.copy()

    def reset_all(self) -> None:
        for metric in self._metrics.values():
            metric.reset()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metrics": {name: metric.to_dict() for name, metric in self._metrics.items()},
            "metric_count": len(self._metrics),
        }

    def export_prometheus(self) -> str:
        lines = []

        for metric in self._metrics.values():
            lines.append(f"# HELP {metric.name} {metric.description}")
            lines.append(f"# TYPE {metric.name} {metric.type}")

            if isinstance(metric, Counter):
                for label_key, value in metric._counters.items():
                    labels = ",".join(f'{k}="{v}"' for k, v in label_key)
                    lines.append(f"{metric.name}{{{labels}}} {value}")

            elif isinstance(metric, Gauge):
                for label_key, value in metric._gauges.items():
                    labels = ",".join(f'{k}="{v}"' for k, v in label_key)
                    lines.append(f"{metric.name}{{{labels}}} {value}")

            elif isinstance(metric, Histogram):
                for label_key, values in metric._observations.items():
                    labels = ",".join(f'{k}="{v}"' for k, v in label_key)
                    stats = metric._calculate_stats(values)
                    for bucket, count in stats["buckets"].items():
                        lines.append(f"{metric.name}_bucket{{{labels},le=\"{bucket[1:]}}} {count}")
                    lines.append(f"{metric.name}_sum{{{labels}}} {stats['sum']}")
                    lines.append(f"{metric.name}_count{{{labels}}} {stats['count']}")

            elif isinstance(metric, Summary):
                for label_key, observations in metric._observations.items():
                    labels = ",".join(f'{k}="{v}"' for k, v in label_key)
                    values = [v for v, t in observations]
                    stats = metric._calculate_summary(values)
                    lines.append(f"{metric.name}_sum{{{labels}}} {stats['sum']}")
                    lines.append(f"{metric.name}_count{{{labels}}} {stats['count']}")
                    for q, v in stats["quantiles"].items():
                        lines.append(f"{metric.name}{{{labels},quantile=\"{q}\"} {v}")

            lines.append("")

        return "\n".join(lines)


_global_registry: Optional[MetricsRegistry] = None


def init_registry() -> MetricsRegistry:
    global _global_registry

    if _global_registry is None:
        _global_registry = MetricsRegistry()

    return _global_registry


def get_registry() -> MetricsRegistry:
    global _global_registry

    if _global_registry is None:
        _global_registry = init_registry()

    return _global_registry


def create_counter(name: str, description: str, **kwargs) -> Counter:
    return get_registry().counter(name, description, **kwargs)


def create_gauge(name: str, description: str, **kwargs) -> Gauge:
    return get_registry().gauge(name, description, **kwargs)


def create_histogram(name: str, description: str, **kwargs) -> Histogram:
    return get_registry().histogram(name, description, **kwargs)


def create_summary(name: str, description: str, **kwargs) -> Summary:
    return get_registry().summary(name, description, **kwargs)
