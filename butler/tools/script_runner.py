from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List


class ScriptRunner:
    def __init__(self, script_dir: str, allowlist: List[str], timeout_sec: int) -> None:
        self.script_dir = script_dir or "/app/butler/scripts"
        self.allowlist = set([name for name in allowlist if name])
        self.timeout_sec = max(int(timeout_sec), 1)

    def run(self, script_name: str, args: List[str]) -> Dict[str, Any]:
        if not script_name:
            return {"error": "missing_script"}
        safe_name = os.path.basename(script_name)
        if safe_name != script_name:
            return {"error": "invalid_script_name"}
        if self.allowlist and safe_name not in self.allowlist:
            return {"error": "script_not_allowed", "script": safe_name}
        script_path = os.path.join(self.script_dir, safe_name)
        if not os.path.isfile(script_path):
            return {"error": "script_not_found", "script": safe_name}
        try:
            result = subprocess.run(
                [script_path, *args],
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"error": "timeout", "script": safe_name}
