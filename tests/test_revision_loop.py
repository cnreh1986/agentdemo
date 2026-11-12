from src.orchestration.runner import WorkforceRunner
from src.providers.demo_provider import DemoProvider
from src.services.run_service import RunService


class AlwaysReviseProvider(DemoProvider):
    def complete_json(self, *, system_prompt, user_prompt, schema_name, temperature=None):
        data = super().complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name=schema_name,
            temperature=temperature,
        )
        if schema_name == "review":
            data["status"] = "revision_required"
            data["issues"] = ["Still needs work"]
            data["recommendations"] = ["Improve clarity"]
            data["revision_targets"] = ["execution"]
        return data


def test_revision_limit_stops_at_human_gate():
    runner = WorkforceRunner(AlwaysReviseProvider(), max_revisions=1)
    state = runner.run(task="Plan my next productive week.", mode="demo")
    assert state["revision_count"] == 1
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    assert state["review"]["status"] == "revision_required"
    assert state.get("unresolved_issues")


def test_human_revision_respects_cap():
    service = RunService()
    state = service.start_run(task="Plan my next productive week.", mode="demo")
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    # Demo already used 1 revision; human request should hit limit
    updated = service.apply_human_decision(state, decision="revise", note="Add more detail")
    assert updated["status"] == "AWAITING_HUMAN_APPROVAL"
    assert any(
        e["event_type"] in {"revision_limit_reached", "human_revision_requested"}
        for e in updated["events"]
    )
