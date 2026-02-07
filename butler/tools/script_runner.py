from __future__ import annotations

import logging
import os
import re
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


class ScriptRunner:
    def __init__(self, script_dir: str, allowlist: List[str], timeout_sec: int) -> None:
        self.script_dir = script_dir or "/app/butler/scripts"
        self.allowlist = set([name for name in allowlist if name])
        self.timeout_sec = max(int(timeout_sec), 1)

    def _validate_script_name(self, script_name: str) -> bool:
        if not script_name:
            return False
        safe_name = os.path.basename(script_name)
        if safe_name != script_name:
            return False
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', safe_name):
            logger.warning(f"Invalid script name format: {safe_name}")
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

    def run(self, script_name: str, args: List[str]) -> Dict[str, Any]:
        if not script_name:
            return {"error": "missing_script"}
        
        if not self._validate_script_name(script_name):
            return {"error": "invalid_script_name"}
        
        safe_name = os.path.basename(script_name)
        
        if self.allowlist and safe_name not in self.allowlist:
            logger.warning(f"Script not in allowlist: {safe_name}")
            return {"error": "script_not_allowed", "script": safe_name}
        
        if not self._validate_args(args):
            return {"error": "invalid_arguments"}
        
        script_path = os.path.join(self.script_dir, safe_name)
        if not os.path.isfile(script_path):
            return {"error": "script_not_found", "script": safe_name}
        
        try:
            result = subprocess.run(
                [script_path] + args,
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
        except subprocess.TimeoutExpired:
            logger.error(f"Script timeout: {safe_name}")
            return {"error": "timeout", "script": safe_name}
        except (ValueError, OSError, subprocess.SubprocessError) as e:
            logger.error(f"Script execution error: {e}")
            return {"error": "execution_failed", "detail": str(e)}
