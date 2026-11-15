"""Graph node implementations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from src.agents.execution_agent import ExecutionAgent
from src.agents.planning_agent import PlanningAgent
from src.agents.research_agent import ResearchAgent
from src.agents.reviewer_agent import ReviewerAgent
from src.config.prompts import get_prompt
from src.config.validation import validate_task_input
from src.demo.fixtures import build_task_spec
from src.models.task import TaskSpec
from src.services.comparison_intent import (
    comparison_success_criteria,
    parse_competitive_analysis_intent,
)
from src.services.job_intent import classify_task_class, job_success_criteria, parse_job_search_intent
from src.orchestration.events import make_event
from src.orchestration.state import WorkforceState
from src.providers.llm_base import LLMProvider
from src.providers.search_base import SearchProvider


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NodeContext:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        search_provider: SearchProvider | None = None,
        jobs_provider: Any | None = None,
        prompt_overrides: dict[str, str] | None = None,
    ):
        self.provider = provider
        self.search_provider = search_provider
        self.jobs_provider = jobs_provider
        self.prompt_overrides = prompt_overrides or {}
        self.research_agent = ResearchAgent(
            provider,
            search_provider=search_provider,
            jobs_provider=jobs_provider,
            prompt_overrides=self.prompt_overrides,
        )
        self.planning_agent = PlanningAgent(provider, prompt_overrides=self.prompt_overrides)
        self.execution_agent = ExecutionAgent(provider, prompt_overrides=self.prompt_overrides)
        self.reviewer_agent = ReviewerAgent(provider, prompt_overrides=self.prompt_overrides)


def validate_node(state: WorkforceState) -> dict[str, Any]:
    task_input = state.get("task_input") or {}
    result = validate_task_input(
        task_input.get("task", ""),
        task_input.get("background", ""),
        task_input.get("constraints", ""),
        task_input.get("time_horizon", ""),
        task_input.get("output_format", "Briefing"),
    )
    run_id = state.get("run_id") or str(uuid4())
    if not result.ok:
        return {
            "run_id": run_id,
            "status": "FAILED",
            "current_stage": "orchestrator",
            "error": "; ".join(result.errors),
            "events": [
                make_event(
                    run_id=run_id,
                    stage="orchestrator",
                    event_type="validation_failed",
                    status="failed",
                    message="; ".join(result.errors),
                )
            ],
            "node_states": {"orchestrator": "Failed"},
            "updated_at": _now(),
        }
    return {
        "run_id": run_id,
        "status": "TASK_VALIDATED",
        "current_stage": "orchestrator",
        "task_input": {
            "task": result.task,
            "background": result.background,
            "constraints": result.constraints,
            "time_horizon": result.time_horizon,
            "output_format": result.output_format,
        },
        "events": [
            make_event(
                run_id=run_id,
                stage="orchestrator",
                event_type="task_validated",
                status="ok",
                message="Task validated and normalised.",
            )
        ],
        "node_states": {"orchestrator": "Running"},
        "updated_at": _now(),
    }


def _resolve_task_class(state: WorkforceState, task_input: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Pick the task class and typed intent. A user-confirmed intent in state wins."""
    task = task_input.get("task", "")
    background = task_input.get("background", "")
    constraints = task_input.get("constraints", "")
    horizon = task_input.get("time_horizon", "")
    if state.get("comparison_intent"):
        task_class = "competitive_analysis"
    elif state.get("job_intent"):
        task_class = "job_search"
    else:
        task_class = classify_task_class(task, background, constraints)
    if task_class == "job_search":
        intent = state.get("job_intent") or parse_job_search_intent(task, background, constraints).model_dump(mode="json")
        return task_class, {"job_intent": intent}
    if task_class == "competitive_analysis":
        intent = state.get("comparison_intent") or parse_competitive_analysis_intent(
            task, background, constraints, horizon
        ).model_dump(mode="json")
        return task_class, {"comparison_intent": intent}
    return "briefing", {}


def class_context(state: WorkforceState) -> dict[str, Any]:
    """Task-class inputs handed to agents. Empty for briefing runs."""
    ctx: dict[str, Any] = {}
    for key in ("job_intent", "job_envelope", "comparison_intent", "comparison_envelope"):
        if state.get(key):
            ctx[key] = state[key]
    return ctx


_ARTIFACT_KEYS = {"job_envelope": "job_envelope", "comparison_envelope": "comparison_envelope"}


def specify_node(state: WorkforceState, ctx: NodeContext) -> dict[str, Any]:
    run_id = state["run_id"]
    if state.get("status") == "FAILED":
        return {}
    task_input = state["task_input"]
    mode = state.get("mode", "demo")
    model_configuration = state.get("model_configuration") or {
        "provider": ctx.provider.status().provider_name,
        "model": ctx.provider.status().model_name,
        "live": mode == "live",
    }
    # Prefer provider-built spec when available; fall back to local builder.
    try:
        raw = ctx.provider.complete_json(
            system_prompt=get_prompt("orchestrator", ctx.prompt_overrides),
            user_prompt=__import__("json").dumps({**task_input, "run_id": run_id}, default=str),
            schema_name="task_spec",
        )
        spec = TaskSpec.model_validate(raw).model_dump(mode="json")
    except Exception:
        spec = build_task_spec(
            run_id=run_id,
            task=task_input["task"],
            background=task_input.get("background", ""),
            constraints=task_input.get("constraints", ""),
            time_horizon=task_input.get("time_horizon", ""),
            output_format=task_input.get("output_format", "Briefing"),
            execution_mode=mode,  # type: ignore[arg-type]
            model_configuration=model_configuration,
        )
    task_class, class_updates = _resolve_task_class(state, task_input)
    spec["task_class"] = task_class
    if mode in {"demo", "live"}:
        spec["execution_mode"] = mode
    if task_class == "job_search":
        from src.models.job_search import JobSearchIntent

        spec["success_criteria"] = job_success_criteria(JobSearchIntent.model_validate(class_updates["job_intent"]))
    elif task_class == "competitive_analysis":
        from src.models.competitive_analysis import CompetitiveAnalysisIntent

        spec["success_criteria"] = comparison_success_criteria(
            CompetitiveAnalysisIntent.model_validate(class_updates["comparison_intent"])
        )
    return {
        "status": "SPECIFICATION_CREATED",
        "task_specification": spec,
        **class_updates,
        "events": [
            make_event(
                run_id=run_id,
                stage="orchestrator",
                event_type="specification_created",
                status="completed",
                message=(
                    "Orchestrator completed task specification."
                    if task_class == "briefing"
                    else f"Orchestrator completed task specification (task class: {task_class})."
                ),
                metadata={"task_class": task_class},
            )
        ],
        "node_states": {"orchestrator": "Completed"},
        "agent_executions": {
            "orchestrator": {
                "agent_name": "orchestrator",
                "status": "completed",
                "input": task_input,
                "output": spec,
                "summary": "Created task specification and success criteria.",
                "handoff_to": "research",
                "duration_ms": 0,
            }
        },
        "updated_at": _now(),
    }


def _run_agent_node(
    *,
    state: WorkforceState,
    agent_key: str,
    running_status: str,
    completed_status: str,
    runner: Callable[[TaskSpec, dict[str, Any]], Any],
    context_builder: Callable[[WorkforceState], dict[str, Any]],
    store_key: str,
    handoff_to: str,
    preserve_original_deliverable: bool = False,
    artifact_keys: dict[str, str] | None = None,
) -> dict[str, Any]:
    run_id = state["run_id"]
    if state.get("status") == "FAILED":
        return {}
    task = TaskSpec.model_validate(state["task_specification"])
    events = [
        make_event(
            run_id=run_id,
            stage=agent_key,
            event_type="agent_started",
            status="running",
            message=f"{agent_key.title()} Agent started.",
        )
    ]
    result = runner(task, context_builder(state))
    if result.status == "failed":
        detail = "; ".join(result.issues) if result.issues else result.summary
        fail_message = result.summary if not result.issues else f"{result.summary} {detail}"
        return {
            "status": "FAILED",
            "current_stage": agent_key,
            "error": detail,
            "events": events
            + [
                make_event(
                    run_id=run_id,
                    stage=agent_key,
                    event_type="agent_failed",
                    status="failed",
                    message=fail_message[:500],
                    duration_ms=result.duration_ms,
                    metadata={"issues": result.issues[:8]},
                )
            ],
            "node_states": {agent_key: "Failed"},
            "agent_executions": {
                agent_key: {
                    "agent_name": agent_key,
                    "status": "failed",
                    "input": context_builder(state),
                    "output": result.output,
                    "summary": result.summary,
                    "duration_ms": result.duration_ms,
                    "error": detail,
                }
            },
            "updated_at": _now(),
        }

    updates: dict[str, Any] = {
        "status": completed_status,
        "current_stage": agent_key,
        store_key: result.output,
        "events": events
        + [
            make_event(
                run_id=run_id,
                stage=agent_key,
                event_type="agent_completed",
                status="completed",
                message=result.summary,
                duration_ms=result.duration_ms,
            )
        ],
        "node_states": {agent_key: "Completed"},
        "agent_executions": {
            agent_key: {
                "agent_name": agent_key,
                "status": result.status,
                "input": context_builder(state),
                "output": result.output,
                "summary": result.summary,
                "handoff_to": handoff_to,
                "duration_ms": result.duration_ms,
            }
        },
        "updated_at": _now(),
    }
    for artifact, dest in (artifact_keys or {}).items():
        if artifact in result.artifacts:
            updates[dest] = result.artifacts[artifact]
    if preserve_original_deliverable and not state.get("deliverable_original"):
        updates["deliverable_original"] = result.output
    if result.status == "needs_revision":
        updates["status"] = "REVISION_REQUIRED"
        updates["node_states"] = {agent_key: "Needs revision"}
        updates["events"] = events + [
            make_event(
                run_id=run_id,
                stage=agent_key,
                event_type="revision_requested",
                status="revision_required",
                message=result.summary,
                duration_ms=result.duration_ms,
            )
        ]
        updates["unresolved_issues"] = list(result.output.get("issues") or [])
        updates["revision_instructions"] = "; ".join(result.output.get("recommendations") or [])
    return updates


def make_research_node(ctx: NodeContext):
    def research_node(state: WorkforceState) -> dict[str, Any]:
        return _run_agent_node(
            state={**state, "status": "RESEARCH_RUNNING", "node_states": {"research": "Running"}},
            agent_key="research",
            running_status="RESEARCH_RUNNING",
            completed_status="RESEARCH_COMPLETED",
            runner=ctx.research_agent.run,
            context_builder=lambda s: {
                "task_specification": s.get("task_specification"),
                "mode": s.get("mode"),
                **class_context(s),
            },
            store_key="research",
            handoff_to="planning",
            artifact_keys=_ARTIFACT_KEYS,
        )

    return research_node


def make_planning_node(ctx: NodeContext):
    def planning_node(state: WorkforceState) -> dict[str, Any]:
        return _run_agent_node(
            state={**state, "status": "PLANNING_RUNNING"},
            agent_key="planning",
            running_status="PLANNING_RUNNING",
            completed_status="PLANNING_COMPLETED",
            runner=ctx.planning_agent.run,
            context_builder=lambda s: {
                "research": s.get("research"),
                **class_context(s),
            },
            store_key="plan",
            handoff_to="execution",
        )

    return planning_node


def make_execution_node(ctx: NodeContext):
    def execution_node(state: WorkforceState) -> dict[str, Any]:
        instructions = state.get("revision_instructions") or state.get("human_revision_instruction")
        return _run_agent_node(
            state={**state, "status": "EXECUTION_RUNNING" if not instructions else "REVISION_RUNNING"},
            agent_key="execution",
            running_status="EXECUTION_RUNNING",
            completed_status="EXECUTION_COMPLETED",
            runner=ctx.execution_agent.run,
            context_builder=lambda s: {
                "research": s.get("research"),
                "plan": s.get("plan"),
                "revision_instructions": instructions,
                "prior_deliverable": s.get("deliverable"),
                **class_context(s),
            },
            store_key="deliverable",
            handoff_to="reviewer",
            preserve_original_deliverable=True,
            artifact_keys=_ARTIFACT_KEYS,
        )

    return execution_node


def make_review_node(ctx: NodeContext):
    def review_node(state: WorkforceState) -> dict[str, Any]:
        return _run_agent_node(
            state={**state, "status": "REVIEW_RUNNING"},
            agent_key="reviewer",
            running_status="REVIEW_RUNNING",
            completed_status="REVIEW_COMPLETED",
            runner=ctx.reviewer_agent.run,
            context_builder=lambda s: {
                "research": s.get("research"),
                "plan": s.get("plan"),
                "deliverable": s.get("deliverable"),
                **class_context(s),
            },
            store_key="review",
            handoff_to="human_approval",
        )

    return review_node


def await_human_node(state: WorkforceState) -> dict[str, Any]:
    run_id = state["run_id"]
    issues = list(state.get("unresolved_issues") or [])
    if state.get("review") and state["review"].get("status") == "revision_required":
        issues = issues or list(state["review"].get("issues") or [])
    return {
        "status": "AWAITING_HUMAN_APPROVAL",
        "current_stage": "human_approval",
        "unresolved_issues": issues,
        "node_states": {"human_approval": "Queued", "reviewer": state.get("node_states", {}).get("reviewer", "Completed")},
        "events": [
            make_event(
                run_id=run_id,
                stage="human_approval",
                event_type="human_approval_requested",
                status="awaiting",
                message="Workflow paused for explicit human approval.",
                metadata={"unresolved_issues": issues},
            )
        ],
        "updated_at": _now(),
    }


def bump_revision_node(state: WorkforceState) -> dict[str, Any]:
    run_id = state["run_id"]
    count = int(state.get("revision_count") or 0) + 1
    return {
        "revision_count": count,
        "status": "REVISION_RUNNING",
        "current_stage": "execution",
        "node_states": {"execution": "Running", "reviewer": "Waiting"},
        "events": [
            make_event(
                run_id=run_id,
                stage="orchestrator",
                event_type="revision_started",
                status="running",
                message=f"Revision {count} of {state.get('max_revisions', 1)} routed to Execution.",
            )
        ],
        "updated_at": _now(),
    }
