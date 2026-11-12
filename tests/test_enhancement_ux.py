"""Auto-approve, pause/resume, and notice helpers from enhancement.md §§4–6."""

from __future__ import annotations

from src.orchestration.runner import WorkforceRunner, mark_paused, review_is_clean
from src.providers.demo_provider import DemoProvider
from src.services.run_service import AUTO_APPROVE_NOTE, RunService


class AlwaysApproveReviewProvider(DemoProvider):
    def __init__(self):
        super().__init__(force_revision_first=False)


def test_review_is_clean_for_awaiting_approved_review():
    runner = WorkforceRunner(AlwaysApproveReviewProvider(), max_revisions=1)
    state = runner.run(task="Plan my next productive week.", mode="demo")
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    assert review_is_clean(state) is True
    assert RunService.can_auto_approve(state) is True


def test_auto_approve_records_human_origin_event():
    runner = WorkforceRunner(AlwaysApproveReviewProvider(), max_revisions=1)
    state = runner.run(task="Plan my next productive week.", mode="demo")
    service = RunService()
    updated = service.apply_human_decision(
        state,
        decision="approve",
        note=AUTO_APPROVE_NOTE,
    )
    assert updated["status"] == "HUMAN_APPROVED"
    assert updated["approval_note"] == AUTO_APPROVE_NOTE
    events = updated["events"]
    assert any(
        e.get("event_type") == "human_approved"
        and "Auto-approved from user setting" in (e.get("message") or "")
        for e in events
    )


def test_dirty_review_not_auto_approvable_after_gate():
    # Force a failed path isn't needed — unresolved issues on awaiting state
    dirty = {
        "status": "AWAITING_HUMAN_APPROVAL",
        "review": {"status": "revision_required", "issues": ["x"]},
        "unresolved_issues": ["x"],
    }
    assert review_is_clean(dirty) is False
    assert RunService.can_auto_approve(dirty) is False


def test_pause_after_first_stage_keeps_run_id_and_resume_finishes():
    service = RunService()
    first = service.begin_run(task="Plan my next productive week.", mode="demo")
    run_id = first["run_id"]
    assert service.run_has_more_stages(first) is True

    paused = service.pause_run(first)
    assert paused["status"] == "PAUSED"
    assert paused["run_id"] == run_id
    assert paused.get("paused_after_stage")
    assert any(e.get("event_type") == "run_paused" for e in paused["events"])

    # Resume from the same checkpoint / run_id until the human gate.
    state = first
    guard = 0
    while service.run_has_more_stages(state) and (state.get("status") or "") != "FAILED":
        state = service.advance_run(state)
        guard += 1
        assert state["run_id"] == run_id
        assert guard < 30

    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    assert state["research"] is not None
    assert state["deliverable"] is not None


def test_begin_run_returns_before_full_completion():
    service = RunService()
    partial = service.begin_run(task="Create a learning roadmap for a new skill.", mode="demo")
    assert partial["run_id"]
    # First interrupt is after validate — should not yet be awaiting human.
    assert partial["status"] != "AWAITING_HUMAN_APPROVAL"
    assert service.run_has_more_stages(partial) is True
