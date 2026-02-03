from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from datetime import datetime
from pathlib import Path


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogCategory(Enum):
    SYSTEM = "system"
    DEVICE = "device"
    AGENT = "agent"
    AUTOMATION = "automation"
    GOAL = "goal"
    MEMORY = "memory"
    VISION = "vision"
    DIALOGUE = "dialogue"
    NETWORK = "network"
    SECURITY = "security"
    PERFORMANCE = "performance"
    USER = "user"
    CUSTOM = "custom"


@dataclass
class LogEntry:
    timestamp: float
    level: LogLevel
    category: LogCategory
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    thread_id: Optional[str] = None
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "level": self.level.value,
            "category": self.category.value,
            "message": self.message,
            "context": self.context,
            "source": self.source,
            "thread_id": self.thread_id,
            "request_id": self.request_id,
            "user_id": self.user_id,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class ButlerLogFormatter(logging.Formatter):
    def __init__(self):
        super().__init__()
        self.colors = {
            logging.DEBUG: "\033[36m",
            logging.INFO: "\033[32m",
            logging.WARNING: "\033[33m",
            logging.ERROR: "\033[31m",
            logging.CRITICAL: "\033[35m",
        }
        self.reset = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.colors.get(record.levelno, "")
        level = record.levelname
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        parts = [
            f"{color}[{timestamp}]{self.reset}",
            f"{color}[{level}]{self.reset}",
            f"{color}[{record.name}]{self.reset}",
            f"{record.getMessage()}",
        ]

        if hasattr(record, "category"):
            parts.insert(3, f"[{record.category}]")

        if hasattr(record, "context") and record.context:
            parts.append(f" | Context: {json.dumps(record.context)}")

        return " ".join(parts)


class ButlerLogger:
    def __init__(
        self,
        name: str = "butler",
        log_dir: Optional[str] = None,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        level: LogLevel = LogLevel.INFO,
        enable_console: bool = True,
        enable_file: bool = True,
    ):
        self.name = name
        self.log_dir = Path(log_dir) if log_dir else Path.home() / ".butler" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.max_bytes = max_bytes
        self.backup_count = backup_count

        self._loggers: Dict[str, logging.Logger] = {}
        self._handlers: List[logging.Handler] = []
        self._log_entries: List[LogEntry] = []
        self._max_entries = 10000
        self._listeners: List[Callable[[LogEntry], None]] = []

        self._setup_logging(level, enable_console, enable_file)

    def _setup_logging(
        self,
        level: LogLevel,
        enable_console: bool,
        enable_file: bool,
    ) -> None:
        log_level = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }[level]

        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(ButlerLogFormatter())
            self._handlers.append(console_handler)

        if enable_file:
            file_handler = logging.handlers.RotatingFileHandler(
                self.log_dir / f"{self.name}.log",
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(ButlerLogFormatter())
            self._handlers.append(file_handler)

            error_handler = logging.handlers.RotatingFileHandler(
                self.log_dir / f"{self.name}_error.log",
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding="utf-8",
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(ButlerLogFormatter())
            self._handlers.append(error_handler)

    def get_logger(self, name: str) -> logging.Logger:
        if name not in self._loggers:
            logger = logging.getLogger(f"{self.name}.{name}")
            logger.setLevel(logging.DEBUG)

            for handler in self._handlers:
                if handler not in logger.handlers:
                    logger.addHandler(handler)

            self._loggers[name] = logger

        return self._loggers[name]

    def log(
        self,
        level: LogLevel,
        category: LogCategory,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = LogEntry(
            timestamp=time.time(),
            level=level,
            category=category,
            message=message,
            context=context or {},
            source=source,
            thread_id=str(os.getpid()),
            request_id=request_id,
            user_id=user_id,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

        self._log_entries.append(entry)

        if len(self._log_entries) > self._max_entries:
            self._log_entries = self._log_entries[-self._max_entries:]

        logger = self.get_logger(category.value)
        log_level = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }[level]

        extra = {
            "category": category.value,
            "context": entry.context,
        }

        logger.log(log_level, message, extra=extra)

        for listener in self._listeners:
            try:
                listener(entry)
            except Exception as e:
                logger.error(f"Error notifying log listener: {e}")

    def debug(
        self,
        category: LogCategory,
        message: str,
        **kwargs
    ) -> None:
        self.log(LogLevel.DEBUG, category, message, **kwargs)

    def info(
        self,
        category: LogCategory,
        message: str,
        **kwargs
    ) -> None:
        self.log(LogLevel.INFO, category, message, **kwargs)

    def warning(
        self,
        category: LogCategory,
        message: str,
        **kwargs
    ) -> None:
        self.log(LogLevel.WARNING, category, message, **kwargs)

    def error(
        self,
        category: LogCategory,
        message: str,
        **kwargs
    ) -> None:
        self.log(LogLevel.ERROR, category, message, **kwargs)

    def critical(
        self,
        category: LogCategory,
        message: str,
        **kwargs
    ) -> None:
        self.log(LogLevel.CRITICAL, category, message, **kwargs)

    def add_listener(self, listener: Callable[[LogEntry], None]) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[LogEntry], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def get_entries(
        self,
        level: Optional[LogLevel] = None,
        category: Optional[LogCategory] = None,
        limit: int = 100,
        since: Optional[float] = None,
    ) -> List[LogEntry]:
        entries = self._log_entries

        if level:
            entries = [e for e in entries if e.level == level]

        if category:
            entries = [e for e in entries if e.category == category]

        if since:
            entries = [e for e in entries if e.timestamp >= since]

        return entries[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        if not self._log_entries:
            return {"total_entries": 0}

        by_level = {level.value: 0 for level in LogLevel}
        by_category = {cat.value: 0 for cat in LogCategory}

        for entry in self._log_entries:
            by_level[entry.level.value] += 1
            by_category[entry.category.value] += 1

        return {
            "total_entries": len(self._log_entries),
            "by_level": by_level,
            "by_category": by_category,
            "time_range": {
                "start": self._log_entries[0].timestamp,
                "end": self._log_entries[-1].timestamp,
            },
        }

    def clear_entries(self) -> None:
        self._log_entries.clear()

    def export_to_file(
        self,
        filepath: str,
        level: Optional[LogLevel] = None,
        category: Optional[LogCategory] = None,
        since: Optional[float] = None,
    ) -> None:
        entries = self.get_entries(level, category, limit=None, since=since)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([entry.to_dict() for entry in entries], f, ensure_ascii=False, indent=2)


_global_logger: Optional[ButlerLogger] = None


def init_logger(
    name: str = "butler",
    log_dir: Optional[str] = None,
    level: LogLevel = LogLevel.INFO,
    enable_console: bool = True,
    enable_file: bool = True,
) -> ButlerLogger:
    global _global_logger

    if _global_logger is None:
        _global_logger = ButlerLogger(
            name=name,
            log_dir=log_dir,
            level=level,
            enable_console=enable_console,
            enable_file=enable_file,
        )

    return _global_logger


def get_logger() -> ButlerLogger:
    global _global_logger

    if _global_logger is None:
        _global_logger = init_logger()

    return _global_logger


def get_module_logger(module_name: str) -> logging.Logger:
    return get_logger().get_logger(module_name)
