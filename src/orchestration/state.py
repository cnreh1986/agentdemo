"""LangGraph workforce state."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def merge_dicts(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(left or {})
    out.update(right or {})
    return out


class WorkforceState(TypedDict, total=False):
    run_id: str
    mode: str
    status: str
    current_stage: str
    revision_count: int
    max_revisions: int
    task_input: dict[str, Any]
    task_specification: dict[str, Any] | None
    research: dict[str, Any] | None
    plan: dict[str, Any] | None
    deliverable: dict[str, Any] | None
    deliverable_original: dict[str, Any] | None
    review: dict[str, Any] | None
    events: Annotated[list[dict[str, Any]], operator.add]
    node_states: Annotated[dict[str, str], merge_dicts]
    agent_executions: Annotated[dict[str, Any], merge_dicts]
    error: str | None
    unresolved_issues: list[str]
    revision_instructions: str | None
    human_revision_instruction: str | None
    approval_status: str | None
    approval_note: str | None
    approval_at: str | None
    demo_disclaimer: str | None
    model_configuration: dict[str, Any]
    created_at: str
    updated_at: str
