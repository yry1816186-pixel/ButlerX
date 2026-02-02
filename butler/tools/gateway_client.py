from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx


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
        except Exception as exc:
            return {"error": str(exc)}
