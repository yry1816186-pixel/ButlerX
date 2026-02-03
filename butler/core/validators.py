from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum

try:
    from pydantic import BaseModel, Field, validator, field_validator
    from pydantic_core import PydanticUndefinedType
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    Field = lambda **kwargs: kwargs
    validator = lambda *args, **kwargs: lambda func: func
    field_validator = lambda *args, **kwargs: lambda func: func


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ASREngine(str, Enum):
    FASTER_WHISPER = "faster-whisper"
    OPENAI_WHISPER = "openai-whisper"


class EventType(str, Enum):
    DEVICE_STATE_CHANGE = "device_state_change"
    VOICE_COMMAND = "voice_command"
    SCHEDULE = "schedule"
    CUSTOM_EVENT = "custom_event"
    SYSTEM_EVENT = "system_event"


class ActionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Severity(str, Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


class EventPayload(BaseModel if PYDANTIC_AVAILABLE else object):
    device_id: Optional[str] = None
    device_type: Optional[str] = None
    state: Optional[Dict[str, Any]] = None
    command: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    
    if PYDANTIC_AVAILABLE:
        class Config:
            extra = "allow"


class EventInput(BaseModel if PYDANTIC_AVAILABLE else object):
    event_id: str = Field(..., min_length=1, max_length=100)
    ts: int = Field(..., ge=0)
    source: str = Field(..., min_length=1, max_length=100)
    type: EventType
    payload: Optional[EventPayload] = None
    severity: Severity = Severity(0)
    correlation_id: Optional[str] = Field(None, max_length=100)
    
    if PYDANTIC_AVAILABLE:
        @field_validator("ts")
        @classmethod
        def validate_ts(cls, v):
            if v > int(datetime.now().timestamp() * 1000) + 86400000:
                raise ValueError("Timestamp cannot be more than 1 day in the future")
            return v
        
        @field_validator("event_id")
        @classmethod
        def validate_event_id(cls, v):
            if not re.match(r'^[a-zA-Z0-9\-_]+$', v):
                raise ValueError("Event ID must contain only alphanumeric characters, hyphens, and underscores")
            return v


class PlanAction(BaseModel if PYDANTIC_AVAILABLE else object):
    action_type: str = Field(..., min_length=1, max_length=50)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    if PYDANTIC_AVAILABLE:
        class Config:
            extra = "allow"


class PlanInput(BaseModel if PYDANTIC_AVAILABLE else object):
    plan_id: str = Field(..., min_length=1, max_length=100)
    triggered_by_event_id: str = Field(..., min_length=1, max_length=100)
    actions: List[PlanAction] = Field(..., min_items=1)
    policy: str = Field(..., min_length=1, max_length=100)
    reason: Optional[str] = Field(None, max_length=500)
    created_ts: int = Field(..., ge=0)
    
    if PYDANTIC_AVAILABLE:
        @field_validator("plan_id", "triggered_by_event_id")
        @classmethod
        def validate_ids(cls, v):
            if not re.match(r'^[a-zA-Z0-9\-_]+$', v):
                raise ValueError("ID must contain only alphanumeric characters, hyphens, and underscores")
            return v


class ResultInput(BaseModel if PYDANTIC_AVAILABLE else object):
    plan_id: str = Field(..., min_length=1, max_length=100)
    action_type: str = Field(..., min_length=1, max_length=50)
    status: ActionStatus
    output: Dict[str, Any] = Field(default_factory=dict)
    ts: int = Field(..., ge=0)
    
    if PYDANTIC_AVAILABLE:
        @field_validator("plan_id")
        @classmethod
        def validate_plan_id(cls, v):
            if not re.match(r'^[a-zA-Z0-9\-_]+$', v):
                raise ValueError("Plan ID must contain only alphanumeric characters, hyphens, and underscores")
            return v


class ScheduleInput(BaseModel if PYDANTIC_AVAILABLE else object):
    schedule_id: str = Field(..., min_length=1, max_length=100)
    run_at: int = Field(..., ge=0)
    actions: List[PlanAction] = Field(..., min_items=1)
    status: ActionStatus = ActionStatus.PENDING
    created_ts: int = Field(..., ge=0)
    note: Optional[str] = Field(None, max_length=500)
    
    if PYDANTIC_AVAILABLE:
        @field_validator("schedule_id")
        @classmethod
        def validate_schedule_id(cls, v):
            if not re.match(r'^[a-zA-Z0-9\-_]+$', v):
                raise ValueError("Schedule ID must contain only alphanumeric characters, hyphens, and underscores")
            return v


class VoiceCommandInput(BaseModel if PYDANTIC_AVAILABLE else object):
    command: str = Field(..., min_length=1, max_length=1000)
    language: str = Field("zh-CN", max_length=10)
    confidence: float = Field(..., ge=0.0, le=1.0)
    
    if PYDANTIC_AVAILABLE:
        @field_validator("command")
        @classmethod
        def validate_command(cls, v):
            if not v.strip():
                raise ValueError("Command cannot be empty or whitespace only")
            return v.strip()


class DeviceStateInput(BaseModel if PYDANTIC_AVAILABLE else object):
    device_id: str = Field(..., min_length=1, max_length=100)
    state: Dict[str, Any] = Field(..., min_items=1)
    timestamp: Optional[int] = Field(None, ge=0)
    
    if PYDANTIC_AVAILABLE:
        @field_validator("device_id")
        @classmethod
        def validate_device_id(cls, v):
            if not re.match(r'^[a-zA-Z0-9\-_:]+$', v):
                raise ValueError("Device ID must contain only alphanumeric characters, hyphens, underscores, and colons")
            return v


class SkillInput(BaseModel if PYDANTIC_AVAILABLE else object):
    skill_name: str = Field(..., min_length=1, max_length=50)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    if PYDANTIC_AVAILABLE:
        @field_validator("skill_name")
        @classmethod
        def validate_skill_name(cls, v):
            if not re.match(r'^[a-zA-Z0-9_]+$', v):
                raise ValueError("Skill name must contain only alphanumeric characters and underscores")
            return v.lower()


class APIKeyInput(BaseModel if PYDANTIC_AVAILABLE else object):
    service: str = Field(..., min_length=1, max_length=50)
    api_key: str = Field(..., min_length=10, max_length=500)
    
    if PYDANTIC_AVAILABLE:
        @field_validator("api_key")
        @classmethod
        def validate_api_key(cls, v):
            if v in ["", "your_api_key_here", "your_glm_api_key_here"]:
                raise ValueError("API key cannot be empty or a placeholder")
            return v


class MemoryChunkInput(BaseModel if PYDANTIC_AVAILABLE else object):
    content: str = Field(..., min_length=1, max_length=10000)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    tags: Optional[List[str]] = Field(default_factory=list)
    source: Optional[str] = Field(None, max_length=100)
    
    if PYDANTIC_AVAILABLE:
        @field_validator("content")
        @classmethod
        def validate_content(cls, v):
            if not v.strip():
                raise ValueError("Content cannot be empty or whitespace only")
            return v.strip()
        
        @field_validator("tags")
        @classmethod
        def validate_tags(cls, v):
            if v:
                for tag in v:
                    if not re.match(r'^[a-zA-Z0-9\-_\u4e00-\u9fa5]+$', tag):
                        raise ValueError(f"Tag '{tag}' contains invalid characters")
            return v


class VectorSearchInput(BaseModel if PYDANTIC_AVAILABLE else object):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(10, ge=1, le=100)
    min_score: float = Field(0.5, ge=0.0, le=1.0)
    
    if PYDANTIC_AVAILABLE:
        @field_validator("query")
        @classmethod
        def validate_query(cls, v):
            if not v.strip():
                raise ValueError("Query cannot be empty or whitespace only")
            return v.strip()


class ValidationError(BaseModel if PYDANTIC_AVAILABLE else object):
    field: str
    message: str
    value: Any = None


class ValidationResult(BaseModel if PYDANTIC_AVAILABLE else object):
    is_valid: bool
    errors: List[ValidationError] = Field(default_factory=list)
    data: Optional[Dict[str, Any]] = None


def validate_event(data: Dict[str, Any]) -> ValidationResult:
    try:
        if PYDANTIC_AVAILABLE:
            event = EventInput(**data)
            return ValidationResult(is_valid=True, data=event.model_dump())
        else:
            basic_validation(data, ["event_id", "ts", "source", "type"])
            return ValidationResult(is_valid=True, data=data)
    except Exception as e:
        return ValidationResult(is_valid=False, errors=[ValidationError(field="general", message=str(e))])


def validate_plan(data: Dict[str, Any]) -> ValidationResult:
    try:
        if PYDANTIC_AVAILABLE:
            plan = PlanInput(**data)
            return ValidationResult(is_valid=True, data=plan.model_dump())
        else:
            basic_validation(data, ["plan_id", "triggered_by_event_id", "actions", "policy"])
            return ValidationResult(is_valid=True, data=data)
    except Exception as e:
        return ValidationResult(is_valid=False, errors=[ValidationError(field="general", message=str(e))])


def validate_result(data: Dict[str, Any]) -> ValidationResult:
    try:
        if PYDANTIC_AVAILABLE:
            result = ResultInput(**data)
            return ValidationResult(is_valid=True, data=result.model_dump())
        else:
            basic_validation(data, ["plan_id", "action_type", "status", "ts"])
            return ValidationResult(is_valid=True, data=data)
    except Exception as e:
        return ValidationResult(is_valid=False, errors=[ValidationError(field="general", message=str(e))])


def validate_schedule(data: Dict[str, Any]) -> ValidationResult:
    try:
        if PYDANTIC_AVAILABLE:
            schedule = ScheduleInput(**data)
            return ValidationResult(is_valid=True, data=schedule.model_dump())
        else:
            basic_validation(data, ["schedule_id", "run_at", "actions"])
            return ValidationResult(is_valid=True, data=data)
    except Exception as e:
        return ValidationResult(is_valid=False, errors=[ValidationError(field="general", message=str(e))])


def validate_voice_command(data: Dict[str, Any]) -> ValidationResult:
    try:
        if PYDANTIC_AVAILABLE:
            cmd = VoiceCommandInput(**data)
            return ValidationResult(is_valid=True, data=cmd.model_dump())
        else:
            basic_validation(data, ["command", "confidence"])
            return ValidationResult(is_valid=True, data=data)
    except Exception as e:
        return ValidationResult(is_valid=False, errors=[ValidationError(field="general", message=str(e))])


def validate_device_state(data: Dict[str, Any]) -> ValidationResult:
    try:
        if PYDANTIC_AVAILABLE:
            state = DeviceStateInput(**data)
            return ValidationResult(is_valid=True, data=state.model_dump())
        else:
            basic_validation(data, ["device_id", "state"])
            return ValidationResult(is_valid=True, data=data)
    except Exception as e:
        return ValidationResult(is_valid=False, errors=[ValidationError(field="general", message=str(e))])


def basic_validation(data: Dict[str, Any], required_fields: List[str]):
    missing = [f for f in required_fields if f not in data or data[f] is None]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def sanitize_string(value: str, max_length: int = 1000) -> str:
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    if len(value) > max_length:
        value = value[:max_length]
    return value


def sanitize_dict(data: Dict[str, Any], max_keys: int = 100) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    if len(data) > max_keys:
        data = dict(list(data.items())[:max_keys])
    return {k: sanitize_string(str(k), 100): v for k, v in data.items()}
