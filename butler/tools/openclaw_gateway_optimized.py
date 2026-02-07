"""Optimized OpenClaw Gateway client with reconnection and retry support."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
except ImportError:
    websockets = None
    WebSocketClientProtocol = None

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """States of the WebSocket connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSING = "closing"
    ERROR = "error"


@dataclass
class GatewayConfig:
    """Configuration for OpenClaw Gateway client.

    Attributes:
        url: WebSocket URL for the gateway
        token: Bearer token for authentication
        password: Password for authentication
        device_identity: Device identity information
        reconnect_interval_sec: Initial reconnection interval
        max_reconnect_interval_sec: Maximum reconnection interval
        heartbeat_interval_sec: Heartbeat interval in seconds
        request_timeout_sec: Default request timeout
        max_retries: Maximum number of retries for failed requests
        enable_auto_reconnect: Whether to automatically reconnect
    """

    url: str = "ws://127.0.0.1:18789"
    token: Optional[str] = None
    password: Optional[str] = None
    device_identity: Dict[str, Any] = field(default_factory=dict)
    reconnect_interval_sec: float = 1.0
    max_reconnect_interval_sec: float = 60.0
    heartbeat_interval_sec: float = 30.0
    request_timeout_sec: float = 30.0
    max_retries: int = 3
    enable_auto_reconnect: bool = True


@dataclass
class RequestResult:
    """Result of a gateway request.

    Attributes:
        success: Whether the request succeeded
        data: Response data if successful
        error: Error message if failed
        retry_count: Number of retries attempted
    """

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0


class OpenClawGatewayClientOptimized:
    """Optimized OpenClaw Gateway WebSocket client.

    Features:
    - Automatic reconnection with exponential backoff
    - Heartbeat/keepalive mechanism
    - Request queue with timeout
    - Connection state management
    - Retry mechanism for failed requests
    - Event handling with callbacks
    """

    def __init__(self, config: Optional[GatewayConfig] = None) -> None:
        """Initialize the gateway client.

        Args:
            config: Gateway configuration, uses defaults if None
        """
        self.config = config or GatewayConfig()

        if websockets is None:
            raise RuntimeError(
                "websockets library is required. Install with: pip install websockets"
            )

        self.ws: Optional[WebSocketClientProtocol] = None
        self.seq = 0
        self.state = ConnectionState.DISCONNECTED

        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.request_timeout = self.config.request_timeout_sec

        self.event_handlers: Dict[str, List[Callable]] = {}
        self.state_handlers: Dict[ConnectionState, List[Callable]] = {}

        self._reconnect_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._reconnect_count = 0
        self._last_heartbeat: Optional[datetime] = None

    async def connect(self) -> bool:
        """Connect to the OpenClaw Gateway.

        Returns:
            True if connection succeeded, False otherwise
        """
        if self.state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            return True

        self.state = ConnectionState.CONNECTING
        self._notify_state_change(ConnectionState.CONNECTING)

        headers = {}
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"

        try:
            logger.info("Connecting to OpenClaw Gateway at %s", self.config.url)
            self.ws = await websockets.connect(
                self.config.url,
                additional_headers=headers,
                ping_interval=self.config.heartbeat_interval_sec,
                ping_timeout=10.0,
                close_timeout=10.0,
            )

            await self._send_hello()

            self.state = ConnectionState.CONNECTED
            self._reconnect_count = 0
            self._notify_state_change(ConnectionState.CONNECTED)

            logger.info("Successfully connected to OpenClaw Gateway")

            self._listen_task = asyncio.create_task(self._listen())
            self._heartbeat_task = asyncio.create_task(self._heartbeat())

            return True

        except Exception as exc:
            logger.error("Failed to connect to OpenClaw Gateway: %s", exc)
            self.state = ConnectionState.ERROR
            self._notify_state_change(ConnectionState.ERROR)

            if self.config.enable_auto_reconnect:
                self._start_reconnect()

            return False

    async def disconnect(self) -> None:
        """Disconnect from the OpenClaw Gateway."""
        logger.info("Disconnecting from OpenClaw Gateway")
        self.state = ConnectionState.CLOSING
        self._notify_state_change(ConnectionState.CLOSING)

        self.config.enable_auto_reconnect = False

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        if self.ws:
            await self.ws.close()

        self.ws = None
        self.state = ConnectionState.DISCONNECTED
        self._notify_state_change(ConnectionState.DISCONNECTED)

        logger.info("Disconnected from OpenClaw Gateway")

    async def call(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> RequestResult:
        """Call a gateway method.

        Args:
            method: Method name to call
            params: Parameters for the method
            timeout: Request timeout in seconds

        Returns:
            RequestResult with the response or error
        """
        if not self._is_connected():
            return RequestResult(
                success=False,
                error=f"Not connected (state: {self.state.value})",
            )

        timeout = timeout or self.config.request_timeout_sec
        retry_count = 0
        last_error = None

        while retry_count <= self.config.max_retries:
            try:
                request_id = self._next_seq()
                request_payload = {
                    "type": "request",
                    "seq": request_id,
                    "method": method,
                    "params": params or {},
                }

                await self.ws.send(json.dumps(request_payload))

                future = asyncio.Future()
                self.pending_requests[request_id] = future

                try:
                    response = await asyncio.wait_for(future, timeout=timeout)
                    return RequestResult(
                        success=True,
                        data=response,
                        retry_count=retry_count,
                    )
                except asyncio.TimeoutError:
                    del self.pending_requests[request_id]
                    last_error = "timeout"
                    retry_count += 1
                    logger.warning(
                        "Request timed out for method %s (attempt %d/%d)",
                        method,
                        retry_count,
                        self.config.max_retries,
                    )

            except Exception as exc:
                last_error = str(exc)
                retry_count += 1
                logger.warning(
                    "Request failed for method %s: %s (attempt %d/%d)",
                    method,
                    exc,
                    retry_count,
                    self.config.max_retries,
                )

                if retry_count <= self.config.max_retries:
                    await asyncio.sleep(1.0 * retry_count)

        return RequestResult(
            success=False,
            error=last_error or "max_retries_exceeded",
            retry_count=retry_count,
        )

    async def send_message(
        self,
        target: str,
        message: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> RequestResult:
        """Send a message through a channel.

        Args:
            target: Destination target
            message: Message content
            channel: Optional channel specification
            account: Optional account specification

        Returns:
            RequestResult with the response or error
        """
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
    ) -> RequestResult:
        """Send media through a channel.

        Args:
            target: Destination target
            media: Media content URL or base64
            message: Optional message text
            channel: Optional channel specification
            account: Optional account specification

        Returns:
            RequestResult with the response or error
        """
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
    ) -> RequestResult:
        """Reply to a message.

        Args:
            target: Destination target
            message_id: ID of message to reply to
            message: Reply message content
            channel: Optional channel specification
            account: Optional account specification

        Returns:
            RequestResult with the response or error
        """
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

    def on_event(self, event_name: str, handler: Callable) -> None:
        """Register an event handler.

        Args:
            event_name: Name of the event to handle
            handler: Callback function for the event
        """
        if event_name not in self.event_handlers:
            self.event_handlers[event_name] = []
        self.event_handlers[event_name].append(handler)

    def on_state_change(self, state: ConnectionState, handler: Callable) -> None:
        """Register a state change handler.

        Args:
            state: State to watch
            handler: Callback function for state change
        """
        if state not in self.state_handlers:
            self.state_handlers[state] = []
        self.state_handlers[state].append(handler)

    def remove_event_handler(self, event_name: str, handler: Callable) -> None:
        """Remove an event handler.

        Args:
            event_name: Name of the event
            handler: Callback function to remove
        """
        if event_name in self.event_handlers:
            handlers = self.event_handlers[event_name]
            if handler in handlers:
                handlers.remove(handler)
            if not handlers:
                del self.event_handlers[event_name]

    def _is_connected(self) -> bool:
        """Check if the client is connected."""
        return (
            self.state == ConnectionState.CONNECTED
            and self.ws is not None
            and not self.ws.closed
        )

    async def _send_hello(self) -> None:
        """Send hello message to gateway."""
        if not self.ws:
            return

        hello_payload = {
            "type": "hello",
            "seq": self._next_seq(),
            "version": 1,
            "clientName": "butler",
            "clientDisplayName": "Smart Butler",
            "deviceIdentity": self.config.device_identity,
        }

        if self.config.password:
            hello_payload["auth"] = {"password": self.config.password}

        await self.ws.send(json.dumps(hello_payload))
        logger.debug("Sent hello message to gateway")

    async def _listen(self) -> None:
        """Listen for messages from the gateway."""
        if not self.ws:
            return

        logger.debug("Starting to listen for gateway messages")

        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self._handle_frame(data)
                except json.JSONDecodeError as exc:
                    logger.error("Failed to decode JSON message: %s", exc)
                except Exception as exc:
                    logger.error("Error handling frame: %s", exc)

        except websockets.exceptions.ConnectionClosed as exc:
            logger.warning("Gateway connection closed: %s", exc)
            self._handle_disconnect()

        except Exception as exc:
            logger.error("Error in listen loop: %s", exc)
            self._handle_disconnect()

    async def _handle_frame(self, data: Dict[str, Any]) -> None:
        """Handle a frame from the gateway.

        Args:
            data: Frame data as dictionary
        """
        frame_type = data.get("type")

        if frame_type == "helloOk":
            logger.debug("Received helloOk from gateway")
            self.state = ConnectionState.CONNECTED
            self._notify_state_change(ConnectionState.CONNECTED)

        elif frame_type == "response":
            seq = data.get("seq")
            if seq:
                future = self.pending_requests.pop(seq, None)
                if future:
                    future.set_result(data)
                else:
                    logger.warning("Received response for unknown request ID: %s", seq)

        elif frame_type == "event":
            await self._dispatch_event(data)

        else:
            logger.warning("Unknown frame type: %s", frame_type)

    async def _dispatch_event(self, event: Dict[str, Any]) -> None:
        """Dispatch an event to registered handlers.

        Args:
            event: Event data
        """
        event_name = event.get("event")
        handlers = self.event_handlers.get(event_name, [])

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as exc:
                logger.error("Error in event handler for %s: %s", event_name, exc)

    async def _heartbeat(self) -> None:
        """Send periodic heartbeats to keep connection alive."""
        logger.debug("Starting heartbeat task")

        while self._is_connected():
            try:
                await asyncio.sleep(self.config.heartbeat_interval_sec)

                if self._is_connected():
                    await self.ws.ping()
                    self._last_heartbeat = datetime.now()

            except Exception as exc:
                logger.error("Heartbeat error: %s", exc)
                self._handle_disconnect()
                break

    def _handle_disconnect(self) -> None:
        """Handle disconnection event."""
        logger.warning("Disconnected from gateway")

        self.state = ConnectionState.DISCONNECTED
        self._notify_state_change(ConnectionState.DISCONNECTED)

        for future in self.pending_requests.values():
            future.cancel()
        self.pending_requests.clear()

        if self.config.enable_auto_reconnect:
            self._start_reconnect()

    def _start_reconnect(self) -> None:
        """Start automatic reconnection."""
        if self._reconnect_task and not self._reconnect_task.done():
            return

        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        logger.info("Started reconnection task")

    async def _reconnect_loop(self) -> None:
        """Reconnection loop with exponential backoff."""
        self.state = ConnectionState.RECONNECTING
        self._notify_state_change(ConnectionState.RECONNECTING)

        while self.config.enable_auto_reconnect and self.state != ConnectionState.CONNECTED:
            interval = min(
                self.config.reconnect_interval_sec * (2 ** self._reconnect_count),
                self.config.max_reconnect_interval_sec,
            )

            logger.info(
                "Reconnecting in %.1f seconds (attempt %d)",
                interval,
                self._reconnect_count + 1,
            )

            await asyncio.sleep(interval)

            if await self.connect():
                self._reconnect_count = 0
                break
            else:
                self._reconnect_count += 1

    def _notify_state_change(self, new_state: ConnectionState) -> None:
        """Notify state change handlers.

        Args:
            new_state: New connection state
        """
        handlers = self.state_handlers.get(new_state, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(new_state))
                else:
                    handler(new_state)
            except Exception as exc:
                logger.error("Error in state change handler: %s", exc)

    def _next_seq(self) -> str:
        """Generate next sequence number."""
        self.seq += 1
        return str(self.seq)


class OpenClawGatewaySyncOptimized:
    """Synchronous wrapper for the optimized gateway client."""

    def __init__(self, config: Optional[GatewayConfig] = None) -> None:
        """Initialize the sync wrapper.

        Args:
            config: Gateway configuration
        """
        self.config = config or GatewayConfig()
        self._client: Optional[OpenClawGatewayClientOptimized] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = asyncio.Lock()

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create event loop."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def connect(self) -> bool:
        """Connect to the gateway.

        Returns:
            True if connection succeeded, False otherwise
        """
        loop = self._get_loop()

        async def _connect() -> bool:
            self._client = OpenClawGatewayClientOptimized(self.config)
            return await self._client.connect()

        return loop.run_until_complete(_connect())

    def disconnect(self) -> None:
        """Disconnect from the gateway."""
        if self._client:
            loop = self._get_loop()
            loop.run_until_complete(self._client.disconnect())

    def send_message(
        self,
        target: str,
        message: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a message through a channel.

        Args:
            target: Destination target
            message: Message content
            channel: Optional channel specification
            account: Optional account specification

        Returns:
            Response data or error dictionary
        """
        if not self._client:
            return {"error": "not_connected"}

        loop = self._get_loop()

        async def _send() -> RequestResult:
            return await self._client.send_message(target, message, channel, account)

        result = loop.run_until_complete(_send())

        if result.success and result.data:
            return result.data
        return {"error": result.error or "unknown_error"}

    def send_media(
        self,
        target: str,
        media: str,
        message: Optional[str] = None,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send media through a channel.

        Args:
            target: Destination target
            media: Media content URL or base64
            message: Optional message text
            channel: Optional channel specification
            account: Optional account specification

        Returns:
            Response data or error dictionary
        """
        if not self._client:
            return {"error": "not_connected"}

        loop = self._get_loop()

        async def _send() -> RequestResult:
            return await self._client.send_media(target, media, message, channel, account)

        result = loop.run_until_complete(_send())

        if result.success and result.data:
            return result.data
        return {"error": result.error or "unknown_error"}

    def reply_to_message(
        self,
        target: str,
        message_id: str,
        message: str,
        channel: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reply to a message.

        Args:
            target: Destination target
            message_id: ID of message to reply to
            message: Reply message content
            channel: Optional channel specification
            account: Optional account specification

        Returns:
            Response data or error dictionary
        """
        if not self._client:
            return {"error": "not_connected"}

        loop = self._get_loop()

        async def _reply() -> RequestResult:
            return await self._client.reply_to_message(target, message_id, message, channel, account)

        result = loop.run_until_complete(_reply())

        if result.success and result.data:
            return result.data
        return {"error": result.error or "unknown_error"}
