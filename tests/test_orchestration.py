from src.orchestration.runner import WorkforceRunner
from src.providers.demo_provider import DemoProvider
from src.providers.llm_base import LLMProvider, ProviderError, ProviderStatus


class FailOnExecutionProvider(DemoProvider):
    def complete_json(self, *, system_prompt, user_prompt, schema_name, temperature=None):
        if schema_name == "deliverable":
            raise ProviderError("Simulated execution failure", code="exec_fail")
        return super().complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name=schema_name,
            temperature=temperature,
        )


class AlwaysApproveReviewProvider(DemoProvider):
    def __init__(self):
        super().__init__(force_revision_first=False)


def test_demo_graph_order_and_human_gate():
    runner = WorkforceRunner(DemoProvider(), max_revisions=1)
    state = runner.run(task="Plan my next productive week.", mode="demo")
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    assert state["revision_count"] == 1
    assert state["research"] is not None
    assert state["plan"] is not None
    assert state["deliverable"] is not None
    assert state["review"]["status"] == "approved"
    assert state["approval_status"] is None
    stages = [e["stage"] for e in state["events"] if e["event_type"] in {"agent_started", "specification_created"}]
    assert "orchestrator" in stages or any(e["event_type"] == "specification_created" for e in state["events"])
    assert any(e["event_type"] == "human_approval_requested" for e in state["events"])


def test_reviewer_approved_does_not_set_human_approved():
    runner = WorkforceRunner(AlwaysApproveReviewProvider(), max_revisions=1)
    state = runner.run(task="Research a product opportunity and prepare a brief.", mode="demo")
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    assert state["status"] != "HUMAN_APPROVED"


def test_failed_execution_preserves_prior_outputs():
    runner = WorkforceRunner(FailOnExecutionProvider(), max_revisions=1)
    state = runner.run(task="Create a learning roadmap for a new skill.", mode="demo")
    assert state["status"] == "FAILED"
    assert state["research"] is not None
    assert state["plan"] is not None
    assert state.get("deliverable") in (None, {})
