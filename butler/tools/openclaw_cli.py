from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, List, Optional, Union


class OpenClawCLI:
    def __init__(self, cli_path: str, env: Optional[Dict[str, Any]] = None) -> None:
        self.cli_path = cli_path or "openclaw"
        self.env = env or {}

    def _run_command(self, cmd: List[str]) -> Dict[str, Any]:
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

        return self._run_command(cmd)

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

    def poll(
        self,
        target: str,
        question: str,
        options: List[str],
        channel: Optional[str] = None,
        account: Optional[str] = None,
        multi: bool = False,
        duration_hours: Optional[int] = None,
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}
        if not question:
            return {"error": "missing_poll_question"}
        if not options:
            return {"error": "missing_poll_options"}

        cmd: List[str] = [self.cli_path, "message", "poll", "--target", target, "--poll-question", question]

        for opt in options:
            cmd.extend(["--poll-option", opt])

        if multi:
            cmd.append("--poll-multi")

        if duration_hours is not None:
            cmd.extend(["--poll-duration-hours", str(duration_hours)])

        if message:
            cmd.extend(["--message", message])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def react(
        self,
        target: str,
        message_id: str,
        emoji: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
        remove: bool = False,
        participant: Optional[str] = None,
        from_me: bool = False,
        target_author: Optional[str] = None,
        target_author_uuid: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}
        if not message_id:
            return {"error": "missing_message_id"}

        cmd: List[str] = [self.cli_path, "message", "react", "--target", target, "--message-id", message_id]

        if emoji:
            cmd.extend(["--emoji", emoji])

        if remove:
            cmd.append("--remove")

        if participant:
            cmd.extend(["--participant", participant])

        if from_me:
            cmd.append("--from-me")

        if target_author:
            cmd.extend(["--target-author", target_author])

        if target_author_uuid:
            cmd.extend(["--target-author-uuid", target_author_uuid])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def get_reactions(
        self,
        target: str,
        message_id: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}
        if not message_id:
            return {"error": "missing_message_id"}

        cmd: List[str] = [self.cli_path, "message", "reactions", "--target", target, "--message-id", message_id]

        if limit:
            cmd.extend(["--limit", str(limit)])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def read_messages(
        self,
        target: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
        limit: Optional[int] = None,
        before: Optional[str] = None,
        after: Optional[str] = None,
        around: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}

        cmd: List[str] = [self.cli_path, "message", "read", "--target", target]

        if limit:
            cmd.extend(["--limit", str(limit)])

        if before:
            cmd.extend(["--before", before])

        if after:
            cmd.extend(["--after", after])

        if around:
            cmd.extend(["--around", around])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def edit_message(
        self,
        target: str,
        message_id: str,
        message: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}
        if not message_id:
            return {"error": "missing_message_id"}
        if not message:
            return {"error": "missing_message"}

        cmd: List[str] = [self.cli_path, "message", "edit", "--target", target, "--message-id", message_id, "--message", message]

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def delete_message(
        self,
        target: str,
        message_id: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}
        if not message_id:
            return {"error": "missing_message_id"}

        cmd: List[str] = [self.cli_path, "message", "delete", "--target", target, "--message-id", message_id]

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def pin_message(
        self,
        target: str,
        message_id: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}
        if not message_id:
            return {"error": "missing_message_id"}

        cmd: List[str] = [self.cli_path, "message", "pin", "--target", target, "--message-id", message_id]

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def unpin_message(
        self,
        target: str,
        message_id: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}
        if not message_id:
            return {"error": "missing_message_id"}

        cmd: List[str] = [self.cli_path, "message", "unpin", "--target", target, "--message-id", message_id]

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def list_pins(
        self,
        target: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}

        cmd: List[str] = [self.cli_path, "message", "list-pins", "--target", target]

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def thread_create(
        self,
        target: str,
        thread_name: str,
        message_id: Optional[str] = None,
        auto_archive_min: Optional[int] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}
        if not thread_name:
            return {"error": "missing_thread_name"}

        cmd: List[str] = [self.cli_path, "message", "thread-create", "--target", target, "--thread-name", thread_name]

        if message_id:
            cmd.extend(["--message-id", message_id])

        if auto_archive_min is not None:
            cmd.extend(["--auto-archive-min", str(auto_archive_min)])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def thread_list(
        self,
        guild_id: str,
        channel_id: Optional[str] = None,
        include_archived: bool = False,
        before: Optional[str] = None,
        limit: Optional[int] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not guild_id:
            return {"error": "missing_guild_id"}

        cmd: List[str] = [self.cli_path, "message", "thread-list", "--guild-id", guild_id]

        if channel_id:
            cmd.extend(["--channel-id", channel_id])

        if include_archived:
            cmd.append("--include-archived")

        if before:
            cmd.extend(["--before", before])

        if limit:
            cmd.extend(["--limit", str(limit)])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def thread_reply(
        self,
        target: str,
        message: str,
        media: Optional[str] = None,
        reply_to: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}
        if not message:
            return {"error": "missing_message"}

        cmd: List[str] = [self.cli_path, "message", "thread-reply", "--target", target, "--message", message]

        if media:
            cmd.extend(["--media", media])

        if reply_to:
            cmd.extend(["--reply-to", reply_to])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def emoji_list(
        self,
        guild_id: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        cmd: List[str] = [self.cli_path, "message", "emoji-list"]

        if guild_id:
            cmd.extend(["--guild-id", guild_id])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def emoji_upload(
        self,
        guild_id: str,
        emoji_name: str,
        media: str,
        role_ids: Optional[List[str]] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not guild_id:
            return {"error": "missing_guild_id"}
        if not emoji_name:
            return {"error": "missing_emoji_name"}
        if not media:
            return {"error": "missing_media"}

        cmd: List[str] = [self.cli_path, "message", "emoji-upload", "--guild-id", guild_id, "--emoji-name", emoji_name, "--media", media]

        if role_ids:
            for role_id in role_ids:
                cmd.extend(["--role-ids", role_id])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def sticker_send(
        self,
        target: str,
        sticker_ids: List[str],
        message: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}
        if not sticker_ids:
            return {"error": "missing_sticker_ids"}

        cmd: List[str] = [self.cli_path, "message", "sticker", "--target", target]

        for sticker_id in sticker_ids:
            cmd.extend(["--sticker-id", sticker_id])

        if message:
            cmd.extend(["--message", message])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def sticker_upload(
        self,
        guild_id: str,
        sticker_name: str,
        sticker_desc: str,
        sticker_tags: str,
        media: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not guild_id:
            return {"error": "missing_guild_id"}
        if not sticker_name:
            return {"error": "missing_sticker_name"}
        if not sticker_desc:
            return {"error": "missing_sticker_desc"}
        if not sticker_tags:
            return {"error": "missing_sticker_tags"}
        if not media:
            return {"error": "missing_media"}

        cmd: List[str] = [self.cli_path, "message", "sticker-upload", "--guild-id", guild_id, "--sticker-name", sticker_name, "--sticker-desc", sticker_desc, "--sticker-tags", sticker_tags, "--media", media]

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def broadcast(
        self,
        targets: List[str],
        message: Optional[str] = None,
        media: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        if not targets:
            return {"error": "missing_targets"}
        if not message and not media:
            return {"error": "missing_message_or_media"}

        cmd: List[str] = [self.cli_path, "message", "broadcast"]

        for target in targets:
            cmd.extend(["--targets", target])

        if message:
            cmd.extend(["--message", message])

        if media:
            cmd.extend(["--media", media])

        if dry_run:
            cmd.append("--dry-run")

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def search(
        self,
        guild_id: str,
        query: str,
        channel_id: Optional[str] = None,
        channel_ids: Optional[List[str]] = None,
        author_id: Optional[str] = None,
        author_ids: Optional[List[str]] = None,
        limit: Optional[int] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not guild_id:
            return {"error": "missing_guild_id"}
        if not query:
            return {"error": "missing_query"}

        cmd: List[str] = [self.cli_path, "message", "search", "--guild-id", guild_id, "--query", query]

        if channel_id:
            cmd.extend(["--channel-id", channel_id])

        if channel_ids:
            for cid in channel_ids:
                cmd.extend(["--channel-ids", cid])

        if author_id:
            cmd.extend(["--author-id", author_id])

        if author_ids:
            for aid in author_ids:
                cmd.extend(["--author-ids", aid])

        if limit:
            cmd.extend(["--limit", str(limit)])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def member_info(
        self,
        user_id: str,
        guild_id: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not user_id:
            return {"error": "missing_user_id"}

        cmd: List[str] = [self.cli_path, "message", "member-info", "--user-id", user_id]

        if guild_id:
            cmd.extend(["--guild-id", guild_id])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def role_info(
        self,
        guild_id: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not guild_id:
            return {"error": "missing_guild_id"}

        cmd: List[str] = [self.cli_path, "message", "role-info", "--guild-id", guild_id]

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def role_add(
        self,
        guild_id: str,
        user_id: str,
        role_id: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not guild_id:
            return {"error": "missing_guild_id"}
        if not user_id:
            return {"error": "missing_user_id"}
        if not role_id:
            return {"error": "missing_role_id"}

        cmd: List[str] = [self.cli_path, "message", "role-add", "--guild-id", guild_id, "--user-id", user_id, "--role-id", role_id]

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def role_remove(
        self,
        guild_id: str,
        user_id: str,
        role_id: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not guild_id:
            return {"error": "missing_guild_id"}
        if not user_id:
            return {"error": "missing_user_id"}
        if not role_id:
            return {"error": "missing_role_id"}

        cmd: List[str] = [self.cli_path, "message", "role-remove", "--guild-id", guild_id, "--user-id", user_id, "--role-id", role_id]

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account"])

        return self._run_command(cmd)

    def channel_info(
        self,
        target: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}

        cmd: List[str] = [self.cli_path, "message", "channel-info", "--target", target]

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def channel_list(
        self,
        guild_id: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not guild_id:
            return {"error": "missing_guild_id"}

        cmd: List[str] = [self.cli_path, "message", "channel-list", "--guild-id", guild_id]

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def channel_create(
        self,
        guild_id: str,
        name: str,
        channel_type: Optional[str] = None,
        parent_id: Optional[str] = None,
        position: Optional[int] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not guild_id:
            return {"error": "missing_guild_id"}
        if not name:
            return {"error": "missing_name"}

        cmd: List[str] = [self.cli_path, "message", "channel-create", "--guild-id", guild_id, "--name", name]

        if channel_type:
            cmd.extend(["--type", channel_type])

        if parent_id:
            cmd.extend(["--parent-id", parent_id])

        if position is not None:
            cmd.extend(["--position", str(position)])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def channel_edit(
        self,
        target: str,
        name: Optional[str] = None,
        channel_type: Optional[str] = None,
        parent_id: Optional[str] = None,
        position: Optional[int] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}

        cmd: List[str] = [self.cli_path, "message", "channel-edit", "--target", target]

        if name:
            cmd.extend(["--name", name])

        if channel_type:
            cmd.extend(["--type", channel_type])

        if parent_id:
            cmd.extend(["--parent-id", parent_id])

        if position is not None:
            cmd.extend(["--position", str(position)])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def channel_delete(
        self,
        target: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not target:
            return {"error": "missing_target"}

        cmd: List[str] = [self.cli_path, "message", "channel-delete", "--target", target]

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def voice_status(
        self,
        guild_id: str,
        user_id: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not guild_id:
            return {"error": "missing_guild_id"}

        cmd: List[str] = [self.cli_path, "message", "voice-status", "--guild-id", guild_id]

        if user_id:
            cmd.extend(["--user-id", user_id])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def event_list(
        self,
        guild_id: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not guild_id:
            return {"error": "missing_guild_id"}

        cmd: List[str] = [self.cli_path, "message", "event-list", "--guild-id", guild_id]

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def event_create(
        self,
        guild_id: str,
        event_name: str,
        start_time: str,
        end_time: Optional[str] = None,
        description: Optional[str] = None,
        channel_id: Optional[str] = None,
        location: Optional[str] = None,
        event_type: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not guild_id:
            return {"error": "missing_guild_id"}
        if not event_name:
            return {"error": "missing_event_name"}
        if not start_time:
            return {"error": "missing_start_time"}

        cmd: List[str] = [self.cli_path, "message", "event-create", "--guild-id", guild_id, "--event-name", event_name, "--start-time", start_time]

        if end_time:
            cmd.extend(["--end-time", end_time])

        if description:
            cmd.extend(["--desc", description])

        if channel_id:
            cmd.extend(["--channel-id", channel_id])

        if location:
            cmd.extend(["--location", location])

        if event_type:
            cmd.extend(["--event-type", event_type])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def timeout(
        self,
        guild_id: str,
        user_id: str,
        duration_min: Optional[int] = None,
        until: Optional[str] = None,
        reason: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not guild_id:
            return {"error": "missing_guild_id"}
        if not user_id:
            return {"error": "missing_user_id"}

        cmd: List[str] = [self.cli_path, "message", "timeout", "--guild-id", guild_id, "--user-id", user_id]

        if duration_min is not None:
            cmd.extend(["--duration-min", str(duration_min)])

        if until:
            cmd.extend(["--until", until])

        if reason:
            cmd.extend(["--reason", reason])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def kick(
        self,
        guild_id: str,
        user_id: str,
        reason: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not guild_id:
            return {"error": "missing_guild_id"}
        if not user_id:
            return {"error": "missing_user_id"}

        cmd: List[str] = [self.cli_path, "message", "kick", "--guild-id", guild_id, "--user-id", user_id]

        if reason:
            cmd.extend(["--reason", reason])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def ban(
        self,
        guild_id: str,
        user_id: str,
        delete_days: Optional[int] = None,
        reason: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not guild_id:
            return {"error": "missing_guild_id"}
        if not user_id:
            return {"error": "missing_user_id"}

        cmd: List[str] = [self.cli_path, "message", "ban", "--guild-id", guild_id, "--user-id", user_id]

        if delete_days is not None:
            cmd.extend(["--delete-days", str(delete_days)])

        if reason:
            cmd.extend(["--reason", reason])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)

    def set_presence(
        self,
        presence: str,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not presence:
            return {"error": "missing_presence"}

        cmd: List[str] = [self.cli_path, "message", "set-presence", "--presence", presence]

        if status:
            cmd.extend(["--status", status])

        if channel:
            cmd.extend(["--channel", channel])

        if account:
            cmd.extend(["--account", account])

        return self._run_command(cmd)
