"""Run controller for Demo and Live modes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from src.config.settings import get_settings
from src.orchestration.events import make_event
from src.orchestration.runner import WorkforceRunner, mark_paused, review_is_clean
from src.providers.demo_provider import DemoProvider
from src.providers.firecrawl_search import FirecrawlSearchProvider
from src.providers.litellm_provider import LiteLLMProvider
from src.providers.search_base import NullSearchProvider
from src.providers.serpapi_jobs import SerpApiJobsProvider
from src.services.job_intent import classify_task_class

UpdateCallback = Callable[[dict[str, Any]], None]

AUTO_APPROVE_NOTE = "Auto-approved from user setting"


class RunService:
    def __init__(self, prompt_overrides: dict[str, str] | None = None):
        self.prompt_overrides = prompt_overrides or {}
        self.settings = get_settings()

    def _provider(self, mode: str):
        if mode == "demo":
            return DemoProvider()
        return LiteLLMProvider(self.settings)

    def _search(self, mode: str):
        # Demo Mode never calls live search / providers.
        if mode != "live":
            return NullSearchProvider()
        if self.settings.search_configured:
            return FirecrawlSearchProvider(self.settings)
        return NullSearchProvider()

    def _jobs(self, mode: str):
        # Demo Mode never calls SerpAPI; Live uses it only for job_search tasks.
        if mode != "live":
            return None
        return SerpApiJobsProvider(self.settings)

    def _runner(self, mode: str) -> WorkforceRunner:
        return WorkforceRunner(
            self._provider(mode),
            search_provider=self._search(mode),
            jobs_provider=self._jobs(mode),
            prompt_overrides=self.prompt_overrides,
            max_revisions=self.settings.max_revisions,
        )

    def _ensure_live_ready(
        self,
        mode: str,
        *,
        task: str = "",
        background: str = "",
        constraints: str = "",
        job_intent: dict[str, Any] | None = None,
    ) -> None:
        if mode == "live" and not self.settings.has_llm_credentials:
            raise RuntimeError(
                "Live LLM Mode requires provider credentials. "
                "Configure OPENAI_API_KEY (or matching provider key). "
                "The app will not fall back to Demo Mode."
            )
        if mode == "live" and not self.settings.jobs_search_configured:
            if job_intent or classify_task_class(task, background, constraints) == "job_search":
                raise RuntimeError(
                    "Live job search requires SERPAPI_API_KEY (SerpAPI Google Jobs). "
                    "Configure it, or use Demo Mode. The app will not invent listings."
                )

    def start_run(
        self,
        *,
        task: str,
        background: str = "",
        constraints: str = "",
        time_horizon: str = "",
        output_format: str = "Briefing",
        mode: str = "demo",
        on_update: UpdateCallback | None = None,
        job_intent: dict[str, Any] | None = None,
        comparison_intent: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_live_ready(
            mode, task=task, background=background, constraints=constraints, job_intent=job_intent
        )
        return self._runner(mode).run(
            task=task,
            background=background,
            constraints=constraints,
            time_horizon=time_horizon,
            output_format=output_format,
            mode=mode,
            on_update=on_update,
            job_intent=job_intent,
            comparison_intent=comparison_intent,
        )

    def begin_run(
        self,
        *,
        task: str,
        background: str = "",
        constraints: str = "",
        time_horizon: str = "",
        output_format: str = "Briefing",
        mode: str = "demo",
        on_update: UpdateCallback | None = None,
        job_intent: dict[str, Any] | None = None,
        comparison_intent: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Start a run and return after the first stage boundary."""
        self._ensure_live_ready(
            mode, task=task, background=background, constraints=constraints, job_intent=job_intent
        )
        return self._runner(mode).begin_run(
            task=task,
            background=background,
            constraints=constraints,
            time_horizon=time_horizon,
            output_format=output_format,
            mode=mode,
            on_update=on_update,
            job_intent=job_intent,
            comparison_intent=comparison_intent,
        )

    def advance_run(
        self,
        run_state: dict[str, Any],
        *,
        on_update: UpdateCallback | None = None,
    ) -> dict[str, Any]:
        """Advance one stage for an in-progress or paused run (same run_id)."""
        mode = run_state.get("mode") or "demo"
        self._ensure_live_ready(mode)
        run_id = run_state["run_id"]
        runner = self._runner(mode)
        return runner.continue_run(run_id, on_update=on_update)

    def run_has_more_stages(self, run_state: dict[str, Any]) -> bool:
        mode = run_state.get("mode") or "demo"
        return self._runner(mode).run_is_complete(run_state["run_id"]) is False

    def pause_run(self, run_state: dict[str, Any]) -> dict[str, Any]:
        return mark_paused(run_state)

    @staticmethod
    def can_auto_approve(run_state: dict[str, Any]) -> bool:
        return review_is_clean(run_state)

    def apply_human_decision(
        self,
        run_state: dict[str, Any],
        *,
        decision: str,
        note: str = "",
        on_update: UpdateCallback | None = None,
    ) -> dict[str, Any]:
        state = dict(run_state)
        now = datetime.now(timezone.utc).isoformat()
        note = (note or "").strip()

        if decision == "approve":
            state["approval_status"] = "approved"
            state["approval_note"] = note
            state["approval_at"] = now
            state["status"] = "HUMAN_APPROVED"
            node_states = dict(state.get("node_states") or {})
            node_states["human_approval"] = "Completed"
            state["node_states"] = node_states
            events = list(state.get("events") or [])
            if note == AUTO_APPROVE_NOTE:
                message = "Auto-approved from user setting."
            else:
                message = "Human approved the deliverable for personal use (no external action)."
            events.append(
                make_event(
                    run_id=state["run_id"],
                    stage="human_approval",
                    event_type="human_approved",
                    status="approved",
                    message=message,
                    metadata={"note": note, "auto_approve": note == AUTO_APPROVE_NOTE}
                    if note
                    else {},
                )
            )
            state["events"] = events
            return state

        if decision == "reject":
            state["approval_status"] = "rejected"
            state["approval_note"] = note
            state["approval_at"] = now
            state["status"] = "HUMAN_REJECTED"
            node_states = dict(state.get("node_states") or {})
            node_states["human_approval"] = "Failed"
            state["node_states"] = node_states
            events = list(state.get("events") or [])
            events.append(
                make_event(
                    run_id=state["run_id"],
                    stage="human_approval",
                    event_type="human_rejected",
                    status="rejected",
                    message="Human rejected the deliverable.",
                    metadata={"note": note} if note else {},
                )
            )
            state["events"] = events
            return state

        if decision == "revise":
            if not note:
                raise ValueError("Revision requires a short instruction.")
            events = list(state.get("events") or [])
            events.append(
                make_event(
                    run_id=state["run_id"],
                    stage="human_approval",
                    event_type="human_revision_requested",
                    status="revision_required",
                    message=f"Human requested revision: {note}",
                )
            )
            state["events"] = events
            mode = state.get("mode", "demo")
            runner = self._runner(mode)
            return runner.run(
                task=state["task_input"]["task"],
                mode=mode,
                human_revision_instruction=note,
                prior_state=state,
                on_update=on_update,
            )

        raise ValueError(f"Unknown decision: {decision}")
