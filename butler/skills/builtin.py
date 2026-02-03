from __future__ import annotations

import logging
from typing import Any, Dict

from .skill_base import (
    Skill,
    SkillCategory,
    SkillCommandSpec,
    SkillMetadata,
    SkillContext,
    SkillResult,
    skill,
)

logger = logging.getLogger(__name__)


@skill(
    name="device",
    version="1.0.0",
    author="Butler Team",
    description="设备控制技能",
    category=SkillCategory.DEVICE,
)
class DeviceSkill(Skill):
    metadata = SkillMetadata(
        name="device",
        version="1.0.0",
        author="Butler Team",
        description="设备控制技能",
        category=SkillCategory.DEVICE,
    )

    commands = {
        "turn_on": SkillCommandSpec(
            name="turn_on",
            description="打开设备",
            parameters={
                "device_id": {"type": "string", "description": "设备ID"},
                "brightness": {"type": "number", "description": "亮度 (可选)", "default": 100},
            },
            examples=["打开客厅灯", "turn_on light_living_room"],
        ),
        "turn_off": SkillCommandSpec(
            name="turn_off",
            description="关闭设备",
            parameters={
                "device_id": {"type": "string", "description": "设备ID"},
            },
            examples=["关闭客厅灯", "turn_off light_living_room"],
        ),
        "toggle": SkillCommandSpec(
            name="toggle",
            description="切换设备状态",
            parameters={
                "device_id": {"type": "string", "description": "设备ID"},
            },
            examples=["切换客厅灯", "toggle light_living_room"],
        ),
        "set_brightness": SkillCommandSpec(
            name="set_brightness",
            description="设置设备亮度",
            parameters={
                "device_id": {"type": "string", "description": "设备ID"},
                "brightness": {"type": "number", "description": "亮度 (0-100)"},
            },
            examples=["设置客厅灯亮度为50", "set_brightness light_living_room 50"],
        ),
    }

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.devices: Dict[str, Any] = {}

    async def initialize(self) -> bool:
        logger.info("DeviceSkill initialized")
        return True

    async def shutdown(self) -> bool:
        logger.info("DeviceSkill shut down")
        return True

    async def execute(
        self, command: str, params: Dict[str, Any], context: SkillContext
    ) -> SkillResult:
        try:
            if command == "turn_on":
                return await self._turn_on(params, context)
            elif command == "turn_off":
                return await self._turn_off(params, context)
            elif command == "toggle":
                return await self._toggle(params, context)
            elif command == "set_brightness":
                return await self._set_brightness(params, context)
            else:
                return SkillResult(
                    success=False, error=f"Unknown command: {command}"
                )

        except Exception as e:
            logger.error(f"DeviceSkill error: {e}")
            return SkillResult(success=False, error=str(e))

    async def _turn_on(
        self, params: Dict[str, Any], context: SkillContext
    ) -> SkillResult:
        device_id = params.get("device_id")
        brightness = params.get("brightness", 100)

        if not device_id:
            return SkillResult(success=False, error="Missing device_id parameter")

        self.devices[device_id] = {"state": "on", "brightness": brightness}

        logger.info(f"Turned on device: {device_id} (brightness: {brightness})")

        return SkillResult(
            success=True,
            output=f"已打开设备 {device_id}，亮度 {brightness}%",
        )

    async def _turn_off(
        self, params: Dict[str, Any], context: SkillContext
    ) -> SkillResult:
        device_id = params.get("device_id")

        if not device_id:
            return SkillResult(success=False, error="Missing device_id parameter")

        self.devices[device_id] = {"state": "off", "brightness": 0}

        logger.info(f"Turned off device: {device_id}")

        return SkillResult(
            success=True,
            output=f"已关闭设备 {device_id}",
        )

    async def _toggle(
        self, params: Dict[str, Any], context: SkillContext
    ) -> SkillResult:
        device_id = params.get("device_id")

        if not device_id:
            return SkillResult(success=False, error="Missing device_id parameter")

        current_state = self.devices.get(device_id, {}).get("state", "off")

        if current_state == "on":
            return await self._turn_off(params, context)
        else:
            return await self._turn_on(params, context)

    async def _set_brightness(
        self, params: Dict[str, Any], context: SkillContext
    ) -> SkillResult:
        device_id = params.get("device_id")
        brightness = params.get("brightness")

        if not device_id or brightness is None:
            return SkillResult(success=False, error="Missing device_id or brightness parameter")

        brightness = max(0, min(100, int(brightness)))

        self.devices[device_id] = {"state": "on", "brightness": brightness}

        logger.info(f"Set device {device_id} brightness to {brightness}")

        return SkillResult(
            success=True,
            output=f"已设置设备 {device_id} 亮度为 {brightness}%",
        )


@skill(
    name="notification",
    version="1.0.0",
    author="Butler Team",
    description="通知技能",
    category=SkillCategory.COMMUNICATION,
)
class NotificationSkill(Skill):
    metadata = SkillMetadata(
        name="notification",
        version="1.0.0",
        author="Butler Team",
        description="通知技能",
        category=SkillCategory.COMMUNICATION,
    )

    commands = {
        "send": SkillCommandSpec(
            name="send",
            description="发送通知",
            parameters={
                "message": {"type": "string", "description": "通知消息"},
                "priority": {
                    "type": "string",
                    "description": "优先级 (low/normal/high)",
                    "default": "normal",
                },
            },
            examples=["发送通知: 系统启动成功", "send 系统启动完成"],
        ),
    }

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.notifications: list = []

    async def initialize(self) -> bool:
        logger.info("NotificationSkill initialized")
        return True

    async def shutdown(self) -> bool:
        logger.info("NotificationSkill shut down")
        return True

    async def execute(
        self, command: str, params: Dict[str, Any], context: SkillContext
    ) -> SkillResult:
        try:
            if command == "send":
                return await self._send(params, context)
            else:
                return SkillResult(
                    success=False, error=f"Unknown command: {command}"
                )

        except Exception as e:
            logger.error(f"NotificationSkill error: {e}")
            return SkillResult(success=False, error=str(e))

    async def _send(
        self, params: Dict[str, Any], context: SkillContext
    ) -> SkillResult:
        message = params.get("message")
        priority = params.get("priority", "normal")

        if not message:
            return SkillResult(success=False, error="Missing message parameter")

        notification = {
            "message": message,
            "priority": priority,
            "timestamp": context.timestamp.isoformat(),
        }

        self.notifications.append(notification)

        logger.info(f"Sent notification: {message} (priority: {priority})")

        return SkillResult(
            success=True,
            output=f"已发送通知: {message}",
        )
