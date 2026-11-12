"""Deterministic provider for Demo Mode — no network calls."""

from __future__ import annotations

import json
from typing import Any

from src.demo.fixtures import (
    build_deliverable,
    build_plan,
    build_research_packet,
    build_review,
    build_task_spec,
)
from src.providers.llm_base import LLMProvider, ProviderStatus


class DemoProvider(LLMProvider):
    def __init__(self, *, force_revision_first: bool = True):
        self.force_revision_first = force_revision_first
        self._review_calls = 0
        self._execution_calls = 0

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            ready=True,
            provider_name="demo",
            model_name="fixtures",
            message="Demo Mode ready — illustrative outputs only.",
        )

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        payload = self._parse_user(user_prompt)
        task = payload.get("task") or payload.get("original_task") or "Demo task"
        run_id = payload.get("run_id", "demo-run")

        if schema_name == "task_spec":
            return build_task_spec(
                run_id=run_id,
                task=task,
                background=payload.get("background", ""),
                constraints=payload.get("constraints", ""),
                time_horizon=payload.get("time_horizon", ""),
                output_format=payload.get("output_format", "Briefing"),
                execution_mode="demo",
            )
        if schema_name == "research":
            return build_research_packet(run_id, task)
        if schema_name == "plan":
            return build_plan(task)
        if schema_name == "deliverable":
            self._execution_calls += 1
            revised = self._execution_calls > 1 or bool(payload.get("revision_instructions"))
            return build_deliverable(
                task,
                revised=revised,
                revision_note=payload.get("revision_instructions"),
            )
        if schema_name == "review":
            self._review_calls += 1
            if self.force_revision_first and self._review_calls == 1:
                return build_review(revision_required=True, quality_score=68)
            return build_review(revision_required=False, quality_score=86)
        raise ValueError(f"Unknown schema_name for DemoProvider: {schema_name}")

    def _parse_user(self, user_prompt: str) -> dict[str, Any]:
        try:
            data = json.loads(user_prompt)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return {"task": user_prompt}
