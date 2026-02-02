from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional

import httpx


class WebSearchClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        query_param: str,
        key_param: str,
        provider: str,
        timeout_sec: int,
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.query_param = query_param or "q"
        self.key_param = key_param or "api_key"
        self.provider = (provider or "").lower()
        self.timeout_sec = max(int(timeout_sec), 1)

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        if not query:
            return {"error": "query_required"}
        limit = max(int(limit), 1)
        if self.api_url:
            return self._search_api(query, limit)
        return self._search_duckduckgo(query, limit)

    def _search_api(self, query: str, limit: int) -> Dict[str, Any]:
        params = {self.query_param: query, "num": limit}
        if self.api_key:
            params[self.key_param] = self.api_key
        try:
            resp = httpx.get(self.api_url, params=params, timeout=self.timeout_sec)
            resp.raise_for_status()
            data = resp.json()
            return {
                "results": self._normalize_results(data, limit),
                "raw": data,
            }
        except Exception as exc:
            return {"error": str(exc)}

    def _normalize_results(self, data: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        if self.provider == "serpapi":
            for item in data.get("organic_results", [])[:limit]:
                results.append(
                    {
                        "title": item.get("title"),
                        "url": item.get("link"),
                        "snippet": item.get("snippet"),
                    }
                )
            return results
        if self.provider == "bing":
            items = ((data.get("webPages") or {}).get("value") or [])[:limit]
            for item in items:
                results.append(
                    {
                        "title": item.get("name"),
                        "url": item.get("url"),
                        "snippet": item.get("snippet"),
                    }
                )
            return results
        # generic: try common keys
        items = data.get("results") or data.get("items") or []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            results.append(
                {
                    "title": item.get("title") or item.get("name"),
                    "url": item.get("url") or item.get("link"),
                    "snippet": item.get("snippet") or item.get("description"),
                }
            )
        return results

    def _search_duckduckgo(self, query: str, limit: int) -> Dict[str, Any]:
        url = "https://duckduckgo.com/html/"
        try:
            resp = httpx.get(url, params={"q": query}, timeout=self.timeout_sec)
            resp.raise_for_status()
        except Exception as exc:
            return {"error": str(exc)}

        results = []
        for match in re.findall(r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>', resp.text):
            link, title = match
            results.append({"title": html.unescape(title), "url": link})
            if len(results) >= limit:
                break
        if not results:
            return {"results": [], "raw_html": resp.text[:1000]}
        return {"results": results}
