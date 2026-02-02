from __future__ import annotations

import json
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
        message: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
        media: Optional[str] = None,
        buttons: Optional[str] = None,
        card: Optional[str] = None,
        reply_to: Optional[str] = None,
        thread_id: Optional[str] = None,
        silent: bool = False,
        gif_playback: bool = False,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}
        if not message and not media:
            return {"error": "missing_message_or_media"}

        cmd: List[str] = [self.cli_path, "message", "send", "--target", target]

        if message:
            cmd.extend(["--message", message])

        if media:
            cmd.extend(["--media", media])

        if buttons:
            cmd.extend(["--buttons", buttons])

        if card:
            cmd.extend(["--card", card])

        if reply_to:
            cmd.extend(["--reply-to", reply_to])

        if thread_id:
            cmd.extend(["--thread-id", thread_id])

        if silent:
            cmd.append("--silent")

        if gif_playback:
            cmd.append("--gif-playback")

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

    def send_with_buttons(
        self,
        target: str,
        message: str,
        buttons: List[Dict[str, Any]],
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.send_message(
            target=target,
            message=message,
            buttons=json.dumps(buttons),
            channel=channel,
            account=account,
        )

    def send_with_media(
        self,
        target: str,
        media: str,
        message: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.send_message(
            target=target,
            message=message,
            media=media,
            channel=channel,
            account=account,
        )

    def reply_to_message(
        self,
        target: str,
        message_id: str,
        message: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.send_message(
            target=target,
            message=message,
            reply_to=message_id,
            channel=channel,
            account=account,
        )

    def send_to_thread(
        self,
        target: str,
        thread_id: str,
        message: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.send_message(
            target=target,
            message=message,
            thread_id=thread_id,
            channel=channel,
            account=account,
        )
