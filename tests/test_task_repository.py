from pathlib import Path

import pytest

from src.persistence.database import Database
from src.persistence.task_repository import TaskRepository


def test_task_crud(tmp_path: Path):
    repo = TaskRepository(Database(tmp_path / "tasks.db"))
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

    listed = repo.list_tasks()
    assert len(listed) == 1
    assert listed[0]["task"] == "Plan my next productive week."

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
    assert repo.get_task(created["id"])["task"] == "Plan a focused week."

    assert repo.delete_task(created["id"]) is True
    assert repo.get_task(created["id"]) is None
    assert repo.list_tasks() == []
    assert repo.delete_task(created["id"]) is False


def test_create_requires_title_and_task(tmp_path: Path):
    repo = TaskRepository(Database(tmp_path / "tasks.db"))
    with pytest.raises(ValueError, match="Title"):
        repo.create_task(title="  ", task="Something")
    with pytest.raises(ValueError, match="Task"):
        repo.create_task(title="T", task="")
