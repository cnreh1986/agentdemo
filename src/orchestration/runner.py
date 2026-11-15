"""Execute the workforce graph and return a UI-friendly run dict."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.checkpoint.memory import MemorySaver

from src.config.settings import get_settings
from src.orchestration.events import make_event
from src.orchestration.graph import STAGE_INTERRUPT_AFTER, build_workforce_graph, initial_state
from src.providers.demo_provider import DemoProvider
from src.providers.llm_base import LLMProvider
from src.providers.search_base import NullSearchProvider, SearchProvider

UpdateCallback = Callable[[dict[str, Any]], None]

# Process-wide checkpointer so Streamlit reruns can resume the same run_id.
_SHARED_CHECKPOINTER = MemorySaver()

TERMINAL_STATUSES = {
    "AWAITING_HUMAN_APPROVAL",
    "HUMAN_APPROVED",
    "HUMAN_REJECTED",
    "FAILED",
    "CANCELLED",
}


def review_is_clean(state: dict[str, Any]) -> bool:
    """True when auto-approve may run (awaiting human, no open review issues)."""
    if (state.get("status") or "") == "FAILED":
        return False
    if (state.get("status") or "") != "AWAITING_HUMAN_APPROVAL":
        return False
    review = state.get("review") or {}
    if review.get("status") == "revision_required":
        return False
    if list(state.get("unresolved_issues") or []):
        return False
    return True


def mark_paused(state: dict[str, Any]) -> dict[str, Any]:
    """Mark a mid-run state as PAUSED after the stage that just finished."""
    out = dict(state)
    stage = out.get("current_stage") or out.get("paused_after_stage") or "unknown"
    out["status"] = "PAUSED"
    out["paused_after_stage"] = stage
    node_states = dict(out.get("node_states") or {})
    # Keep last active agent label readable in the pipeline.
    for key, label in list(node_states.items()):
        if label in {"Running", "Queued"} and key != "human_approval":
            node_states[key] = "Paused"
    out["node_states"] = node_states
    events = list(out.get("events") or [])
    events.append(
        make_event(
            run_id=out["run_id"],
            stage=stage,
            event_type="run_paused",
            status="paused",
            message=f"Paused after {stage}. Resume when ready.",
        )
    )
    out["events"] = events
    return out


class WorkforceRunner:
    def __init__(
        self,
        provider: LLMProvider | None = None,
        *,
        search_provider: SearchProvider | None = None,
        jobs_provider: Any | None = None,
        prompt_overrides: dict[str, str] | None = None,
        max_revisions: int | None = None,
    ):
        settings = get_settings()
        self.provider = provider or DemoProvider()
        self.search_provider = search_provider or NullSearchProvider()
        self.jobs_provider = jobs_provider
        self.prompt_overrides = prompt_overrides or {}
        self.max_revisions = (
            max_revisions if max_revisions is not None else settings.max_revisions
        )
        self.graph = build_workforce_graph(
            self.provider,
            search_provider=self.search_provider,
            jobs_provider=self.jobs_provider,
            prompt_overrides=self.prompt_overrides,
            checkpointer=_SHARED_CHECKPOINTER,
            interrupt_after=STAGE_INTERRUPT_AFTER,
        )

    def _config(self, run_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": run_id}}

    def _has_pending(self, run_id: str) -> bool:
        snap = self.graph.get_state(self._config(run_id))
        return bool(snap.next)

    def _stream_until_interrupt(
        self,
        inputs: dict[str, Any] | None,
        *,
        run_id: str,
        on_update: UpdateCallback | None = None,
    ) -> dict[str, Any]:
        config = self._config(run_id)
        final: dict[str, Any] | None = None
        for snapshot in self.graph.stream(inputs, config, stream_mode="values"):
            final = dict(snapshot)
            if on_update:
                on_update(final)
        if final is None:
            # No new values (should be rare); fall back to checkpoint values.
            snap = self.graph.get_state(config)
            final = dict(snap.values or {})
        return final

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
        """Run until the first stage interrupt (or terminal)."""
        status = self.provider.status()
        seed = initial_state(
            task=task,
            background=background,
            constraints=constraints,
            time_horizon=time_horizon,
            output_format=output_format,
            mode=mode,
            max_revisions=self.max_revisions,
            model_configuration={
                "provider": status.provider_name,
                "model": status.model_name,
                "live": mode == "live",
            },
            job_intent=job_intent,
            comparison_intent=comparison_intent,
        )
        if on_update:
            on_update(dict(seed))
        return self._stream_until_interrupt(seed, run_id=seed["run_id"], on_update=on_update)

    def continue_run(
        self,
        run_id: str,
        *,
        on_update: UpdateCallback | None = None,
    ) -> dict[str, Any]:
        """Resume from the last interrupt until the next interrupt or END."""
        if not self._has_pending(run_id):
            snap = self.graph.get_state(self._config(run_id))
            return dict(snap.values or {})
        return self._stream_until_interrupt(None, run_id=run_id, on_update=on_update)

    def run_is_complete(self, run_id: str) -> bool:
        return not self._has_pending(run_id)

    def run(
        self,
        *,
        task: str,
        background: str = "",
        constraints: str = "",
        time_horizon: str = "",
        output_format: str = "Briefing",
        mode: str = "demo",
        on_update: UpdateCallback | None = None,
        human_revision_instruction: str | None = None,
        prior_state: dict[str, Any] | None = None,
        job_intent: dict[str, Any] | None = None,
        comparison_intent: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if prior_state and human_revision_instruction:
            state = dict(prior_state)
            state["human_revision_instruction"] = human_revision_instruction
            state["revision_instructions"] = human_revision_instruction
            seed = initial_state(
                task=state["task_input"]["task"],
                background=state["task_input"].get("background", ""),
                constraints=state["task_input"].get("constraints", ""),
                time_horizon=state["task_input"].get("time_horizon", ""),
                output_format=state["task_input"].get("output_format", "Briefing"),
                mode=state.get("mode", mode),
                max_revisions=state.get("max_revisions", self.max_revisions),
                run_id=state["run_id"],
                model_configuration=state.get("model_configuration"),
                demo_disclaimer=state.get("demo_disclaimer"),
            )
            seed.update(
                {
                    "task_specification": state.get("task_specification"),
                    "job_intent": state.get("job_intent"),
                    "job_envelope": state.get("job_envelope"),
                    "comparison_intent": state.get("comparison_intent"),
                    "comparison_envelope": state.get("comparison_envelope"),
                    "research": state.get("research"),
                    "plan": state.get("plan"),
                    "deliverable": state.get("deliverable"),
                    "deliverable_original": state.get("deliverable_original")
                    or state.get("deliverable"),
                    "revision_count": int(state.get("revision_count") or 0),
                    "human_revision_instruction": human_revision_instruction,
                    "revision_instructions": human_revision_instruction,
                    "events": list(state.get("events") or []),
                    "agent_executions": dict(state.get("agent_executions") or {}),
                    "node_states": dict(state.get("node_states") or seed["node_states"]),
                }
            )
            from src.orchestration.human_revision import run_human_revision

            return run_human_revision(
                self.provider,
                seed,
                search_provider=self.search_provider,
                jobs_provider=self.jobs_provider,
                prompt_overrides=self.prompt_overrides,
                on_update=on_update,
            )

        state = self.begin_run(
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
        run_id = state["run_id"]
        while self._has_pending(run_id) and (state.get("status") or "") != "FAILED":
            state = self.continue_run(run_id, on_update=on_update)
        return state
