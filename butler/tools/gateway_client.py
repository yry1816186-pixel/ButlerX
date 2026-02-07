from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional

import httpx
import websockets.client
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK


class GatewayClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        token_header: str,
        timeout_sec: int,
        allowlist: Optional[List[str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.token = token
        self.token_header = token_header or "Authorization"
        self.timeout_sec = max(int(timeout_sec), 1)
        self.allowlist = [item for item in (allowlist or []) if item]

    def request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.base_url:
            return {"error": "gateway_not_configured"}
        if not path:
            return {"error": "path_required"}
        if self.allowlist and not any(path.startswith(prefix) for prefix in self.allowlist):
            return {"error": "path_not_allowed", "path": path}

        url = f"{self.base_url}{path}"
        headers = {}
        if self.token:
            if self.token_header.lower() == "authorization":
                headers[self.token_header] = f"Bearer {self.token}"
            else:
                headers[self.token_header] = self.token

        try:
            resp = httpx.request(
                method=method.upper(),
                url=url,
                json=body,
                headers=headers,
                timeout=self.timeout_sec,
            )
            return {
                "status": resp.status_code,
                "text": resp.text,
                "headers": dict(resp.headers),
            }
        except (httpx.HTTPError, httpx.TimeoutException, httpx.ConnectError) as exc:
            return {"error": str(exc)}

    def get(self, path: str) -> Dict[str, Any]:
        return self.request("GET", path)

    def post(self, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.request("POST", path, body)

    def put(self, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.request("PUT", path, body)

    def delete(self, path: str) -> Dict[str, Any]:
        return self.request("DELETE", path)


class GatewayWebSocketClient:
    def __init__(
        self,
        ws_url: str,
        token: Optional[str] = None,
        token_header: str = "Authorization",
        ping_interval: int = 20,
        ping_timeout: int = 20,
        close_timeout: int = 10,
        max_retries: int = 3,
        retry_delay: int = 5,
    ) -> None:
        self.ws_url = ws_url
        self.token = token
        self.token_header = token_header
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.close_timeout = close_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._websocket: Optional[websockets.client.WebSocketClientProtocol] = None
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._message_handlers: List[Callable] = []
        self._error_handlers: List[Callable] = []
        self._close_handlers: List[Callable] = []
        self._connected = False
        self._should_reconnect = True

    def _build_headers(self) -> Dict[str, str]:
        headers = {}
        if self.token:
            if self.token_header.lower() == "authorization":
                headers[self.token_header] = f"Bearer {self.token}"
            else:
                headers[self.token_header] = self.token
        return headers

    async def connect(self) -> bool:
        if self._connected and self._websocket:
            return True

        retry_count = 0
        while retry_count < self.max_retries:
            try:
            self._websocket = await websockets.connect(
                self.ws_url,
                additional_headers=self._build_headers(),
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
                close_timeout=self.close_timeout,
            )
            self._connected = True
            return True
        except (OSError, ConnectionRefusedError, ConnectionError) as e:
            retry_count +=1
            if retry_count < self.max_retries:
                await asyncio.sleep(self.retry_delay)
            else:
                self._call_error_handlers({"error": f"Connection failed after {self.max_retries} retries", "details": str(e)})
                return False
        except (websockets.exceptions.WebSocketException, ValueError) as e:
            self._call_error_handlers({"error": "Unexpected connection error", "details": str(e)})
            return False

    async def disconnect(self) -> None:
        self._should_reconnect = False
        if self._websocket:
            try:
                await self._websocket.close()
            except (websockets.exceptions.WebSocketException, RuntimeError):
                pass
        self._connected = False
        self._websocket = None

    async def send(self, data: Any) -> bool:
        if not self._websocket or not self._connected:
            return False

        try:
            if isinstance(data, (dict, list)):
                message = json.dumps(data)
            else:
                message = str(data)
            
            await self._websocket.send(message)
            return True
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK):
            self._connected = False
            self._call_close_handlers({"code": 1000, "reason": "Connection closed"})
            return False
        except Exception as e:
            self._call_error_handlers({"error": "Send error", "details": str(e)})
            return False

    async def receive(self) -> Optional[Any]:
        if not self._websocket or not self._connected:
            return None

        try:
            message = await self._websocket.recv()
            try:
                return json.loads(message)
            except json.JSONDecodeError:
                return message
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK):
            self._connected = False
            self._call_close_handlers({"code": 1000, "reason": "Connection closed"})
            return None
        except Exception as e:
            self._call_error_handlers({"error": "Receive error", "details": str(e)})
            return None

    def on_event(self, event_type: str) -> Callable:
        def decorator(handler: Callable) -> Callable:
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(handler)
            return handler
        return decorator

    def on_message(self, handler: Callable) -> None:
        self._message_handlers.append(handler)

    def on_error(self, handler: Callable) -> None:
        self._error_handlers.append(handler)

    def on_close(self, handler: Callable) -> None:
        self._close_handlers.append(handler)

    def _call_event_handlers(self, event_type: str, data: Any) -> None:
        for handler in self._event_handlers.get(event_type, []):
            try:
                handler(data)
            except (RuntimeError, ValueError, TypeError):
                pass

    def _call_message_handlers(self, data: Any) -> None:
        for handler in self._message_handlers:
            try:
                handler(data)
            except (RuntimeError, ValueError, TypeError):
                pass

    def _call_error_handlers(self, error: Dict[str, Any]) -> None:
        for handler in self._error_handlers:
            try:
                handler(error)
            except (RuntimeError, ValueError, TypeError):
                pass

    def _call_close_handlers(self, close_info: Dict[str, Any]) -> None:
        for handler in self._close_handlers:
            try:
                handler(close_info)
            except (RuntimeError, ValueError, TypeError):
                pass

    async def listen(self) -> None:
        await self.connect()
        while self._should_reconnect and self._connected:
            try:
                message = await self.receive()
                if message is None:
                    break
                
                if isinstance(message, dict):
                    event_type = message.get("event") or message.get("type")
                    if event_type:
                        self._call_event_handlers(event_type, message)
                    else:
                        self._call_message_handlers(message)
                else:
                    self._call_message_handlers(message)
            except Exception as e:
                self._call_error_handlers({"error": "Listen error", "details": str(e)})
                if self._should_reconnect:
                    await asyncio.sleep(self.retry_delay)
                    await self.connect()

    @property
    def is_connected(self) -> bool:
        return self._connected and self._websocket is not None

    def __enter__(self) -> GatewayWebSocketClient:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if asyncio.get_event_loop().is_running():
            asyncio.create_task(self.disconnect())
        else:
            asyncio.run(self.disconnect())


async def run_gateway_client_async(
    ws_url: str,
    token: Optional[str] = None,
    token_header: str = "Authorization",
    message_handler: Optional[Callable] = None,
    event_handlers: Optional[Dict[str, Callable]] = None,
    error_handler: Optional[Callable] = None,
) -> None:
    client = GatewayWebSocketClient(ws_url, token, token_header)
    
    if message_handler:
        client.on_message(message_handler)
    
    if event_handlers:
        for event_type, handler in event_handlers.items():
            client.on_event(event_type)(handler)
    
    if error_handler:
        client.on_error(error_handler)
    
    await client.listen()
    await client.disconnect()


class GatewayClientV2:
    def __init__(
        self,
        base_url: str,
        token: str,
        token_header: str,
        timeout_sec: int,
        allowlist: Optional[List[str]] = None,
    ) -> None:
        self.http = GatewayClient(base_url, token, token_header, timeout_sec, allowlist)
        
        ws_base_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{ws_base_url}/v1/gateway"
        self.ws: Optional[GatewayWebSocketClient] = None
        self.token = token
        self.token_header = token_header

    def request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.http.request(method, path, body)

    def get(self, path: str) -> Dict[str, Any]:
        return self.http.get(path)

    def post(self, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.http.post(path, body)

    def put(self, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.http.put(path, body)

    def delete(self, path: str) -> Dict[str, Any]:
        return self.http.delete(path)

    def create_websocket_client(self, **kwargs) -> GatewayWebSocketClient:
        return GatewayWebSocketClient(
            self.ws_url,
            self.token,
            self.token_header,
            **kwargs
        )

    async def connect_websocket(self, **kwargs) -> GatewayWebSocketClient:
        client = self.create_websocket_client(**kwargs)
        await client.connect()
        self.ws = client
        return client

    async def disconnect_websocket(self) -> None:
        if self.ws:
            await self.ws.disconnect()
            self.ws = None
