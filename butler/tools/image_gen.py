from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class ImageGenerator:
    def __init__(self, api_url: str, api_key: str, model: str, timeout_sec: int) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.timeout_sec = max(int(timeout_sec), 1)
        self._client = httpx.Client(timeout=self.timeout_sec)

    def __del__(self) -> None:
        """确保HTTP客户端被正确关闭"""
        try:
            if hasattr(self, '_client') and self._client:
                self._client.close()
        except Exception as e:
            logger.warning(f"Error closing ImageGenerator client: {e}")

    def generate(self, prompt: str, size: str = "1024x1024", n: int = 1) -> Dict[str, Any]:
        if not self.api_url:
            return {"error": "image_api_not_configured"}
        if not self.api_key:
            return {"error": "image_api_key_missing"}
        if not prompt:
            return {"error": "prompt_required"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "n": int(n),
            "size": size,
        }
        if self.model:
            payload["model"] = self.model
        try:
            resp = self._client.post(self.api_url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Image generation API error: {e.response.status_code}")
            return {"error": f"api_error_{e.response.status_code}"}
        except httpx.TimeoutException:
            logger.error(f"Image generation timeout after {self.timeout_sec}s")
            return {"error": "timeout"}
        except Exception as exc:
            logger.error(f"Image generation error: {exc}")
            return {"error": str(exc)}
