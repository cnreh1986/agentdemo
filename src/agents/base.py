"""Common agent interface."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ValidationError

from src.config.prompts import get_prompt
from src.models.agent import AgentResult
from src.models.task import TaskSpec
from src.providers.llm_base import LLMProvider, ProviderError


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
        return get_prompt(self.name, self.prompt_overrides)

    def run(self, task: TaskSpec, context: dict[str, Any] | None = None) -> AgentResult:
        context = context or {}
        started = time.perf_counter()
        try:
            raw = self.provider.complete_json(
                system_prompt=self.system_prompt(),
                user_prompt=self.build_user_prompt(task, context),
                schema_name=self.schema_name,
            )
            validated = self.output_model.model_validate(raw)
            output = validated.model_dump(mode="json")
            duration = int((time.perf_counter() - started) * 1000)
            return AgentResult(
                agent_name=self.name,
                status="completed",
                summary=self.summarise(output),
                output=output,
                duration_ms=duration,
            )
        except ValidationError as exc:
            duration = int((time.perf_counter() - started) * 1000)
            return AgentResult(
                agent_name=self.name,
                status="failed",
                summary="Agent output failed schema validation.",
                output={},
                issues=[f"Schema validation error: {exc.error_count()} issue(s)"],
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
