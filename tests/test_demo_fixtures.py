from src.demo.fixtures import build_demo_packets
from src.demo.runner import DemoRunner


REQUIRED_RESEARCH = {
    "run_id",
    "research_question",
    "key_findings",
    "evidence_items",
    "assumptions",
    "uncertainties",
    "risks",
    "open_questions",
    "research_limitations",
    "status",
    "agent_summary",
}


def test_demo_packets_shape():
    packets = build_demo_packets(task="Plan my next productive week.")
    assert packets["research"].keys() >= REQUIRED_RESEARCH
    assert packets["research"]["evidence_items"] == []
    assert any("Demo Mode" in x for x in packets["research"]["research_limitations"])
    assert packets["review_v1"]["status"] == "revision_required"
    assert packets["review_v2"]["status"] == "approved"
    assert "markdown_content" in packets["deliverable_v2"]


def test_demo_runner_end_to_end():
    runner = DemoRunner(max_revisions=1, step_delay_s=0)
    state = runner.run(task="Plan my next productive week.")
    assert state["mode"] == "demo"
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    assert state["revision_count"] == 1
    assert state["research"] is not None
    assert state["plan"] is not None
    assert state["deliverable"]["status"] == "revised"
    assert state["review"]["status"] == "approved"
    assert state["deliverable_original"] is not None
    assert any(e["event_type"] == "human_approval_requested" for e in state["events"])
    assert "illustrative" in state["demo_disclaimer"].lower() or "Demo Mode" in state["demo_disclaimer"]
