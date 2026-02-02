from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, Optional


class OpenClawCLI:
    def __init__(self, cli_path: str, env: Optional[Dict[str, Any]] = None) -> None:
        self.cli_path = cli_path or "openclaw"
        self.env = env or {}

    def send_message(
        self,
        target: str,
        message: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}
        if not message:
            return {"error": "missing_message"}

        cmd: List[str] = [self.cli_path, "message", "send", "--target", target, "--message", message]
        if channel:
            cmd.extend(["--channel", channel])
        if account:
            cmd.extend(["--account", account])

        env = os.environ.copy()
        for key, value in self.env.items():
            env[str(key)] = str(value)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except FileNotFoundError:
            return {"error": "openclaw_cli_not_found", "cli_path": self.cli_path}
