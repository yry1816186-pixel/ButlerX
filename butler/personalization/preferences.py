from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class PreferenceType(Enum):
    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    ENUM = "enum"
    LIST = "list"
    DICT = "dict"
    TIME = "time"
    COLOR = "color"


class PreferenceCategory(Enum):
    SYSTEM = "system"
    AUTOMATION = "automation"
    DEVICE = "device"
    SCENARIO = "scenario"
    UI = "ui"
    NOTIFICATION = "notification"
    VOICE = "voice"
    PRIVACY = "privacy"
    CUSTOM = "custom"


@dataclass
class PreferenceOption:
    value: Any
    label: str
    description: str = ""
    icon: Optional[str] = None


@dataclass
class PreferenceDefinition:
    preference_id: str
    name: str
    description: str
    category: PreferenceCategory
    preference_type: PreferenceType
    default_value: Any
    options: Optional[List[PreferenceOption]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    validation_regex: Optional[str] = None
    required: bool = False
    readonly: bool = False
    visible: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        if self.readonly:
            return False, "This preference is readonly"

        if self.required and value is None:
            return False, "This preference is required"

        if value is None:
            return True, None

        if self.preference_type == PreferenceType.BOOLEAN:
            if not isinstance(value, bool):
                return False, "Value must be a boolean"

        elif self.preference_type == PreferenceType.INTEGER:
            if not isinstance(value, int):
                return False, "Value must be an integer"
            if self.min_value is not None and value < self.min_value:
                return False, f"Value must be >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Value must be <= {self.max_value}"

        elif self.preference_type == PreferenceType.FLOAT:
            if not isinstance(value, (int, float)):
                return False, "Value must be a number"
            value = float(value)
            if self.min_value is not None and value < self.min_value:
                return False, f"Value must be >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Value must be <= {self.max_value}"

        elif self.preference_type == PreferenceType.STRING:
            if not isinstance(value, str):
                return False, "Value must be a string"
            if self.validation_regex:
                import re
                if not re.match(self.validation_regex, value):
                    return False, f"Value does not match pattern: {self.validation_regex}"

        elif self.preference_type == PreferenceType.ENUM:
            if self.options:
                valid_values = [opt.value for opt in self.options]
                if value not in valid_values:
                    return False, f"Value must be one of: {valid_values}"

        elif self.preference_type == PreferenceType.LIST:
            if not isinstance(value, list):
                return False, "Value must be a list"

        elif self.preference_type == PreferenceType.DICT:
            if not isinstance(value, dict):
                return False, "Value must be a dictionary"

        return True, None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preference_id": self.preference_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "type": self.preference_type.value,
            "default_value": self.default_value,
            "options": [
                {
                    "value": opt.value,
                    "label": opt.label,
                    "description": opt.description,
                    "icon": opt.icon,
                }
                for opt in (self.options or [])
            ],
            "min_value": self.min_value,
            "max_value": self.max_value,
            "validation_regex": self.validation_regex,
            "required": self.required,
            "readonly": self.readonly,
            "visible": self.visible,
            "metadata": self.metadata,
        }


@dataclass
class PreferenceValue:
    preference_id: str
    value: Any
    updated_at: float = field(default_factory=time.time)
    updated_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preference_id": self.preference_id,
            "value": self.value,
            "updated_at": self.updated_at,
            "updated_by": self.updated_by,
            "metadata": self.metadata,
        }


class PreferenceManager:
    def __init__(self):
        self.definitions: Dict[str, PreferenceDefinition] = {}
        self.values: Dict[str, PreferenceValue] = {}
        self.change_listeners: List[Callable[[str, Any, Any], None]] = []

        self._init_default_definitions()

    def _init_default_definitions(self) -> None:
        definitions = [
            PreferenceDefinition(
                preference_id="system.language",
                name="系统语言",
                description="系统界面和语音响应的语言",
                category=PreferenceCategory.SYSTEM,
                preference_type=PreferenceType.ENUM,
                default_value="zh-CN",
                options=[
                    PreferenceOption(value="zh-CN", label="简体中文"),
                    PreferenceOption(value="zh-TW", label="繁體中文"),
                    PreferenceOption(value="en-US", label="English"),
                ],
            ),
            PreferenceDefinition(
                preference_id="system.timezone",
                name="时区",
                description="系统使用的时区",
                category=PreferenceCategory.SYSTEM,
                preference_type=PreferenceType.STRING,
                default_value="Asia/Shanghai",
                required=True,
            ),
            PreferenceDefinition(
                preference_id="system.auto_update",
                name="自动更新",
                description="是否自动检查和安装系统更新",
                category=PreferenceCategory.SYSTEM,
                preference_type=PreferenceType.BOOLEAN,
                default_value=True,
            ),
            PreferenceDefinition(
                preference_id="automation.auto_activate",
                name="自动激活自动化",
                description="是否自动激活符合条件的自动化",
                category=PreferenceCategory.AUTOMATION,
                preference_type=PreferenceType.BOOLEAN,
                default_value=True,
            ),
            PreferenceDefinition(
                preference_id="automation.default_priority",
                name="默认自动化优先级",
                description="新创建的自动化的默认优先级",
                category=PreferenceCategory.AUTOMATION,
                preference_type=PreferenceType.INTEGER,
                default_value=5,
                min_value=0,
                max_value=10,
            ),
            PreferenceDefinition(
                preference_id="device.auto_discovery",
                name="自动设备发现",
                description="是否自动发现网络中的新设备",
                category=PreferenceCategory.DEVICE,
                preference_type=PreferenceType.BOOLEAN,
                default_value=True,
            ),
            PreferenceDefinition(
                preference_id="device.offline_timeout",
                name="设备离线超时",
                description="设备离线多久后视为不可用（秒）",
                category=PreferenceCategory.DEVICE,
                preference_type=PreferenceType.INTEGER,
                default_value=300,
                min_value=60,
                max_value=3600,
            ),
            PreferenceDefinition(
                preference_id="scenario.transition_delay",
                name="场景切换延迟",
                description="场景切换时的延迟时间（秒）",
                category=PreferenceCategory.SCENARIO,
                preference_type=PreferenceType.FLOAT,
                default_value=2.0,
                min_value=0.0,
                max_value=10.0,
            ),
            PreferenceDefinition(
                preference_id="ui.theme",
                name="界面主题",
                description="用户界面的颜色主题",
                category=PreferenceCategory.UI,
                preference_type=PreferenceType.ENUM,
                default_value="light",
                options=[
                    PreferenceOption(value="light", label="浅色"),
                    PreferenceOption(value="dark", label="深色"),
                    PreferenceOption(value="auto", label="自动"),
                ],
            ),
            PreferenceDefinition(
                preference_id="ui.dashboard_layout",
                name="仪表板布局",
                description="主仪表板的布局方式",
                category=PreferenceCategory.UI,
                preference_type=PreferenceType.ENUM,
                default_value="grid",
                options=[
                    PreferenceOption(value="grid", label="网格"),
                    PreferenceOption(value="list", label="列表"),
                    PreferenceOption(value="compact", label="紧凑"),
                ],
            ),
            PreferenceDefinition(
                preference_id="notification.enable_push",
                name="启用推送通知",
                description="是否接收推送通知",
                category=PreferenceCategory.NOTIFICATION,
                preference_type=PreferenceType.BOOLEAN,
                default_value=True,
            ),
            PreferenceDefinition(
                preference_id="notification.min_priority",
                name="通知最低优先级",
                description="只显示此优先级及以上的通知",
                category=PreferenceCategory.NOTIFICATION,
                preference_type=PreferenceType.ENUM,
                default_value="medium",
                options=[
                    PreferenceOption(value="low", label="低"),
                    PreferenceOption(value="medium", label="中"),
                    PreferenceOption(value="high", label="高"),
                ],
            ),
            PreferenceDefinition(
                preference_id="voice.wake_word",
                name="唤醒词",
                description="语音助手的唤醒词",
                category=PreferenceCategory.VOICE,
                preference_type=PreferenceType.STRING,
                default_value="小管家",
                validation_regex=r"^[\u4e00-\u9fa5a-zA-Z\s]{2,10}$",
                required=True,
            ),
            PreferenceDefinition(
                preference_id="voice.sensitivity",
                name="语音灵敏度",
                description="语音识别的灵敏度",
                category=PreferenceCategory.VOICE,
                preference_type=PreferenceType.INTEGER,
                default_value=70,
                min_value=0,
                max_value=100,
            ),
            PreferenceDefinition(
                preference_id="privacy.collect_analytics",
                name="收集分析数据",
                description="是否收集匿名使用数据以改进服务",
                category=PreferenceCategory.PRIVACY,
                preference_type=PreferenceType.BOOLEAN,
                default_value=False,
            ),
            PreferenceDefinition(
                preference_id="privacy.share_usage",
                name="共享使用统计",
                description="是否与开发者共享使用统计信息",
                category=PreferenceCategory.PRIVACY,
                preference_type=PreferenceType.BOOLEAN,
                default_value=False,
            ),
        ]

        for definition in definitions:
            self.definitions[definition.preference_id] = definition

        logger.info(f"Initialized {len(definitions)} preference definitions")

    def register_definition(self, definition: PreferenceDefinition) -> None:
        self.definitions[definition.preference_id] = definition
        logger.info(f"Registered preference definition: {definition.preference_id}")

    def unregister_definition(self, preference_id: str) -> bool:
        if preference_id in self.definitions:
            del self.definitions[preference_id]
            return True
        return False

    def get_definition(self, preference_id: str) -> Optional[PreferenceDefinition]:
        return self.definitions.get(preference_id)

    def get_definitions(self, category: Optional[PreferenceCategory] = None) -> List[PreferenceDefinition]:
        definitions = list(self.definitions.values())

        if category:
            definitions = [d for d in definitions if d.category == category]

        return definitions

    def get_value(self, preference_id: str, default: Any = None) -> Any:
        if preference_id in self.values:
            return self.values[preference_id].value

        definition = self.definitions.get(preference_id)
        if definition:
            return definition.default_value

        return default

    def set_value(
        self,
        preference_id: str,
        value: Any,
        updated_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, Optional[str]]:
        definition = self.definitions.get(preference_id)
        if not definition:
            return False, f"Preference definition not found: {preference_id}"

        is_valid, error_message = definition.validate(value)
        if not is_valid:
            return False, error_message

        old_value = self.get_value(preference_id)

        self.values[preference_id] = PreferenceValue(
            preference_id=preference_id,
            value=value,
            updated_by=updated_by,
            metadata=metadata or {},
        )

        logger.info(f"Preference updated: {preference_id} = {value}")

        for listener in self.change_listeners:
            try:
                listener(preference_id, old_value, value)
            except Exception as e:
                logger.error(f"Error in preference change listener: {e}")

        return True, None

    def reset_value(self, preference_id: str) -> bool:
        if preference_id in self.values:
            old_value = self.values[preference_id].value
            del self.values[preference_id]

            definition = self.definitions.get(preference_id)
            if definition:
                new_value = definition.default_value

                for listener in self.change_listeners:
                    try:
                        listener(preference_id, old_value, new_value)
                    except Exception as e:
                        logger.error(f"Error in preference change listener: {e}")

                logger.info(f"Preference reset: {preference_id}")
                return True

        return False

    def reset_all(self) -> None:
        self.values.clear()
        logger.info("All preferences reset to defaults")

    def add_change_listener(self, listener: Callable[[str, Any, Any], None]) -> None:
        self.change_listeners.append(listener)

    def remove_change_listener(self, listener: Callable[[str, Any, Any], None]) -> None:
        if listener in self.change_listeners:
            self.change_listeners.remove(listener)

    def to_dict(self, include_values: bool = True) -> Dict[str, Any]:
        result = {
            "definitions": {
                pref_id: definition.to_dict()
                for pref_id, definition in self.definitions.items()
            },
        }

        if include_values:
            result["values"] = {
                pref_id: value.to_dict()
                for pref_id, value in self.values.items()
            }

        return result

    def save_to_file(self, filepath: str) -> None:
        data = {
            "values": [
                value.to_dict() for value in self.values.values()
            ],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Preferences saved to {filepath}")

    def load_from_file(self, filepath: str) -> None:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            for value_data in data.get("values", []):
                preference_id = value_data["preference_id"]
                value = value_data["value"]

                definition = self.definitions.get(preference_id)
                if definition:
                    is_valid, _ = definition.validate(value)
                    if is_valid:
                        self.values[preference_id] = PreferenceValue(
                            preference_id=preference_id,
                            value=value,
                            updated_at=value_data.get("updated_at", time.time()),
                            updated_by=value_data.get("updated_by"),
                            metadata=value_data.get("metadata", {}),
                        )

            logger.info(f"Preferences loaded from {filepath}")
        except Exception as e:
            logger.error(f"Error loading preferences from {filepath}: {e}")
