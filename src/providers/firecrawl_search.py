"""Optional Firecrawl search adapter."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from src.config.settings import Settings, get_settings
from src.providers.search_base import SearchProvider, SearchResult, utc_now_iso

FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v2/search"


class FirecrawlSearchProvider(SearchProvider):
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self.settings = settings or get_settings()
        self._client = client

    def is_configured(self) -> bool:
        return bool(self.settings.firecrawl_api_key)

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        if not self.is_configured():
            return []
        payload = {"query": query, "limit": max_results}
        headers = {
            "Authorization": f"Bearer {self.settings.firecrawl_api_key}",
            "Content-Type": "application/json",
        }
        retrieved = utc_now_iso()
        if self._client is not None:
            response = self._client.post(
                FIRECRAWL_SEARCH_URL, json=payload, headers=headers, timeout=30
            )
            response.raise_for_status()
            data = response.json()
        else:
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    FIRECRAWL_SEARCH_URL, json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()
        return self._parse_results(data, retrieved)

    def _parse_results(self, data: dict[str, Any], retrieved_at: str) -> list[SearchResult]:
        results: list[SearchResult] = []
        web_items = (data.get("data") or {}).get("web") or data.get("web") or []
        # Some responses may flatten results under data as a list
        if not web_items and isinstance(data.get("data"), list):
            web_items = data["data"]
        for item in web_items:
            if not isinstance(item, dict):
                continue
            url = (item.get("url") or "").strip()
            if not url:
                continue
            domain = urlparse(url).netloc
            snippet = (
                item.get("description")
                or item.get("snippet")
                or item.get("content")
                or ""
            )
            if isinstance(snippet, list):
                # highlights arrays — join short strings
                snippet = " ".join(str(part) for part in snippet if part)
            results.append(
                SearchResult(
                    title=(item.get("title") or domain or "Source").strip(),
                    url=url,
                    domain=domain,
                    snippet=str(snippet)[:500],
                    retrieved_at=retrieved_at,
                )
            )
        return results
