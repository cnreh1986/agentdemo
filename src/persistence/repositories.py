"""Run history repository."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.orchestration.events import sanitize_value
from src.persistence.database import Database


class RunRepository:
    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def save_run(self, state: dict[str, Any]) -> None:
        safe_state = sanitize_value(state)
        run_id = safe_state["run_id"]
        now = datetime.now(timezone.utc).isoformat()
        completed = safe_state.get("status") in {
            "HUMAN_APPROVED",
            "HUMAN_REJECTED",
            "FAILED",
            "CANCELLED",
            "AWAITING_HUMAN_APPROVAL",
        }
        model_cfg = safe_state.get("model_configuration") or {}
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    id, created_at, updated_at, task_input, task_specification_json,
                    mode, provider_name, model_name, status, current_stage,
                    revision_count, max_revisions, approval_status, approval_note,
                    completed_at, state_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    updated_at=excluded.updated_at,
                    task_specification_json=excluded.task_specification_json,
                    status=excluded.status,
                    current_stage=excluded.current_stage,
                    revision_count=excluded.revision_count,
                    approval_status=excluded.approval_status,
                    approval_note=excluded.approval_note,
                    completed_at=excluded.completed_at,
                    state_json=excluded.state_json
                """,
                (
                    run_id,
                    safe_state.get("created_at") or now,
                    safe_state.get("updated_at") or now,
                    json.dumps(safe_state.get("task_input") or {}),
                    json.dumps(safe_state.get("task_specification")),
                    safe_state.get("mode", "demo"),
                    model_cfg.get("provider"),
                    model_cfg.get("model"),
                    safe_state.get("status"),
                    safe_state.get("current_stage"),
                    int(safe_state.get("revision_count") or 0),
                    int(safe_state.get("max_revisions") or 1),
                    safe_state.get("approval_status"),
                    safe_state.get("approval_note"),
                    now if completed else None,
                    json.dumps(safe_state),
                ),
            )
            conn.execute("DELETE FROM agent_executions WHERE run_id = ?", (run_id,))
            for name, packet in (safe_state.get("agent_executions") or {}).items():
                conn.execute(
                    """
                    INSERT INTO agent_executions (
                        id, run_id, agent_name, status, input_json, output_json,
                        started_at, completed_at, duration_ms, error_code,
                        safe_error_message, attempt_number
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        run_id,
                        name,
                        packet.get("status"),
                        json.dumps(packet.get("input")),
                        json.dumps(packet.get("output")),
                        packet.get("started_at"),
                        packet.get("completed_at"),
                        packet.get("duration_ms"),
                        packet.get("error_code"),
                        packet.get("error"),
                        packet.get("attempt_number", 1),
                    ),
                )
            conn.execute("DELETE FROM workflow_events WHERE run_id = ?", (run_id,))
            for event in safe_state.get("events") or []:
                conn.execute(
                    """
                    INSERT INTO workflow_events (
                        id, run_id, timestamp, stage, event_type, status, message, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.get("event_id") or str(uuid4()),
                        run_id,
                        event.get("timestamp") or now,
                        event.get("stage"),
                        event.get("event_type"),
                        event.get("status"),
                        event.get("message"),
                        json.dumps(event.get("metadata") or {}),
                    ),
                )
            conn.execute("DELETE FROM artifacts WHERE run_id = ?", (run_id,))
            deliverable = safe_state.get("deliverable") or {}
            if deliverable:
                conn.execute(
                    """
                    INSERT INTO artifacts (
                        id, run_id, artifact_type, title, content_markdown, content_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        run_id,
                        "deliverable",
                        deliverable.get("title"),
                        deliverable.get("markdown_content"),
                        json.dumps(deliverable),
                        now,
                    ),
                )
            conn.commit()

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, updated_at, task_input, mode, status, approval_status
                FROM runs ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result = []
        for row in rows:
            task_input = json.loads(row["task_input"] or "{}")
            result.append(
                {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "task": task_input.get("task", ""),
                    "mode": row["mode"],
                    "status": row["status"],
                    "approval_status": row["approval_status"],
                }
            )
        return result

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT state_json FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return json.loads(row["state_json"])

    def clear_all(self) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM artifacts")
            conn.execute("DELETE FROM workflow_events")
            conn.execute("DELETE FROM agent_executions")
            conn.execute("DELETE FROM runs")
            conn.commit()

    def increment_metric(self, field: str, amount: int = 1) -> None:
        allowed = {"runs_started", "runs_completed", "exports_downloaded"}
        if field not in allowed:
            raise ValueError("invalid metric")
        with self.db.connect() as conn:
            conn.execute(
                f"UPDATE workshop_metrics SET {field} = {field} + ? WHERE id = 1",
                (amount,),
            )
            conn.commit()

    def metrics(self) -> dict[str, int]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT runs_started, runs_completed, exports_downloaded FROM workshop_metrics WHERE id = 1"
            ).fetchone()
        if not row:
            return {"runs_started": 0, "runs_completed": 0, "exports_downloaded": 0}
        return dict(row)
