from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .ir_controller import IRCommand, IRProtocol

logger = logging.getLogger(__name__)


@dataclass
class LearningSession:
    session_id: str
    device_id: str
    command_name: str
    start_time: float
    learned_commands: List[IRCommand] = field(default_factory=list)
    status: str = "learning"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "device_id": self.device_id,
            "command_name": self.command_name,
            "start_time": self.start_time,
            "learned_commands": [cmd.to_dict() for cmd in self.learned_commands],
            "status": self.status,
            "metadata": self.metadata,
        }


class IRLearner:
    def __init__(self, use_broadlink: bool = False, use_lirc: bool = False) -> None:
        self.active_sessions: Dict[str, LearningSession] = {}
        self.session_history: List[LearningSession] = []
        self.use_broadlink = use_broadlink
        self.use_lirc = use_lirc

    def start_learning_session(
        self,
        device_id: str,
        command_name: str
    ) -> LearningSession:
        import uuid
        session = LearningSession(
            session_id=str(uuid.uuid4()),
            device_id=device_id,
            command_name=command_name,
            start_time=time.time(),
            status="learning",
        )
        self.active_sessions[session.session_id] = session
        logger.info(f"Started IR learning session: {session.session_id}")
        return session

    def learn_command(
        self,
        session_id: str,
        duration: float = 5.0
    ) -> Dict[str, Any]:
        result = {
            "success": False,
            "message": "",
            "session_id": session_id,
            "command": None,
            "timestamp": time.time(),
        }

        session = self.active_sessions.get(session_id)
        if not session:
            result["message"] = "学习会话不存在"
            return result

        try:
            command = self._capture_ir_signal(session, duration)
            if command:
                session.learned_commands.append(command)
                session.status = "completed"
                session.metadata["completed_at"] = time.time()
                
                del self.active_sessions[session_id]
                self.session_history.append(session)
                
                result["success"] = True
                result["message"] = f"成功学习命令: {command.name}"
                result["command"] = command.to_dict()
                logger.info(f"Learned IR command: {command.name}")
            else:
                result["message"] = "未能捕获红外信号，请重试"
        except Exception as e:
            logger.error(f"IR learning failed: {e}")
            result["message"] = f"学习命令时出错: {str(e)}"

        return result

    def _capture_ir_signal(
        self,
        session: LearningSession,
        duration: float
    ) -> Optional[IRCommand]:
        import uuid
        
        if self.use_broadlink:
            return self._capture_broadlink(session, duration)
        elif self.use_lirc:
            return self._capture_lirc(session, duration)
        else:
            logger.warning("No IR receiver configured, simulating capture")
            return IRCommand(
                command_id=str(uuid.uuid4()),
                name=session.command_name,
                protocol=IRProtocol.NEC,
                code="0xFF00FF00",
                raw_data=[1, 2, 3, 4],
            )

    def _capture_broadlink(
        self,
        session: LearningSession,
        duration: float
    ) -> Optional[IRCommand]:
        try:
            import broadlink
            import struct
            
            device_ip = "192.168.1.100"
            device = broadlink.gendevice(device_ip, 0x4eb5)
            device.auth()
            
            device.enter_learning()
            time.sleep(duration)
            
            learned_data = device.check_data()
            device.cancel_learning()
            
            if learned_data:
                import uuid
                command = IRCommand(
                    command_id=str(uuid.uuid4()),
                    name=session.command_name,
                    protocol=IRProtocol.RAW,
                    code="",
                    raw_data=list(learned_data),
                )
                return command
            
            return None
        except ImportError:
            logger.error("broadlink library not installed")
            return None
        except Exception as e:
            logger.error(f"Broadlink capture failed: {e}")
            return None

    def _capture_lirc(
        self,
        session: LearningSession,
        duration: float
    ) -> Optional[IRCommand]:
        try:
            import subprocess
            
            lirc_cmd = ["irrecord", "-d", "duration=" + str(int(duration)), session.command_name]
            result = subprocess.run(lirc_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                output = result.stdout
                
                import uuid
                command = IRCommand(
                    command_id=str(uuid.uuid4()),
                    name=session.command_name,
                    protocol=IRProtocol.NEC,
                    code=output,
                )
                return command
            
            return None
        except Exception as e:
            logger.error(f"LIRC capture failed: {e}")
            return None

    def stop_learning_session(self, session_id: str) -> bool:
        session = self.active_sessions.get(session_id)
        if not session:
            return False

        session.status = "cancelled"
        session.metadata["cancelled_at"] = time.time()

        del self.active_sessions[session_id]
        self.session_history.append(session)

        logger.info(f"Stopped IR learning session: {session_id}")
        return True

    def get_session(self, session_id: str) -> Optional[LearningSession]:
        return self.active_sessions.get(session_id)

    def get_active_sessions(self) -> List[LearningSession]:
        return list(self.active_sessions.values())

    def get_session_history(self, limit: int = 50) -> List[LearningSession]:
        return self.session_history[-limit:]

    def get_learned_commands_for_device(
        self,
        device_id: str
    ) -> List[IRCommand]:
        commands = []
        for session in self.session_history:
            if session.device_id == device_id and session.status == "completed":
                commands.extend(session.learned_commands)
        return commands

    def export_learned_commands(
        self,
        device_id: str,
        output_format: str = "json"
    ) -> Dict[str, Any]:
        result = {
            "success": False,
            "message": "",
            "data": None,
        }

        commands = self.get_learned_commands_for_device(device_id)
        if not commands:
            result["message"] = f"没有为设备 {device_id} 学习的命令"
            return result

        try:
            if output_format == "json":
                data = [cmd.to_dict() for cmd in commands]
                result["success"] = True
                result["message"] = f"成功导出 {len(commands)} 个命令"
                result["data"] = data
            else:
                result["message"] = f"不支持的导出格式: {output_format}"
        except Exception as e:
            logger.error(f"Failed to export commands: {e}")
            result["message"] = f"导出命令时出错: {str(e)}"

        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_sessions": [s.to_dict() for s in self.active_sessions.values()],
            "session_count": len(self.active_sessions),
            "history_count": len(self.session_history),
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"IR learner data saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "IRLearner":
        learner = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for session_data in data.get("active_sessions", []):
            learned_commands = []
            for cmd_data in session_data.get("learned_commands", []):
                command = IRCommand(
                    command_id=cmd_data["command_id"],
                    name=cmd_data["name"],
                    protocol=IRProtocol(cmd_data["protocol"]),
                    code=cmd_data["code"],
                    raw_data=cmd_data.get("raw_data"),
                    repeat_count=cmd_data.get("repeat_count", 1),
                    metadata=cmd_data.get("metadata", {}),
                )
                learned_commands.append(command)

            session = LearningSession(
                session_id=session_data["session_id"],
                device_id=session_data["device_id"],
                command_name=session_data["command_name"],
                start_time=session_data["start_time"],
                learned_commands=learned_commands,
                status=session_data.get("status", "completed"),
                metadata=session_data.get("metadata", {}),
            )
            if session.status == "learning":
                learner.active_sessions[session.session_id] = session
            else:
                learner.session_history.append(session)

        logger.info(f"IR learner loaded from {filepath}")
        return learner
