"""Synchronous Demo Mode runner with visible stage progression."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from src.config.validation import validate_task_input
from src.demo.fixtures import build_demo_packets
from src.orchestration.events import make_event

StageCallback = Callable[[dict[str, Any]], None]

PIPELINE = [
    "orchestrator",
    "research",
    "planning",
    "execution",
    "reviewer",
    "human_approval",
]


class DemoRunner:
    """Deterministic end-to-end demo with one reviewer revision."""

    def __init__(self, max_revisions: int = 1, step_delay_s: float = 0.15):
        self.max_revisions = max_revisions
        self.step_delay_s = step_delay_s

    def run(
        self,
        *,
        task: str,
        background: str = "",
        constraints: str = "",
        time_horizon: str = "",
        output_format: str = "Briefing",
        on_update: StageCallback | None = None,
    ) -> dict[str, Any]:
        validation = validate_task_input(
            task, background, constraints, time_horizon, output_format
        )
        if not validation.ok:
            raise ValueError("; ".join(validation.errors))

        run_id = str(uuid4())
        started = datetime.now(timezone.utc).isoformat()
        packets = build_demo_packets(
            task=validation.task,
            background=validation.background,
            constraints=validation.constraints,
            time_horizon=validation.time_horizon,
            output_format=validation.output_format,
            run_id=run_id,
        )

        state: dict[str, Any] = {
            "run_id": run_id,
            "mode": "demo",
            "status": "TASK_RECEIVED",
            "current_stage": "orchestrator",
            "revision_count": 0,
            "max_revisions": self.max_revisions,
            "node_states": {name: "Waiting" for name in PIPELINE},
            "events": [],
            "task_input": {
                "task": validation.task,
                "background": validation.background,
                "constraints": validation.constraints,
                "time_horizon": validation.time_horizon,
                "output_format": validation.output_format,
            },
            "task_specification": None,
            "research": None,
            "plan": None,
            "deliverable": None,
            "deliverable_original": None,
            "review": None,
            "agent_executions": {},
            "approval_status": None,
            "approval_note": None,
            "approval_at": None,
            "created_at": started,
            "updated_at": started,
            "error": None,
            "demo_disclaimer": (
                "Demo Mode: illustrative outputs only. No live web research and no LLM calls."
            ),
        }

        def emit(**kwargs: Any) -> None:
            event = make_event(run_id=run_id, **kwargs)
            state["events"].append(event)
            state["updated_at"] = event["timestamp"]
            if on_update:
                on_update(state)

        def set_node(name: str, node_status: str) -> None:
            state["node_states"][name] = node_status

        def record_agent(name: str, payload: dict[str, Any], duration_ms: int) -> None:
            now = datetime.now(timezone.utc).isoformat()
            state["agent_executions"][name] = {
                "agent_name": name,
                "status": "completed",
                "input": payload.get("input", {}),
                "output": payload.get("output", {}),
                "summary": payload.get("summary", ""),
                "started_at": payload.get("started_at", now),
                "completed_at": now,
                "duration_ms": duration_ms,
                "error": None,
                "handoff_to": payload.get("handoff_to"),
            }

        emit(
            stage="system",
            event_type="run_created",
            status="ok",
            message="Run created in Demo Mode.",
        )
        emit(
            stage="orchestrator",
            event_type="task_validated",
            status="ok",
            message="Task validated and normalised.",
        )

        # Orchestrator / task specification
        set_node("orchestrator", "Running")
        state["status"] = "SPECIFICATION_CREATED"
        state["current_stage"] = "orchestrator"
        t0 = time.perf_counter()
        self._pause()
        state["task_specification"] = packets["task_specification"]
        duration = int((time.perf_counter() - t0) * 1000)
        record_agent(
            "orchestrator",
            {
                "input": state["task_input"],
                "output": state["task_specification"],
                "summary": "Created task specification and success criteria.",
                "handoff_to": "research",
            },
            duration,
        )
        set_node("orchestrator", "Completed")
        emit(
            stage="orchestrator",
            event_type="specification_created",
            status="completed",
            message="Orchestrator completed task specification.",
            duration_ms=duration,
        )

        # Research
        set_node("research", "Running")
        state["status"] = "RESEARCH_RUNNING"
        state["current_stage"] = "research"
        emit(
            stage="research",
            event_type="agent_started",
            status="running",
            message="Research Agent started.",
        )
        t0 = time.perf_counter()
        self._pause()
        state["research"] = packets["research"]
        duration = int((time.perf_counter() - t0) * 1000)
        record_agent(
            "research",
            {
                "input": {"task_specification": state["task_specification"]},
                "output": state["research"],
                "summary": state["research"]["agent_summary"],
                "handoff_to": "planning",
            },
            duration,
        )
        set_node("research", "Completed")
        state["status"] = "RESEARCH_COMPLETED"
        emit(
            stage="research",
            event_type="agent_completed",
            status="completed",
            message="Research Agent completed (illustrative; not live-verified).",
            duration_ms=duration,
        )

        # Planning
        set_node("planning", "Running")
        state["status"] = "PLANNING_RUNNING"
        state["current_stage"] = "planning"
        emit(
            stage="planning",
            event_type="agent_started",
            status="running",
            message="Planning Agent started.",
        )
        t0 = time.perf_counter()
        self._pause()
        state["plan"] = packets["plan"]
        duration = int((time.perf_counter() - t0) * 1000)
        record_agent(
            "planning",
            {
                "input": {
                    "task_specification": state["task_specification"],
                    "research": state["research"],
                },
                "output": state["plan"],
                "summary": "Converted findings into a prioritised action plan.",
                "handoff_to": "execution",
            },
            duration,
        )
        set_node("planning", "Completed")
        state["status"] = "PLANNING_COMPLETED"
        emit(
            stage="planning",
            event_type="agent_completed",
            status="completed",
            message="Planning Agent completed.",
            duration_ms=duration,
        )

        # Execution v1
        set_node("execution", "Running")
        state["status"] = "EXECUTION_RUNNING"
        state["current_stage"] = "execution"
        emit(
            stage="execution",
            event_type="agent_started",
            status="running",
            message="Execution Agent started.",
        )
        t0 = time.perf_counter()
        self._pause()
        state["deliverable"] = packets["deliverable_v1"]
        state["deliverable_original"] = packets["deliverable_v1"]
        duration = int((time.perf_counter() - t0) * 1000)
        record_agent(
            "execution",
            {
                "input": {
                    "task_specification": state["task_specification"],
                    "research": state["research"],
                    "plan": state["plan"],
                },
                "output": state["deliverable"],
                "summary": "Created initial Markdown deliverable.",
                "handoff_to": "reviewer",
            },
            duration,
        )
        set_node("execution", "Completed")
        state["status"] = "EXECUTION_COMPLETED"
        emit(
            stage="execution",
            event_type="agent_completed",
            status="completed",
            message="Execution Agent completed initial deliverable.",
            duration_ms=duration,
        )

        # Reviewer requests revision
        set_node("reviewer", "Running")
        state["status"] = "REVIEW_RUNNING"
        state["current_stage"] = "reviewer"
        emit(
            stage="reviewer",
            event_type="agent_started",
            status="running",
            message="Reviewer Agent started independent review.",
        )
        t0 = time.perf_counter()
        self._pause()
        state["review"] = packets["review_v1"]
        duration = int((time.perf_counter() - t0) * 1000)
        record_agent(
            "reviewer",
            {
                "input": {
                    "deliverable": state["deliverable"],
                    "task_specification": state["task_specification"],
                },
                "output": state["review"],
                "summary": state["review"]["reviewer_summary"],
                "handoff_to": "execution",
            },
            duration,
        )
        set_node("reviewer", "Needs revision")
        state["status"] = "REVISION_REQUIRED"
        emit(
            stage="reviewer",
            event_type="revision_requested",
            status="revision_required",
            message="Reviewer requested a bounded revision.",
            duration_ms=duration,
        )

        if state["revision_count"] < self.max_revisions:
            state["revision_count"] += 1
            state["status"] = "REVISION_RUNNING"
            set_node("execution", "Running")
            set_node("reviewer", "Waiting")
            emit(
                stage="orchestrator",
                event_type="revision_started",
                status="running",
                message=f"Revision {state['revision_count']} of {self.max_revisions} routed to Execution.",
            )
            t0 = time.perf_counter()
            self._pause()
            state["deliverable"] = packets["deliverable_v2"]
            duration = int((time.perf_counter() - t0) * 1000)
            record_agent(
                "execution_revision",
                {
                    "input": {
                        "prior_deliverable": state["deliverable_original"],
                        "review": packets["review_v1"],
                    },
                    "output": state["deliverable"],
                    "summary": "Revised deliverable after reviewer feedback.",
                    "handoff_to": "reviewer",
                },
                duration,
            )
            set_node("execution", "Completed")
            emit(
                stage="execution",
                event_type="agent_completed",
                status="completed",
                message="Execution Agent completed revised deliverable.",
                duration_ms=duration,
            )

            set_node("reviewer", "Running")
            state["status"] = "REVIEW_RUNNING"
            t0 = time.perf_counter()
            self._pause()
            state["review"] = packets["review_v2"]
            duration = int((time.perf_counter() - t0) * 1000)
            record_agent(
                "reviewer_final",
                {
                    "input": {"deliverable": state["deliverable"]},
                    "output": state["review"],
                    "summary": state["review"]["reviewer_summary"],
                    "handoff_to": "human_approval",
                },
                duration,
            )
            set_node("reviewer", "Completed")
            state["status"] = "REVIEW_COMPLETED"
            emit(
                stage="reviewer",
                event_type="review_passed",
                status="completed",
                message="Reviewer passed the revised deliverable for human approval.",
                duration_ms=duration,
            )

        set_node("human_approval", "Queued")
        state["status"] = "AWAITING_HUMAN_APPROVAL"
        state["current_stage"] = "human_approval"
        emit(
            stage="human_approval",
            event_type="human_approval_requested",
            status="awaiting",
            message="Workflow paused for explicit human approval.",
        )
        return state

    def _pause(self) -> None:
        if self.step_delay_s > 0:
            time.sleep(self.step_delay_s)
