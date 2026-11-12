"""CRUD for user-saved task templates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.persistence.database import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskRepository:
    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def list_tasks(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, title, task, background, constraints, time_horizon,
                       output_format, created_at, updated_at
                FROM saved_tasks
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT id, title, task, background, constraints, time_horizon,
                       output_format, created_at, updated_at
                FROM saved_tasks WHERE id = ?
                """,
                (task_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_task(
        self,
        *,
        title: str,
        task: str,
        background: str = "",
        constraints: str = "",
        time_horizon: str = "",
        output_format: str = "Briefing",
    ) -> dict[str, Any]:
        title = (title or "").strip()
        task = (task or "").strip()
        if not title:
            raise ValueError("Title is required.")
        if not task:
            raise ValueError("Task / objective is required.")
        now = _now()
        task_id = str(uuid4())
        packet = {
            "id": task_id,
            "title": title,
            "task": task,
            "background": (background or "").strip(),
            "constraints": (constraints or "").strip(),
            "time_horizon": (time_horizon or "").strip(),
            "output_format": (output_format or "Briefing").strip() or "Briefing",
            "created_at": now,
            "updated_at": now,
        }
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO saved_tasks (
                    id, title, task, background, constraints, time_horizon,
                    output_format, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    packet["id"],
                    packet["title"],
                    packet["task"],
                    packet["background"],
                    packet["constraints"],
                    packet["time_horizon"],
                    packet["output_format"],
                    packet["created_at"],
                    packet["updated_at"],
                ),
            )
            conn.commit()
        return packet

    def update_task(
        self,
        task_id: str,
        *,
        title: str,
        task: str,
        background: str = "",
        constraints: str = "",
        time_horizon: str = "",
        output_format: str = "Briefing",
    ) -> dict[str, Any]:
        existing = self.get_task(task_id)
        if not existing:
            raise ValueError("Task not found.")
        title = (title or "").strip()
        task = (task or "").strip()
        if not title:
            raise ValueError("Title is required.")
        if not task:
            raise ValueError("Task / objective is required.")
        now = _now()
        packet = {
            **existing,
            "title": title,
            "task": task,
            "background": (background or "").strip(),
            "constraints": (constraints or "").strip(),
            "time_horizon": (time_horizon or "").strip(),
            "output_format": (output_format or "Briefing").strip() or "Briefing",
            "updated_at": now,
        }
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE saved_tasks
                SET title = ?, task = ?, background = ?, constraints = ?,
                    time_horizon = ?, output_format = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    packet["title"],
                    packet["task"],
                    packet["background"],
                    packet["constraints"],
                    packet["time_horizon"],
                    packet["output_format"],
                    packet["updated_at"],
                    task_id,
                ),
            )
            conn.commit()
        return packet

    def delete_task(self, task_id: str) -> bool:
        with self.db.connect() as conn:
            cur = conn.execute("DELETE FROM saved_tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cur.rowcount > 0
