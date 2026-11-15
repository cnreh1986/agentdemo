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
        task_class = payload.get("task_class") or "briefing"
        if task_class != "briefing" and schema_name in {"plan", "deliverable", "review"}:
            special = self._complete_task_class(schema_name, task_class, payload, task)
            if special is not None:
                return special
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

    def _complete_task_class(
        self, schema_name: str, task_class: str, payload: dict[str, Any], task: str
    ) -> dict[str, Any] | None:
        """Demo responses for job_search / competitive_analysis built from the envelope."""
        from src.models.competitive_analysis import ComparisonEnvelope
        from src.models.job_search import JobSearchEnvelope
        from src.services import task_class_packets as packets

        if task_class == "job_search" and payload.get("job_envelope"):
            env = JobSearchEnvelope.model_validate(payload["job_envelope"])
            plan, deliverable = packets.job_plan, packets.job_deliverable_fields
        elif task_class == "competitive_analysis" and payload.get("comparison_envelope"):
            env = ComparisonEnvelope.model_validate(payload["comparison_envelope"])
            plan, deliverable = packets.comparison_plan, packets.comparison_deliverable_fields
        else:
            return None
        if schema_name == "plan":
            return plan(task, env)
        if schema_name == "deliverable":
            self._execution_calls += 1
            return deliverable(
                env, revised=self._execution_calls > 1 or bool(payload.get("revision_instructions"))
            )
        # Review: the deterministic envelope checks decide; no forced demo revision here.
        review = build_review(revision_required=False, quality_score=86)
        review["reviewer_summary"] = (
            "Demo review of the typed envelope; deterministic task-class checks are applied by code. "
            "This is not automatic human approval."
        )
        return review

    def _parse_user(self, user_prompt: str) -> dict[str, Any]:
        try:
            data = json.loads(user_prompt)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return {"task": user_prompt}
