"""LLM provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class ProviderError(Exception):
    """User-safe provider failure."""

    def __init__(self, message: str, *, code: str = "provider_error", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.safe_message = message


@dataclass
class ProviderStatus:
    ready: bool
    provider_name: str
    model_name: str
    message: str


class LLMProvider(ABC):
    @abstractmethod
    def status(self) -> ProviderStatus:
        raise NotImplementedError

    @abstractmethod
    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Return parsed JSON object from the model."""
        raise NotImplementedError
