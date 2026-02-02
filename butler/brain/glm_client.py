from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


@dataclass
class GLMConfig:
    api_key: str
    base_url: str
    model_text: str
    model_vision: Optional[str]
    timeout_sec: int
    temperature: float
    max_tokens: int
    top_p: float


class GLMClient:
    def __init__(self, config: GLMConfig) -> None:
        self.config = config
        base = (config.base_url or "").rstrip("/")
        self.base_url = base
        self._client = httpx.Client(timeout=config.timeout_sec)

    def close(self) -> None:
        self._client.close()

    def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        if not self.config.api_key:
            raise ValueError("GLM_API_KEY is not configured")
        model_name = model or self.config.model_text
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": self._value_or_default(temperature, self.config.temperature),
            "max_tokens": self._value_or_default(max_tokens, self.config.max_tokens),
            "top_p": self._value_or_default(top_p, self.config.top_p),
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"
        logger.debug("GLM request to %s model=%s", url, model_name)
        try:
            resp = self._client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("GLM request failed: %s", e.response.text if hasattr(e, 'response') else str(e))
            raise ValueError(f"GLM API error: {e.response.status_code}" if hasattr(e, 'response') else str(e)) from e
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.error("GLM connection error: %s", e)
            raise ValueError(f"GLM connection failed: {e}") from e

        try:
            data = resp.json()
        except Exception as e:
            logger.error("Failed to parse GLM response: %s", e)
            raise ValueError(f"Invalid GLM response: {e}") from e
        
        content = self._extract_content(data)
        return content, data

    @staticmethod
    def _value_or_default(value: Optional[Any], default: Any) -> Any:
        return default if value is None else value

    @staticmethod
    def _extract_content(data: Dict[str, Any]) -> str:
        choices = data.get("choices")
        if not choices:
            raise ValueError("GLM response missing choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise ValueError("GLM response missing content")
        return content


def normalize_image_inputs(images: Iterable[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in images:
        if isinstance(item, dict):
            url = item.get("url")
            base64_data = item.get("base64")
            mime = item.get("mime") or "image/jpeg"
        else:
            url = item if isinstance(item, str) else None
            base64_data = None
            mime = "image/jpeg"

        if url and url.startswith("http"):
            normalized.append({"type": "image_url", "image_url": {"url": url}})
            continue

        if base64_data:
            data_url = f"data:{mime};base64,{base64_data}"
            normalized.append({"type": "image_url", "image_url": {"url": data_url}})
            continue

        if isinstance(url, str) and url.strip():
            data_url = f"data:{mime};base64,{url.strip()}"
            normalized.append({"type": "image_url", "image_url": {"url": data_url}})

    return normalized


def try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    trimmed = text.strip()
    if trimmed.startswith("```"):
        trimmed = trimmed.strip("`")
        if trimmed.lower().startswith("json"):
            trimmed = trimmed[4:].strip()
    try:
        return json.loads(trimmed)
    except json.JSONDecodeError:
        start = trimmed.find("{")
        end = trimmed.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = trimmed[start : end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                return None
        return None
