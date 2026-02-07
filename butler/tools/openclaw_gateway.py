from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict, Optional, Union

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
except ImportError:
    websockets = None
    WebSocketClientProtocol = None


class OpenClawGatewayClient:
    def __init__(
        self,
        url: str = "ws://127.0.0.1:18789",
        token: Optional[str] = None,
        password: Optional[str] = None,
        device_identity: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.url = url
        self.token = token
        self.password = password
        self.device_identity = device_identity or {}
        self.ws: Optional[WebSocketClientProtocol] = None
        self.seq = 0
        self.pending: Dict[str, Any] = {}
        self.event_handlers: Dict[str, Callable] = {}
        self.connected = False

    async def connect(self) -> bool:
        if websockets is None:
            raise RuntimeError("websockets library is required. Install with: pip install websockets")

        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            self.ws = await websockets.connect(
                self.url,
                additional_headers=headers,
            )

            await self._send_hello()
            self.connected = True
            asyncio.create_task(self._listen())
            return True
        except Exception as e:
            return False

    async def _send_hello(self) -> None:
        if not self.ws:
            return

        import hashlib
        import base64

        hello_payload = {
            "type": "hello",
            "seq": self._next_seq(),
            "version": 1,
            "clientName": "butler",
            "clientDisplayName": "Smart Butler",
            "deviceIdentity": self.device_identity,
        }

        if self.password:
            hello_payload["auth"] = {"password": self.password}

        await self.ws.send(json.dumps(hello_payload))

    async def call(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        if not self.connected or not self.ws:
            return {"error": "not_connected"}

        request_id = self._next_seq()
        request_payload = {
            "type": "request",
            "seq": request_id,
            "method": method,
            "params": params or {},
        }

        await self.ws.send(json.dumps(request_payload))

        try:
            response = await asyncio.wait_for(
                self._wait_for_response(request_id),
                timeout=timeout,
            )
            return response
        except asyncio.TimeoutError:
            return {"error": "timeout"}

    async def _wait_for_response(self, request_id: str) -> Dict[str, Any]:
        while request_id not in self.pending:
            await asyncio.sleep(0.01)
        return self.pending.pop(request_id)

    async def _listen(self) -> None:
        if not self.ws:
            return
        try:
            async for message in self.ws:
                data = json.loads(message)
                await self._handle_frame(data)
        except (websockets.exceptions.WebSocketException, json.JSONDecodeError, ConnectionError):
            self.connected = False

    async def _handle_frame(self, data: Dict[str, Any]) -> None:
        frame_type = data.get("type")

        if frame_type == "helloOk":
            self.connected = True
        elif frame_type == "response":
            seq = data.get("seq")
            if seq:
                self.pending[seq] = data
        elif frame_type == "event":
            await self._dispatch_event(data)

    async def _dispatch_event(self, event: Dict[str, Any]) -> None:
        event_name = event.get("event")
        handler = self.event_handlers.get(event_name)
        if handler:
            await handler(event)

    def on_event(self, event_name: str, handler: Callable) -> None:
        self.event_handlers[event_name] = handler

    def _next_seq(self) -> str:
        self.seq += 1
        return str(self.seq)

    async def send_message(
        self,
        target: str,
        message: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        params = {
            "dest": target,
            "message": message,
        }

        if channel:
            params["channel"] = channel
        if account:
            params["account"] = account

        return await self.call("channels.sendMessage", params)

    async def send_media(
        self,
        target: str,
        media: str,
        message: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        params = {
            "dest": target,
            "message": message or "",
            "media": media,
        }

        if channel:
            params["channel"] = channel
        if account:
            params["account"] = account

        return await self.call("channels.sendMessage", params)

    async def reply_to_message(
        self,
        target: str,
        message_id: str,
        message: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        params = {
            "dest": target,
            "message": message,
            "replyTo": message_id,
        }

        if channel:
            params["channel"] = channel
        if account:
            params["account"] = account

        return await self.call("channels.sendMessage", params)

    async def close(self) -> None:
        if self.ws:
            await self.ws.close()
            self.connected = False


class OpenClawGatewaySync:
    def __init__(
        self,
        url: str = "ws://127.0.0.1:18789",
        token: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self.url = url
        self.token = token
        self.password = password
        self._client: Optional[OpenClawGatewayClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def connect(self) -> bool:
        loop = self._get_loop()
        self._client = OpenClawGatewayClient(
            url=self.url,
            token=self.token,
            password=self.password,
        )
        return loop.run_until_complete(self._client.connect())

    def send_message(
        self,
        target: str,
        message: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._client or not self._client.connected:
            return {"error": "not_connected"}

        loop = self._get_loop()
        return loop.run_until_complete(
            self._client.send_message(target, message, channel, account)
        )

    def close(self) -> None:
        if self._client:
            loop = self._get_loop()
            loop.run_until_complete(self._client.close())
