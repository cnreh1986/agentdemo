import json
from pathlib import Path

import pytest

from src.config.samples import list_system_tasks
from src.persistence.database import Database
from src.persistence.task_repository import TaskRepository


def test_task_crud(tmp_path: Path):
    tasks_dir = tmp_path / "tasks"
    repo = TaskRepository(Database(tmp_path / "tasks.db"), tasks_dir=tasks_dir)
    assert repo.list_tasks() == []

    created = repo.create_task(
        title="My week",
        task="Plan my next productive week.",
        background="PM context",
        constraints="No weekends",
        time_horizon="5 days",
        output_format="Action Plan",
    )
    assert created["id"]
    assert created["title"] == "My week"
    assert created["source"] == "user"
    task_file = tasks_dir / f"{created['id']}.json"
    assert task_file.exists()
    on_disk = json.loads(task_file.read_text(encoding="utf-8"))
    assert on_disk["source"] == "user"

    listed = repo.list_tasks()
    assert len(listed) == 1
    assert listed[0]["task"] == "Plan my next productive week."
    assert listed[0]["source"] == "user"

    got = repo.get_task(created["id"])
    assert got is not None
    assert got["background"] == "PM context"

    updated = repo.update_task(
        created["id"],
        title="My week v2",
        task="Plan a focused week.",
        background="Updated",
        constraints="Protect evenings",
        time_horizon="1 week",
        output_format="Briefing",
    )
    assert updated["title"] == "My week v2"
    assert updated["source"] == "user"
    assert repo.get_task(created["id"])["task"] == "Plan a focused week."
    assert task_file.exists()

    assert repo.delete_task(created["id"]) is True
    assert not task_file.exists()
    assert repo.get_task(created["id"]) is None
    assert repo.list_tasks() == []
    assert repo.delete_task(created["id"]) is False


def test_create_requires_title_and_task(tmp_path: Path):
    repo = TaskRepository(Database(tmp_path / "tasks.db"), tasks_dir=tmp_path / "tasks")
    with pytest.raises(ValueError, match="Title"):
        repo.create_task(title="  ", task="Something")
    with pytest.raises(ValueError, match="Task"):
        repo.create_task(title="T", task="")


def test_imports_sqlite_once(tmp_path: Path):
    db = Database(tmp_path / "tasks.db")
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO saved_tasks (
                id, title, task, background, constraints, time_horizon,
                output_format, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-task-1",
                "Legacy",
                "Do the thing",
                "",
                "",
                "",
                "Briefing",
                "2024-01-01T00:00:00+00:00",
                "2024-01-02T00:00:00+00:00",
            ),
        )
        conn.commit()

    tasks_dir = tmp_path / "tasks"
    repo = TaskRepository(db, tasks_dir=tasks_dir)
    listed = repo.list_tasks()
    assert len(listed) == 1
    assert listed[0]["title"] == "Legacy"
    assert listed[0]["source"] == "user"
    assert (tasks_dir / "legacy-task-1.json").exists()

    assert repo.delete_task("legacy-task-1") is True
    # Second init must not re-import deleted SQLite rows.
    repo2 = TaskRepository(db, tasks_dir=tasks_dir)
    assert repo2.list_tasks() == []


def test_cannot_delete_system_source_file(tmp_path: Path):
    tasks_dir = tmp_path / "tasks"
    repo = TaskRepository(Database(tmp_path / "tasks.db"), tasks_dir=tasks_dir)
    system_id = "system-protected-1"
    packet = {
        "id": system_id,
        "title": "Protected demo",
        "task": "Do not delete me",
        "background": "",
        "constraints": "",
        "time_horizon": "",
        "output_format": "Briefing",
        "source": "system",
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
    }
    path = tasks_dir / f"{system_id}.json"
    path.write_text(json.dumps(packet), encoding="utf-8")

    assert repo.delete_task(system_id) is False
    assert path.exists()
    with pytest.raises(ValueError, match="System"):
        repo.update_task(
            system_id,
            title="Hacked",
            task="Nope",
            background="",
            constraints="",
            time_horizon="",
            output_format="Briefing",
        )


def test_list_system_tasks_helper():
    packets = list_system_tasks()
    assert len(packets) >= 3
    assert all(p["source"] == "system" for p in packets)
    assert all(p["id"].startswith("system-") for p in packets)
    assert {p["title"] for p in packets} >= {
        "Plan my next productive week.",
        "Research a product opportunity and prepare a brief.",
        "Create a learning roadmap for a new skill.",
    }


def test_missing_source_defaults_to_user(tmp_path: Path):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(parents=True)
    legacy_id = "legacy-no-source"
    path = tasks_dir / f"{legacy_id}.json"
    path.write_text(
        json.dumps(
            {
                "id": legacy_id,
                "title": "Old file",
                "task": "Legacy packet without source",
                "background": "",
                "constraints": "",
                "time_horizon": "",
                "output_format": "Briefing",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    # Marker so init does not try sqlite import over empty-looking dir wait — files exist so skip import
    (tasks_dir / ".imported_from_sqlite").write_text("skipped\n", encoding="utf-8")
    repo = TaskRepository(Database(tmp_path / "tasks.db"), tasks_dir=tasks_dir)
    got = repo.get_task(legacy_id)
    assert got is not None
    assert got["source"] == "user"
