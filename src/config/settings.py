"""Application configuration from environment / Streamlit secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load project `.env` (never commit secrets). `.env.example` is template-only.
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_ENV_PATH, override=False)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is not None and value.strip() != "":
        return value.strip()
    try:
        import streamlit as st

        if hasattr(st, "secrets") and name in st.secrets:
            secret = st.secrets.get(name)
            if secret is not None and str(secret).strip() != "":
                return str(secret).strip()
    except Exception:
        pass
    return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    max_revisions: int = 1
    agent_timeout_seconds: int = 60
    persistence_enabled: bool = True
    max_task_length: int = 4000
    llm_model: str = "openai/gpt-4o-mini"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    firecrawl_api_key: str | None = None
    serpapi_api_key: str | None = None
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    llm_max_retries: int = 2
    structured_output_retries: int = 1

    @property
    def has_llm_credentials(self) -> bool:
        model = self.llm_model.lower()
        if model.startswith("openai/") or model.startswith("gpt-"):
            return bool(self.openai_api_key)
        if model.startswith("anthropic/") or model.startswith("claude"):
            return bool(self.anthropic_api_key)
        return bool(self.openai_api_key or self.anthropic_api_key)

    @property
    def search_configured(self) -> bool:
        return bool(self.firecrawl_api_key)

    @property
    def jobs_search_configured(self) -> bool:
        """True when a SerpAPI key is available for Google Jobs (live job_search)."""
        return bool(self.serpapi_api_key)

    @property
    def provider_display_name(self) -> str:
        model = self.llm_model.lower()
        if model.startswith("anthropic/") or model.startswith("claude"):
            return "anthropic"
        if model.startswith("openai/") or model.startswith("gpt-"):
            return "openai"
        return "litellm"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        max_revisions=_env_int("WORKFORCE_MAX_REVISIONS", 1),
        agent_timeout_seconds=_env_int("WORKFORCE_AGENT_TIMEOUT_SECONDS", 60),
        persistence_enabled=_env_bool("WORKFORCE_PERSISTENCE_ENABLED", True),
        max_task_length=_env_int("WORKFORCE_MAX_TASK_LENGTH", 4000),
        llm_model=_env("WORKFORCE_LLM_MODEL", "openai/gpt-4o-mini") or "openai/gpt-4o-mini",
        openai_api_key=_env("OPENAI_API_KEY"),
        anthropic_api_key=_env("ANTHROPIC_API_KEY"),
        firecrawl_api_key=_env("FIRECRAWL_API_KEY"),
        serpapi_api_key=_env("SERPAPI_API_KEY"),
    )


def clear_settings_cache() -> None:
    get_settings.cache_clear()
