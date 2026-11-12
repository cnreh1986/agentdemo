from src.services.run_service import RunService


def test_human_approve_recorded():
    service = RunService()
    state = service.start_run(task="Plan my next productive week.", mode="demo")
    updated = service.apply_human_decision(state, decision="approve", note="Looks good")
    assert updated["status"] == "HUMAN_APPROVED"
    assert updated["approval_status"] == "approved"
    assert updated["approval_at"]
    assert updated["approval_note"] == "Looks good"
    assert any(e["event_type"] == "human_approved" for e in updated["events"])


def test_human_reject_recorded():
    service = RunService()
    state = service.start_run(task="Plan my next productive week.", mode="demo")
    updated = service.apply_human_decision(state, decision="reject", note="Not useful")
    assert updated["status"] == "HUMAN_REJECTED"
    assert updated["approval_status"] == "rejected"
    assert any(e["event_type"] == "human_rejected" for e in updated["events"])


def test_cannot_be_human_approved_without_decision():
    service = RunService()
    state = service.start_run(task="Plan my next productive week.", mode="demo")
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    assert state.get("approval_status") is None
