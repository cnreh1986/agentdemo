"""LangGraph StateGraph for the Personal AI Workforce."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from src.orchestration.nodes import (
    NodeContext,
    await_human_node,
    bump_revision_node,
    make_execution_node,
    make_planning_node,
    make_research_node,
    make_review_node,
    specify_node,
    validate_node,
)
from src.orchestration.routing import after_agent, after_review, after_validation
from src.orchestration.state import WorkforceState
from src.providers.llm_base import LLMProvider
from src.providers.search_base import SearchProvider


# Pause between these nodes so Streamlit can honour Pause without mid-HTTP cancel.
STAGE_INTERRUPT_AFTER = [
    "validate",
    "specify",
    "research",
    "planning",
    "execution",
    "review",
    "bump_revision",
]


def build_workforce_graph(
    provider: LLMProvider,
    *,
    search_provider: SearchProvider | None = None,
    jobs_provider: Any | None = None,
    prompt_overrides: dict[str, str] | None = None,
    checkpointer: Any | None = None,
    interrupt_after: list[str] | None = None,
):
    ctx = NodeContext(
        provider,
        search_provider=search_provider,
        jobs_provider=jobs_provider,
        prompt_overrides=prompt_overrides,
    )

    graph = StateGraph(WorkforceState)
    graph.add_node("validate", validate_node)
    graph.add_node("specify", lambda s: specify_node(s, ctx))
    graph.add_node("research", make_research_node(ctx))
    graph.add_node("planning", make_planning_node(ctx))
    graph.add_node("execution", make_execution_node(ctx))
    graph.add_node("review", make_review_node(ctx))
    graph.add_node("bump_revision", bump_revision_node)
    graph.add_node("await_human", await_human_node)

    graph.set_entry_point("validate")
    graph.add_conditional_edges(
        "validate",
        after_validation,
        {"specify": "specify", "end_failed": END},
    )
    graph.add_edge("specify", "research")
    graph.add_conditional_edges(
        "research",
        after_agent,
        {"continue": "planning", "end_failed": END},
    )
    graph.add_conditional_edges(
        "planning",
        after_agent,
        {"continue": "execution", "end_failed": END},
    )
    graph.add_conditional_edges(
        "execution",
        after_agent,
        {"continue": "review", "end_failed": END},
    )
    graph.add_conditional_edges(
        "review",
        after_review,
        {"revise": "bump_revision", "human": "await_human"},
    )
    graph.add_edge("bump_revision", "execution")
    graph.add_edge("await_human", END)
    kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
    if interrupt_after is not None:
        kwargs["interrupt_after"] = interrupt_after
    return graph.compile(**kwargs)


def initial_state(
    *,
    task: str,
    background: str = "",
    constraints: str = "",
    time_horizon: str = "",
    output_format: str = "Briefing",
    mode: str = "demo",
    max_revisions: int = 1,
    run_id: str | None = None,
    model_configuration: dict[str, Any] | None = None,
    demo_disclaimer: str | None = None,
    job_intent: dict[str, Any] | None = None,
    comparison_intent: dict[str, Any] | None = None,
) -> WorkforceState:
    from datetime import datetime, timezone
    from uuid import uuid4

    now = datetime.now(timezone.utc).isoformat()
    rid = run_id or str(uuid4())
    disclaimer = demo_disclaimer
    if mode == "demo" and not disclaimer:
        disclaimer = (
            "Demo Mode: illustrative outputs only. No live web research and no LLM calls."
        )
    return {
        "run_id": rid,
        "mode": mode,
        "status": "TASK_RECEIVED",
        "current_stage": "orchestrator",
        "revision_count": 0,
        "max_revisions": max_revisions,
        "task_input": {
            "task": task,
            "background": background,
            "constraints": constraints,
            "time_horizon": time_horizon,
            "output_format": output_format,
        },
        "task_specification": None,
        "job_intent": job_intent,
        "job_envelope": None,
        "comparison_intent": comparison_intent,
        "comparison_envelope": None,
        "research": None,
        "plan": None,
        "deliverable": None,
        "deliverable_original": None,
        "review": None,
        "events": [
            {
                "event_id": str(uuid4()),
                "run_id": rid,
                "timestamp": now,
                "stage": "system",
                "event_type": "run_created",
                "status": "ok",
                "message": f"Run created in {mode} mode.",
                "duration_ms": None,
                "metadata": {},
            }
        ],
        "node_states": {
            "orchestrator": "Waiting",
            "research": "Waiting",
            "planning": "Waiting",
            "execution": "Waiting",
            "reviewer": "Waiting",
            "human_approval": "Waiting",
        },
        "agent_executions": {},
        "error": None,
        "unresolved_issues": [],
        "revision_instructions": None,
        "human_revision_instruction": None,
        "approval_status": None,
        "approval_note": None,
        "approval_at": None,
        "demo_disclaimer": disclaimer,
        "model_configuration": model_configuration or {},
        "created_at": now,
        "updated_at": now,
    }
