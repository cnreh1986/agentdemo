"""Execute the workforce graph and return a UI-friendly run dict."""

from __future__ import annotations

from typing import Any, Callable

from src.config.settings import get_settings
from src.orchestration.graph import build_workforce_graph, initial_state
from src.providers.demo_provider import DemoProvider
from src.providers.llm_base import LLMProvider
from src.providers.search_base import NullSearchProvider, SearchProvider

UpdateCallback = Callable[[dict[str, Any]], None]


class WorkforceRunner:
    def __init__(
        self,
        provider: LLMProvider | None = None,
        *,
        search_provider: SearchProvider | None = None,
        prompt_overrides: dict[str, str] | None = None,
        max_revisions: int | None = None,
    ):
        settings = get_settings()
        self.provider = provider or DemoProvider()
        self.search_provider = search_provider or NullSearchProvider()
        self.prompt_overrides = prompt_overrides or {}
        self.max_revisions = (
            max_revisions if max_revisions is not None else settings.max_revisions
        )
        self.graph = build_workforce_graph(
            self.provider,
            search_provider=self.search_provider,
            prompt_overrides=self.prompt_overrides,
        )

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
                prompt_overrides=self.prompt_overrides,
                on_update=on_update,
            )

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
        )
        if on_update:
            on_update(dict(seed))

        final: dict[str, Any] = dict(seed)
        for snapshot in self.graph.stream(seed, stream_mode="values"):
            final = dict(snapshot)
            if on_update:
                on_update(final)
        return final
