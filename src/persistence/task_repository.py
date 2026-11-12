"""CRUD for user-saved task templates stored as JSON files."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.persistence.database import Database

_TASK_FIELDS = (
    "id",
    "title",
    "task",
    "background",
    "constraints",
    "time_horizon",
    "output_format",
    "source",
    "created_at",
    "updated_at",
)

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_tasks_dir() -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / "data" / "tasks"


class TaskRepository:
    def __init__(
        self,
        db: Database | None = None,
        *,
        tasks_dir: str | Path | None = None,
    ):
        self.db = db or Database()
        self.tasks_dir = Path(tasks_dir) if tasks_dir else _default_tasks_dir()
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self._maybe_import_from_sqlite()

    def _path_for(self, task_id: str) -> Path:
        if not _SAFE_ID.match(task_id):
            raise ValueError("Invalid task id.")
        return self.tasks_dir / f"{task_id}.json"

    def _write_packet(self, packet: dict[str, Any]) -> None:
        path = self._path_for(packet["id"])
        path.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _read_packet(self, path: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict) or not data.get("id"):
            return None
        packet = {key: data.get(key, "") for key in _TASK_FIELDS}
        if not packet.get("source"):
            packet["source"] = "user"
        return packet

    def _marker_path(self) -> Path:
        return self.tasks_dir / ".imported_from_sqlite"

    def _maybe_import_from_sqlite(self) -> None:
        """One-time copy of SQLite saved_tasks into files when the directory is empty."""
        marker = self._marker_path()
        if marker.exists():
            return
        existing = list(self.tasks_dir.glob("*.json"))
        if existing:
            marker.write_text("skipped: files already present\n", encoding="utf-8")
            return
        try:
            with self.db.connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, title, task, background, constraints, time_horizon,
                           output_format, created_at, updated_at
                    FROM saved_tasks
                    ORDER BY updated_at DESC
                    """
                ).fetchall()
        except Exception:  # noqa: BLE001 — DB may be missing or table unused
            marker.write_text("imported: 0\n", encoding="utf-8")
            return
        for row in rows:
            # Row may not have source column; force user for imported saved tasks.
            packet = {
                "id": row["id"],
                "title": row["title"],
                "task": row["task"],
                "background": row["background"],
                "constraints": row["constraints"],
                "time_horizon": row["time_horizon"],
                "output_format": row["output_format"],
                "source": "user",
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            try:
                self._write_packet(packet)
            except ValueError:
                continue
        marker.write_text(f"imported: {len(rows)}\n", encoding="utf-8")

    def list_tasks(self) -> list[dict[str, Any]]:
        packets: list[dict[str, Any]] = []
        for path in self.tasks_dir.glob("*.json"):
            packet = self._read_packet(path)
            if packet:
                packets.append(packet)
        packets.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        return packets

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        try:
            path = self._path_for(task_id)
        except ValueError:
            return None
        if not path.exists():
            return None
        return self._read_packet(path)

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
            "source": "user",
            "created_at": now,
            "updated_at": now,
        }
        self._write_packet(packet)
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
        if existing.get("source") == "system":
            raise ValueError("System / demo tasks cannot be edited.")
        title = (title or "").strip()
        task = (task or "").strip()
        if not title:
            raise ValueError("Title is required.")
        if not task:
            raise ValueError("Task / objective is required.")
        packet = {
            **existing,
            "title": title,
            "task": task,
            "background": (background or "").strip(),
            "constraints": (constraints or "").strip(),
            "time_horizon": (time_horizon or "").strip(),
            "output_format": (output_format or "Briefing").strip() or "Briefing",
            "source": "user",
            "updated_at": _now(),
        }
        self._write_packet(packet)
        return packet

    def delete_task(self, task_id: str) -> bool:
        try:
            path = self._path_for(task_id)
        except ValueError:
            return False
        if not path.exists():
            return False
        existing = self._read_packet(path)
        if existing and existing.get("source") == "system":
            return False
        path.unlink()
        return True
