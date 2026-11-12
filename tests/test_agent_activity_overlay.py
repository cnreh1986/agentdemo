from src.orchestration.events import sanitize_value
from src.orchestration.runner import WorkforceRunner
from src.providers.demo_provider import DemoProvider
from src.ui.agent_activity_overlay import (
    AGENT_ACTIVITY_COPY,
    active_stage_key,
    progress_fraction,
    summarise_packet,
)


def test_activity_copy_covers_pipeline_stages():
    for key in ("orchestrator", "research", "planning", "execution", "reviewer", "human_approval"):
        assert key in AGENT_ACTIVITY_COPY
        assert AGENT_ACTIVITY_COPY[key]["what"]
        assert AGENT_ACTIVITY_COPY[key]["steps"]


def test_progress_and_active_stage_helpers():
    state = {
        "status": "PLANNING_RUNNING",
        "current_stage": "planning",
        "node_states": {
            "orchestrator": "Completed",
            "research": "Completed",
            "planning": "Running",
            "execution": "Waiting",
            "reviewer": "Waiting",
            "human_approval": "Waiting",
        },
    }
    assert active_stage_key(state) == "planning"
    frac = progress_fraction(state)
    assert 0.2 < frac < 1.0
    done = {**state, "status": "AWAITING_HUMAN_APPROVAL", "node_states": {k: "Completed" for k in state["node_states"]}}
    assert progress_fraction(done) == 1.0


def test_packet_summaries():
    research_lines = summarise_packet(
        "research",
        {
            "key_findings": ["a", "b"],
            "evidence_items": [],
            "research_limitations": ["No live search"],
        },
    )
    assert any("Key findings: 2" in line for line in research_lines)
    plan_lines = summarise_packet(
        "plan",
        {"actions": [{"title": "Book venue"}, {"title": "Send invites"}, {"title": "Buy cake"}]},
    )
    assert any("Actions: 3" in line for line in plan_lines)
    assert any("Book venue" in line for line in plan_lines)


def test_summaries_sanitise_secrets():
    dirty = {"objective": "task", "api_key": "sk-abcdefghijklmnop", "note": "token=secret123"}
    cleaned = sanitize_value(dirty)
    assert "api_key" not in cleaned
    assert "sk-abcdefghijklmnop" not in str(cleaned)
    lines = summarise_packet("task", cleaned)
    joined = " ".join(lines)
    assert "sk-" not in joined


def test_demo_run_emits_multiple_on_update_callbacks():
    snapshots: list[dict] = []

    def on_update(state: dict) -> None:
        snapshots.append(
            {
                "status": state.get("status"),
                "stage": state.get("current_stage"),
                "nodes": dict(state.get("node_states") or {}),
            }
        )

    state = WorkforceRunner(DemoProvider(), max_revisions=1).run(
        task="Plan my next productive week.",
        mode="demo",
        on_update=on_update,
    )
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    # Seed + per-node stream values should exceed the old seed+final pattern.
    assert len(snapshots) > 2
    completed_or_running = []
    for snap in snapshots:
        nodes = snap["nodes"]
        for key in ("research", "planning", "execution", "reviewer"):
            if nodes.get(key) in {"Running", "Completed", "Needs revision"}:
                completed_or_running.append(key)
    assert "research" in completed_or_running
    assert "planning" in completed_or_running
