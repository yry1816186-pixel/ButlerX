from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator, constr
from enum import Enum


class CommandPayload(BaseModel):
    command_type: str = Field(..., min_length=1, max_length=100)
    source: Optional[str] = Field("ui", max_length=50)
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    correlation_id: Optional[str] = Field(None, max_length=100)
    
    @validator('command_type')
    def validate_command_type(cls, v):
        allowed_commands = [
            'ptz_goto_preset', 'ptz_patrol', 'snapshot', 'store_event',
            'vision_detect', 'face_enroll', 'face_verify', 'system_exec',
            'script_run', 'image_gen', 'voice_asr', 'voice_tts', 'search',
            'home_assistant', 'email', 'automation', 'habit', 'anomaly',
            'energy', 'ir_send', 'ir_learn', 'dashan', 'device_discovery'
        ]
        if v not in allowed_commands:
            raise ValueError(f"Invalid command_type: {v}")
        return v
    
    @validator('source')
    def validate_source(cls, v):
        if v not in ['ui', 'mqtt', 'api', 'voice', 'automation']:
            raise ValueError(f"Invalid source: {v}")
        return v


class StateUpdatePayload(BaseModel):
    mode: Optional[str] = Field(None, min_length=1, max_length=50)
    privacy_mode: Optional[bool] = None


class SystemExecPayload(BaseModel):
    command: str = Field(..., min_length=1, max_length=255)
    args: List[str] = Field(default_factory=list, max_items=20)
    
    @validator('command')
    def validate_command(cls, v):
        import re
        if not re.match(r'^[a-zA-Z0-9_\-/]+$', v):
            raise ValueError("Invalid command format")
        return v
    
    @validator('args')
    def validate_args(cls, v):
        dangerous_patterns = [
            r'[;&|`$()]',
            r'\$\(.*\)',
            r'`.*`',
            r'\\x[0-9a-fA-F]{2}',
        ]
        for arg in v:
            if not isinstance(arg, str):
                raise ValueError("Arguments must be strings")
            if len(arg) > 1000:
                raise ValueError("Argument too long")
            for pattern in dangerous_patterns:
                import re
                if re.search(pattern, arg):
                    raise ValueError("Potentially dangerous argument")
        return v


class ScriptRunPayload(BaseModel):
    script_name: str = Field(..., min_length=1, max_length=255)
    args: List[str] = Field(default_factory=list, max_items=20)
    
    @validator('script_name')
    def validate_script_name(cls, v):
        import re
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', v):
            raise ValueError("Invalid script name format")
        return v
    
    @validator('args')
    def validate_args(cls, v):
        for arg in v:
            if not isinstance(arg, str):
                raise ValueError("Arguments must be strings")
            if len(arg) > 1000:
                raise ValueError("Argument too long")
        return v


class ImageGenPayload(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    negative_prompt: Optional[str] = Field(None, max_length=1000)
    width: Optional[int] = Field(512, ge=256, le=2048)
    height: Optional[int] = Field(512, ge=256, le=2048)
    steps: Optional[int] = Field(30, ge=10, le=100)
    cfg_scale: Optional[float] = Field(7.0, ge=1.0, le=20.0)
    seed: Optional[int] = Field(None, ge=-1, le=2147483647)


class VoiceASRPayload(BaseModel):
    audio_data: str = Field(..., min_length=1, max_length=10485760)
    format: Optional[str] = Field("wav", pattern='^(wav|mp3|ogg|flac|m4a)$')
    language: Optional[str] = Field(None, max_length=10)
    label: Optional[str] = Field(None, max_length=100)
    prompt: Optional[str] = Field(None, max_length=500)
    voiceprint_id: Optional[str] = Field(None, max_length=100)
    
    @validator('audio_data')
    def validate_audio_data(cls, v):
        try:
            import base64
            decoded = base64.b64decode(v, validate=True)
            if len(decoded) > 10485760:
                raise ValueError("Audio data too large (max 10MB)")
        except Exception as e:
            raise ValueError("Invalid base64 audio data")
        return v


class VoiceTTSPayload(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice: Optional[str] = Field(None, max_length=100)
    rate: Optional[int] = Field(100, ge=50, le=200)
    volume: Optional[int] = Field(100, ge=0, le=100)


class SearchPayload(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    num_results: Optional[int] = Field(5, ge=1, le=20)
    language: Optional[str] = Field(None, max_length=10)


class HomeAssistantPayload(BaseModel):
    domain: str = Field(..., min_length=1, max_length=50)
    service: str = Field(..., min_length=1, max_length=50)
    entity_id: Optional[str] = Field(None, max_length=100)
    service_data: Optional[Dict[str, Any]] = Field(default_factory=dict)


class EmailPayload(BaseModel):
    to: List[str] = Field(..., min_items=1, max_items=50)
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1, max_length=100000)
    cc: Optional[List[str]] = Field(None, max_items=50)
    bcc: Optional[List[str]] = Field(None, max_items=50)
    attachments: Optional[List[str]] = Field(None, max_items=10)
    
    @validator('to', 'cc', 'bcc', pre=True)
    def validate_email_list(cls, v):
        if v is None:
            return None
        import re
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        for email in v:
            if not re.match(email_regex, email):
                raise ValueError(f"Invalid email address: {email}")
        return v


class AutomationRulePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    enabled: bool = True
    trigger: Dict[str, Any] = Field(..., min_items=1)
    actions: List[Dict[str, Any]] = Field(..., min_items=1, max_items=20)
    conditions: Optional[List[Dict[str, Any]]] = Field(None, max_items=20)
    
    @validator('trigger')
    def validate_trigger(cls, v):
        if 'type' not in v:
            raise ValueError("Trigger must have a type")
        return v


class FaceEnrollPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    image_data: str = Field(..., min_length=1, max_length=10485760)
    camera_id: Optional[str] = Field(None, max_length=100)
    
    @validator('image_data')
    def validate_image_data(cls, v):
        try:
            import base64
            decoded = base64.b64decode(v, validate=True)
            if len(decoded) > 10485760:
                raise ValueError("Image data too large (max 10MB)")
        except Exception:
            raise ValueError("Invalid base64 image data")
        return v


class FaceVerifyPayload(BaseModel):
    image_data: str = Field(..., min_length=1, max_length=10485760)
    camera_id: Optional[str] = Field(None, max_length=100)
    
    @validator('image_data')
    def validate_image_data(cls, v):
        try:
            import base64
            decoded = base64.b64decode(v, validate=True)
            if len(decoded) > 10485760:
                raise ValueError("Image data too large (max 10MB)")
        except Exception:
            raise ValueError("Invalid base64 image data")
        return v


class PTZPayload(BaseModel):
    camera_id: str = Field(..., min_length=1, max_length=100)
    preset: Optional[str] = Field(None, max_length=100)
    patrol_presets: Optional[List[str]] = Field(None, max_items=20)
    dwell_sec: Optional[int] = Field(5, ge=1, le=300)


class SnapshotPayload(BaseModel):
    camera_id: str = Field(..., min_length=1, max_length=100)
    width: Optional[int] = Field(None, ge=320, le=4096)
    height: Optional[int] = Field(None, ge=240, le=4096)
    quality: Optional[int] = Field(90, ge=1, le=100)


class VisionDetectPayload(BaseModel):
    images: List[str] = Field(..., min_items=1, max_items=10)
    model: Optional[str] = Field("object", max_length=50)
    min_conf: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_det: Optional[int] = Field(None, ge=1, le=100)
    match_faces: bool = False
    top_k: int = Field(3, ge=1, le=10)


class WebSearchPayload(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(5, ge=1, le=20)
    language: Optional[str] = Field(None, max_length=10)
