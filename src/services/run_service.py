"""Run controller for Demo and Live modes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from src.config.settings import get_settings
from src.orchestration.events import make_event
from src.orchestration.runner import WorkforceRunner
from src.providers.demo_provider import DemoProvider
from src.providers.litellm_provider import LiteLLMProvider
from src.providers.firecrawl_search import FirecrawlSearchProvider
from src.providers.search_base import NullSearchProvider

UpdateCallback = Callable[[dict[str, Any]], None]


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
    ) -> dict[str, Any]:
        if mode == "live" and not self.settings.has_llm_credentials:
            raise RuntimeError(
                "Live LLM Mode requires provider credentials. "
                "Configure OPENAI_API_KEY (or matching provider key). "
                "The app will not fall back to Demo Mode."
            )
        runner = WorkforceRunner(
            self._provider(mode),
            search_provider=self._search(mode),
            prompt_overrides=self.prompt_overrides,
            max_revisions=self.settings.max_revisions,
        )
        return runner.run(
            task=task,
            background=background,
            constraints=constraints,
            time_horizon=time_horizon,
            output_format=output_format,
            mode=mode,
            on_update=on_update,
        )

    def apply_human_decision(
        self,
        run_state: dict[str, Any],
        *,
        decision: str,
        note: str = "",
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
            events.append(
                make_event(
                    run_id=state["run_id"],
                    stage="human_approval",
                    event_type="human_approved",
                    status="approved",
                    message="Human approved the deliverable for personal use (no external action).",
                    metadata={"note": note} if note else {},
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
            runner = WorkforceRunner(
                self._provider(mode),
                search_provider=self._search(mode),
                prompt_overrides=self.prompt_overrides,
                max_revisions=int(state.get("max_revisions") or self.settings.max_revisions),
            )
            return runner.run(
                task=state["task_input"]["task"],
                mode=mode,
                human_revision_instruction=note,
                prior_state=state,
            )

        raise ValueError(f"Unknown decision: {decision}")
