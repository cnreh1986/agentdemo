from pathlib import Path

from src.persistence.database import Database
from src.persistence.repositories import RunRepository
from src.services.run_service import RunService


def test_save_list_reload_and_clear(tmp_path: Path):
    db = Database(tmp_path / "test.db")
    repo = RunRepository(db)
    state = RunService().start_run(task="Plan my next productive week.", mode="demo")
    repo.save_run(state)
    rows = repo.list_runs()
    assert len(rows) == 1
    loaded = repo.get_run(state["run_id"])
    assert loaded is not None
    assert loaded["run_id"] == state["run_id"]
    assert "api_key" not in str(loaded).lower() or "sk-" not in str(loaded)
    repo.clear_all()
    assert repo.list_runs() == []


def test_live_mode_blocked_without_credentials(monkeypatch):
    from src.config import settings as settings_mod

    settings_mod.clear_settings_cache()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings_mod.clear_settings_cache()
    service = RunService()
    try:
        service.start_run(task="Plan my week", mode="live")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "credentials" in str(exc).lower()
    finally:
        settings_mod.clear_settings_cache()
