from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class IRProtocol(Enum):
    NEC = "nec"
    RC5 = "rc5"
    RC6 = "rc6"
    SONY = "sony"
    SAMSUNG = "samsung"
    RAW = "raw"
    UNKNOWN = "unknown"


@dataclass
class IRCommand:
    command_id: str
    name: str
    protocol: IRProtocol
    code: str
    raw_data: Optional[List[int]] = None
    repeat_count: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "name": self.name,
            "protocol": self.protocol.value,
            "code": self.code,
            "raw_data": self.raw_data,
            "repeat_count": self.repeat_count,
            "metadata": self.metadata,
        }


@dataclass
class IRDevice:
    device_id: str
    name: str
    device_type: str
    brand: Optional[str] = None
    model: Optional[str] = None
    commands: Dict[str, IRCommand] = field(default_factory=dict)
    learned_commands: Dict[str, IRCommand] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_command(self, command: IRCommand) -> None:
        self.commands[command.command_id] = command

    def get_command(self, command_id: str) -> Optional[IRCommand]:
        return self.commands.get(command_id)

    def add_learned_command(self, command: IRCommand) -> None:
        self.learned_commands[command.command_id] = command
        self.commands[command.command_id] = command

    def list_commands(self) -> List[IRCommand]:
        return list(self.commands.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "device_type": self.device_type,
            "brand": self.brand,
            "model": self.model,
            "commands": [cmd.to_dict() for cmd in self.commands.values()],
            "learned_commands": [cmd.to_dict() for cmd in self.learned_commands.values()],
            "metadata": self.metadata,
        }


class IRController:
    def __init__(self, use_broadlink: bool = False, use_lirc: bool = False) -> None:
        self.devices: Dict[str, IRDevice] = {}
        self.use_broadlink = use_broadlink
        self.use_lirc = use_lirc
        self._init_default_devices()

    def _init_default_devices(self) -> None:
        default_devices = [
            IRDevice(
                device_id="tv_samsung",
                name="三星电视",
                device_type="tv",
                brand="Samsung",
            ),
            IRDevice(
                device_id="air_conditioner_midea",
                name="美的空调",
                device_type="air_conditioner",
                brand="Midea",
            ),
            IRDevice(
                device_id="fan_xiaomi",
                name="小米风扇",
                device_type="fan",
                brand="Xiaomi",
            ),
        ]

        for device in default_devices:
            self.add_device(device)

        logger.info(f"Initialized {len(default_devices)} default IR devices")

    def add_device(self, device: IRDevice) -> None:
        self.devices[device.device_id] = device
        logger.info(f"Added IR device: {device.name}")

    def remove_device(self, device_id: str) -> bool:
        if device_id not in self.devices:
            return False
        device = self.devices.pop(device_id)
        logger.info(f"Removed IR device: {device.name}")
        return True

    def get_device(self, device_id: str) -> Optional[IRDevice]:
        return self.devices.get(device_id)

    def list_devices(self, device_type: Optional[str] = None) -> List[IRDevice]:
        devices = list(self.devices.values())
        if device_type:
            devices = [d for d in devices if d.device_type == device_type]
        return devices

    def send_command(
        self,
        device_id: str,
        command_id: str,
        repeat: int = 1
    ) -> Dict[str, Any]:
        result = {
            "success": False,
            "message": "",
            "device_id": device_id,
            "command_id": command_id,
            "timestamp": time.time(),
        }

        device = self.devices.get(device_id)
        if not device:
            result["message"] = f"设备不存在: {device_id}"
            return result

        command = device.get_command(command_id)
        if not command:
            result["message"] = f"命令不存在: {command_id}"
            return result

        try:
            success = self._transmit_ir(command, repeat)
            if success:
                result["success"] = True
                result["message"] = f"成功发送命令: {command.name} 到 {device.name}"
                logger.info(f"Sent IR command {command.name} to {device.name}")
            else:
                result["message"] = f"发送命令失败: {command.name}"
        except Exception as e:
            logger.error(f"Failed to send IR command: {e}")
            result["message"] = f"发送命令时出错: {str(e)}"

        return result

    def _transmit_ir(self, command: IRCommand, repeat: int) -> bool:
        if self.use_broadlink:
            return self._transmit_broadlink(command, repeat)
        elif self.use_lirc:
            return self._transmit_lirc(command, repeat)
        else:
            logger.warning("No IR transmitter configured, simulating transmission")
            return True

    def _transmit_broadlink(self, command: IRCommand, repeat: int) -> bool:
        try:
            import broadlink
            
            device_ip = "192.168.1.100"
            device = broadlink.gendevice(device_ip, 0x4eb5)
            device.auth()
            
            if command.raw_data:
                data = command.raw_data
            else:
                data = self._convert_code_to_data(command)
            
            for _ in range(repeat or command.repeat_count):
                device.send_data(data)
            
            return True
        except ImportError:
            logger.error("broadlink library not installed")
            return False
        except Exception as e:
            logger.error(f"Broadlink transmission failed: {e}")
            return False

    def _transmit_lirc(self, command: IRCommand, repeat: int) -> bool:
        try:
            import subprocess
            
            lirc_cmd = ["irsend", "SEND_ONCE", command.name, command.code]
            
            for _ in range(repeat or command.repeat_count):
                subprocess.run(lirc_cmd, check=True, capture_output=True)
            
            return True
        except Exception as e:
            logger.error(f"LIRC transmission failed: {e}")
            return False

    def _convert_code_to_data(self, command: IRCommand) -> bytes:
        import struct
        
        code = int(command.code, 16) if command.code.startswith("0x") else int(command.code)
        
        if command.protocol == IRProtocol.NEC:
            data = struct.pack(">I", code)
        elif command.protocol == IRProtocol.RAW:
            data = bytes(command.raw_data or [])
        else:
            data = struct.pack(">I", code)
        
        return data

    def send_raw_signal(
        self,
        device_id: str,
        raw_data: List[int],
        repeat: int = 1
    ) -> Dict[str, Any]:
        result = {
            "success": False,
            "message": "",
            "device_id": device_id,
            "timestamp": time.time(),
        }

        device = self.devices.get(device_id)
        if not device:
            result["message"] = f"设备不存在: {device_id}"
            return result

        try:
            import uuid
            command = IRCommand(
                command_id=str(uuid.uuid4()),
                name="raw_signal",
                protocol=IRProtocol.RAW,
                code="",
                raw_data=raw_data,
                repeat_count=repeat,
            )
            
            success = self._transmit_ir(command, repeat)
            if success:
                result["success"] = True
                result["message"] = f"成功发送原始信号到 {device.name}"
            else:
                result["message"] = "发送原始信号失败"
        except Exception as e:
            logger.error(f"Failed to send raw IR signal: {e}")
            result["message"] = f"发送原始信号时出错: {str(e)}"

        return result

    def batch_send_commands(
        self,
        commands: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        results = []
        for cmd in commands:
            device_id = cmd.get("device_id")
            command_id = cmd.get("command_id")
            repeat = cmd.get("repeat", 1)
            result = self.send_command(device_id, command_id, repeat)
            results.append(result)
        return results

    def search_devices(
        self,
        query: str
    ) -> List[IRDevice]:
        query_lower = query.lower()
        return [
            device for device in self.devices.values()
            if (query_lower in device.name.lower() or 
                query_lower in device.device_id.lower() or
                (device.brand and query_lower in device.brand.lower()))
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "devices": [device.to_dict() for device in self.devices.values()],
            "device_count": len(self.devices),
            "broadlink_enabled": self.use_broadlink,
            "lirc_enabled": self.use_lirc,
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"IR controller data saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "IRController":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        controller = cls()
        
        for device_data in data.get("devices", []):
            commands = {}
            for cmd_data in device_data.get("commands", []):
                command = IRCommand(
                    command_id=cmd_data["command_id"],
                    name=cmd_data["name"],
                    protocol=IRProtocol(cmd_data["protocol"]),
                    code=cmd_data["code"],
                    raw_data=cmd_data.get("raw_data"),
                    repeat_count=cmd_data.get("repeat_count", 1),
                    metadata=cmd_data.get("metadata", {}),
                )
                commands[command.command_id] = command

            device = IRDevice(
                device_id=device_data["device_id"],
                name=device_data["name"],
                device_type=device_data["device_type"],
                brand=device_data.get("brand"),
                model=device_data.get("model"),
                commands=commands,
                learned_commands={},
                metadata=device_data.get("metadata", {}),
            )
            controller.add_device(device)

        logger.info(f"IR controller loaded from {filepath}")
        return controller
