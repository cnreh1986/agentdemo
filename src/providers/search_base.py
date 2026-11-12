"""Optional search provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class SearchResult:
    title: str
    url: str
    domain: str
    snippet: str
    retrieved_at: str


class SearchProvider(ABC):
    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        raise NotImplementedError


class NullSearchProvider(SearchProvider):
    def is_configured(self) -> bool:
        return False

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return []


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
