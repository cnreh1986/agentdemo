"""Common agent interface."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ValidationError

from src.config.prompts import get_prompt, get_task_class_addendum
from src.models.agent import AgentResult
from src.models.task import TaskSpec
from src.providers.llm_base import LLMProvider, ProviderError


def _format_validation_errors(exc: ValidationError, limit: int = 5) -> list[str]:
    issues: list[str] = []
    for err in exc.errors()[:limit]:
        loc = ".".join(str(part) for part in err.get("loc", ())) or "root"
        msg = err.get("msg", "invalid")
        issues.append(f"{loc}: {msg}")
    if exc.error_count() > limit:
        issues.append(f"...and {exc.error_count() - limit} more")
    return issues


class Agent(ABC):
    name: str
    schema_name: str
    output_model: type[BaseModel]

    def __init__(
        self,
        provider: LLMProvider,
        *,
        prompt_overrides: dict[str, str] | None = None,
    ):
        self.provider = provider
        self.prompt_overrides = prompt_overrides or {}

    @abstractmethod
    def build_user_prompt(self, task: TaskSpec, context: dict[str, Any]) -> str:
        raise NotImplementedError

    def system_prompt(self) -> str:
        base = get_prompt(self.name, self.prompt_overrides)
        return base + get_task_class_addendum(self.name, getattr(self, "_task_class", None))

    def prepare_raw_output(self, raw: dict[str, Any], task: TaskSpec, context: dict[str, Any]) -> dict[str, Any]:
        """Hook for subclasses to normalize provider JSON before validation."""
        return raw

    def run(self, task: TaskSpec, context: dict[str, Any] | None = None) -> AgentResult:
        context = context or {}
        self._task_class = getattr(task, "task_class", "briefing")
        started = time.perf_counter()
        user_prompt = self.build_user_prompt(task, context)
        try:
            raw = self.provider.complete_json(
                system_prompt=self.system_prompt(),
                user_prompt=user_prompt,
                schema_name=self.schema_name,
            )
            raw = self.prepare_raw_output(raw, task, context)
            try:
                validated = self.output_model.model_validate(raw)
            except ValidationError as first_exc:
                # One bounded retry with concrete validation feedback.
                feedback = "; ".join(_format_validation_errors(first_exc))
                retry_prompt = (
                    f"{user_prompt}\n\n"
                    "Your previous JSON failed validation. Fix these issues and return "
                    f"ONLY valid JSON for schema `{self.schema_name}`:\n{feedback}"
                )
                raw = self.provider.complete_json(
                    system_prompt=self.system_prompt(),
                    user_prompt=retry_prompt,
                    schema_name=self.schema_name,
                )
                raw = self.prepare_raw_output(raw, task, context)
                try:
                    validated = self.output_model.model_validate(raw)
                except ValidationError as second_exc:
                    duration = int((time.perf_counter() - started) * 1000)
                    details = _format_validation_errors(second_exc)
                    return AgentResult(
                        agent_name=self.name,
                        status="failed",
                        summary="Agent output failed schema validation.",
                        output={},
                        issues=details or [f"Schema validation error: {second_exc.error_count()} issue(s)"],
                        duration_ms=duration,
                    )

            output = validated.model_dump(mode="json")
            duration = int((time.perf_counter() - started) * 1000)
            return AgentResult(
                agent_name=self.name,
                status="completed",
                summary=self.summarise(output),
                output=output,
                duration_ms=duration,
            )
        except ProviderError as exc:
            duration = int((time.perf_counter() - started) * 1000)
            return AgentResult(
                agent_name=self.name,
                status="failed",
                summary=exc.safe_message,
                output={},
                issues=[exc.safe_message],
                duration_ms=duration,
            )
        except Exception as exc:  # noqa: BLE001
            duration = int((time.perf_counter() - started) * 1000)
            return AgentResult(
                agent_name=self.name,
                status="failed",
                summary="Agent execution failed.",
                output={},
                issues=[str(exc)[:300]],
                duration_ms=duration,
            )

    def summarise(self, output: dict[str, Any]) -> str:
        return f"{self.name} completed."

    @staticmethod
    def dumps(payload: dict[str, Any]) -> str:
        return json.dumps(payload, default=str)
