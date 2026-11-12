"""LiteLLM-backed live provider with bounded retries."""

from __future__ import annotations

import json
import re
from typing import Any

from src.config.settings import Settings, get_settings
from src.providers.llm_base import LLMProvider, ProviderError, ProviderStatus

try:
    import litellm
except ImportError:  # pragma: no cover
    litellm = None  # type: ignore


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


class LiteLLMProvider(LLMProvider):
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def status(self) -> ProviderStatus:
        ready = self.settings.has_llm_credentials
        return ProviderStatus(
            ready=ready,
            provider_name=self.settings.provider_display_name,
            model_name=self.settings.llm_model,
            message="Ready" if ready else "Missing provider credentials",
        )

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        if litellm is None:
            raise ProviderError("litellm is not installed.", code="dependency_missing")
        if not self.settings.has_llm_credentials:
            raise ProviderError(
                "Live LLM credentials are missing. Configure the provider key before running Live Mode.",
                code="missing_credentials",
            )

        temp = self.settings.llm_temperature if temperature is None else temperature
        transient_attempts = 1 + max(0, self.settings.llm_max_retries)
        parse_attempts = 1 + max(0, self.settings.structured_output_retries)
        last_error: ProviderError | None = None
        prompt = user_prompt

        for _ in range(transient_attempts):
            try:
                for parse_try in range(parse_attempts):
                    content = self._call(system_prompt, prompt, temp, schema_name)
                    try:
                        return self._parse_json(content)
                    except ProviderError as parse_err:
                        last_error = parse_err
                        if parse_try + 1 >= parse_attempts:
                            raise
                        prompt = (
                            user_prompt
                            + "\n\nReturn ONLY valid JSON matching the required schema. No markdown."
                        )
            except ProviderError as exc:
                last_error = exc
                if not exc.retryable:
                    raise
            except Exception as exc:  # noqa: BLE001
                mapped = self._map_exception(exc)
                last_error = mapped
                if not mapped.retryable:
                    raise mapped from exc

        raise last_error or ProviderError("Provider call failed.", code="provider_error")

    def _call(self, system_prompt: str, user_prompt: str, temperature: float, schema_name: str) -> str:
        assert litellm is not None
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Produce JSON for schema `{schema_name}`.\n"
                    f"Respond with a single JSON object only.\n\n{user_prompt}"
                ),
            },
        ]
        try:
            response = litellm.completion(
                model=self.settings.llm_model,
                messages=messages,
                temperature=temperature,
                max_tokens=self.settings.llm_max_tokens,
                timeout=self.settings.agent_timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            raise self._map_exception(exc) from exc

        try:
            content = response.choices[0].message.content
        except Exception as exc:  # noqa: BLE001
            raise ProviderError("Empty or unreadable model response.", code="empty_response") from exc
        if not content or not str(content).strip():
            raise ProviderError("Empty model response.", code="empty_response")
        return str(content)

    def _parse_json(self, content: str) -> dict[str, Any]:
        text = content.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = _JSON_FENCE.search(text)
            if match:
                try:
                    data = json.loads(match.group(1))
                except json.JSONDecodeError as exc:
                    raise ProviderError(
                        "Model returned invalid JSON. Try again or switch model.",
                        code="invalid_json",
                    ) from exc
            else:
                start = text.find("{")
                end = text.rfind("}")
                if start >= 0 and end > start:
                    try:
                        data = json.loads(text[start : end + 1])
                    except json.JSONDecodeError as exc:
                        raise ProviderError(
                            "Model returned invalid JSON. Try again or switch model.",
                            code="invalid_json",
                        ) from exc
                else:
                    raise ProviderError(
                        "Model returned invalid JSON. Try again or switch model.",
                        code="invalid_json",
                    )
        if not isinstance(data, dict):
            raise ProviderError("Model JSON root must be an object.", code="invalid_json")
        return data

    def _map_exception(self, exc: Exception) -> ProviderError:
        msg = str(exc).lower()
        if "timeout" in msg:
            return ProviderError(
                "The model provider timed out. Try again.", code="timeout", retryable=True
            )
        if "rate" in msg and "limit" in msg:
            return ProviderError(
                "Provider rate limit reached. Wait and retry.", code="rate_limit", retryable=True
            )
        if "auth" in msg or "api key" in msg or "unauthorized" in msg:
            return ProviderError(
                "Provider authentication failed. Check your API key configuration.",
                code="auth_error",
            )
        if "connect" in msg or "network" in msg:
            return ProviderError(
                "Network failure talking to the provider.", code="network", retryable=True
            )
        return ProviderError(
            "Provider call failed. Check setup and try again.", code="provider_error"
        )
