from __future__ import annotations

import logging
import re
import shlex
import subprocess
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


DANGEROUS_PATTERNS = [
    r'[;&|`$()]',
    r'\$\(.*\)',
    r'`.*`',
    r'\\x[0-9a-fA-F]{2}',
    r'\$[a-zA-Z_][a-zA-Z0-9_]*',
]


class SystemExec:
    def __init__(self, allowlist: List[str], timeout_sec: int) -> None:
        self.allowlist = set([cmd for cmd in allowlist if cmd])
        self.timeout_sec = max(int(timeout_sec), 1)
        logger.info(f"SystemExec initialized with {len(self.allowlist)} allowed commands")

    def _validate_command(self, command: str) -> bool:
        if not command:
            return False
        if not re.match(r'^[a-zA-Z0-9_\-/]+$', command):
            logger.warning(f"Invalid command format: {command}")
            return False
        return True

    def _validate_args(self, args: List[str]) -> bool:
        for arg in (args or []):
            if not isinstance(arg, str):
                logger.warning(f"Non-string argument provided: {arg}")
                return False
            
            for pattern in DANGEROUS_PATTERNS:
                if re.search(pattern, arg):
                    logger.warning(f"Potentially dangerous argument detected: {arg}")
                    return False
            
            if '\x00' in arg:
                logger.warning("Null byte detected in argument")
                return False
        
        return True

    def run(self, command: str, args: List[str]) -> Dict[str, Any]:
        if not command:
            logger.warning("Empty command provided to SystemExec")
            return {"error": "missing_command"}
        
        if not self._validate_command(command):
            return {"error": "invalid_command", "command": command}
        
        if self.allowlist and command not in self.allowlist:
            logger.warning(f"Command not in allowlist: {command}")
            return {"error": "command_not_allowed", "command": command}
        
        if not self._validate_args(args):
            return {"error": "invalid_arguments"}
        
        try:
            result = subprocess.run(
                [command] + args,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
                shell=False,
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
        except (ValueError, OSError, subprocess.SubprocessError) as e:
            logger.error(f"SystemExec error: {e}")
            return {"error": "execution_failed", "detail": str(e)}
