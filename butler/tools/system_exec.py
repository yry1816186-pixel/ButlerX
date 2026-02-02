from __future__ import annotations

import logging
import subprocess
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class SystemExec:
    def __init__(self, allowlist: List[str], timeout_sec: int) -> None:
        self.allowlist = set([cmd for cmd in allowlist if cmd])
        self.timeout_sec = max(int(timeout_sec), 1)
        # 记录allowlist配置
        logger.info(f"SystemExec initialized with {len(self.allowlist)} allowed commands")

    def run(self, command: str, args: List[str]) -> Dict[str, Any]:
        if not command:
            logger.warning("Empty command provided to SystemExec")
            return {"error": "missing_command"}
        
        if self.allowlist and command not in self.allowlist:
            logger.warning(f"Command not in allowlist: {command}")
            return {"error": "command_not_allowed", "command": command}
        
        # 验证args不包含危险字符
        for arg in (args or []):
            if not isinstance(arg, str):
                logger.warning(f"Non-string argument provided: {arg}")
                return {"error": "invalid_arguments"}
        
        try:
            result = subprocess.run(
                [command, *args],
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except FileNotFoundError:
            logger.error(f"Command not found: {command}")
            return {"error": "command_not_found", "command": command}
        except subprocess.TimeoutExpired:
            logger.error(f"Command timeout: {command}")
            return {"error": "timeout", "command": command}
        except Exception as e:
            logger.error(f"SystemExec error: {e}")
            return {"error": "execution_failed", "detail": str(e)}
