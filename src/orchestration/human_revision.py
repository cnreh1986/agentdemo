"""Human-requested revision path (outside automatic reviewer loop)."""

from __future__ import annotations

from typing import Any, Callable

from src.orchestration.events import make_event
from src.orchestration.nodes import NodeContext, await_human_node, make_execution_node, make_review_node
from src.providers.llm_base import LLMProvider
from src.providers.search_base import SearchProvider

UpdateCallback = Callable[[dict[str, Any]], None]


def _merge(state: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    out = dict(state)
    for key, value in updates.items():
        if key == "events":
            out["events"] = list(out.get("events") or []) + list(value or [])
        elif key in {"node_states", "agent_executions"}:
            merged = dict(out.get(key) or {})
            merged.update(value or {})
            out[key] = merged
        else:
            out[key] = value
    return out


def _emit(on_update: UpdateCallback | None, state: dict[str, Any]) -> None:
    if on_update:
        on_update(dict(state))


def run_human_revision(
    provider: LLMProvider,
    state: dict[str, Any],
    *,
    search_provider: SearchProvider | None = None,
    jobs_provider: Any | None = None,
    prompt_overrides: dict[str, str] | None = None,
    on_update: UpdateCallback | None = None,
) -> dict[str, Any]:
    max_rev = int(state.get("max_revisions") or 1)
    count = int(state.get("revision_count") or 0)
    if count >= max_rev:
        state = dict(state)
        state["unresolved_issues"] = list(state.get("unresolved_issues") or []) + [
            "Maximum revision count reached; presenting current result for human decision."
        ]
        state = _merge(
            state,
            {
                "events": [
                    make_event(
                        run_id=state["run_id"],
                        stage="human_approval",
                        event_type="revision_limit_reached",
                        status="awaiting",
                        message="Revision limit reached after human request.",
                    )
                ]
            },
        )
        state = _merge(state, await_human_node(state))  # type: ignore[arg-type]
        _emit(on_update, state)
        return state

    ctx = NodeContext(
        provider,
        search_provider=search_provider,
        jobs_provider=jobs_provider,
        prompt_overrides=prompt_overrides,
    )
    state = _merge(
        state,
        {
            "revision_count": count + 1,
            "events": [
                make_event(
                    run_id=state["run_id"],
                    stage="human_approval",
                    event_type="human_revision_started",
                    status="running",
                    message=f"Human revision {count + 1} of {max_rev} started.",
                )
            ],
        },
    )
    _emit(on_update, state)
    state = _merge(state, make_execution_node(ctx)(state))  # type: ignore[arg-type]
    _emit(on_update, state)
    if state.get("status") == "FAILED":
        return state
    state = _merge(state, make_review_node(ctx)(state))  # type: ignore[arg-type]
    _emit(on_update, state)
    if state.get("status") == "FAILED":
        return state
    state = _merge(state, await_human_node(state))  # type: ignore[arg-type]
    _emit(on_update, state)
    return state
