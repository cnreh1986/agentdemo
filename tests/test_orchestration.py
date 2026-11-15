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


# --- Task classes (job_search / competitive_analysis) -------------------------------------

JOB_TASK = "Find product manager jobs in Hyderabad, 5-10 years of experience, posted in the last 7 days."


def test_job_search_demo_branches_through_every_stage_and_stops_at_human_gate():
    runner = WorkforceRunner(DemoProvider(), max_revisions=1)
    state = runner.run(task=JOB_TASK, mode="demo")
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    assert state["task_specification"]["task_class"] == "job_search"
    assert state["job_intent"]["experience"] == {"min_years": 5, "max_years": 10, "range_policy": "overlap"}
    env = state["job_envelope"]
    assert env["illustrative"] is True
    assert env["jobs"] and env["needs_review"] and env["excluded"]
    assert state["research"]["evidence_items"] == []
    assert state["review"]["status"] == "approved"
    assert state["approval_status"] is None
    assert "demo-hyd-pm-1" in state["deliverable"]["markdown_content"]
    assert state["comparison_envelope"] is None


def test_competitive_analysis_demo_branches_and_thin_context_waits():
    runner = WorkforceRunner(DemoProvider(), max_revisions=1)
    rich = runner.run(
        task="Compare product manager and product marketer for our next hire.",
        background="We are an 80-person B2B SaaS company in Hyderabad. We have one technical product manager. "
        "We have no product marketer. Our product manager already writes the release notes and joins the first sales call.",
        constraints="One headcount next quarter. Audience is the founder. Do not name a candidate.",
        time_horizon="Next quarter",
        mode="demo",
    )
    assert rich["task_specification"]["task_class"] == "competitive_analysis"
    assert rich["comparison_envelope"]["status"] == "ready"
    assert rich["status"] == "AWAITING_HUMAN_APPROVAL" and rich["job_envelope"] is None

    thin = runner.run(task="Compare product manager and product marketer.", mode="demo")
    assert thin["comparison_envelope"]["status"] == "needs_context"
    assert thin["comparison_envelope"]["matrix"] == []
    assert thin["review"]["status"] == "approved"


def test_briefing_runs_keep_default_task_class():
    state = WorkforceRunner(DemoProvider(), max_revisions=1).run(task="Plan my next productive week.", mode="demo")
    assert state["task_specification"]["task_class"] == "briefing"
    assert state["job_envelope"] is None and state["comparison_envelope"] is None
    assert state["revision_count"] == 1


def test_human_revision_keeps_job_envelope():
    from src.services.run_service import RunService

    service = RunService()
    state = service.start_run(task=JOB_TASK, mode="demo")
    revised = service.apply_human_decision(state, decision="revise", note="Shorten the summary.")
    assert revised["status"] == "AWAITING_HUMAN_APPROVAL"
    assert revised["job_envelope"]["counts"]["included"] == state["job_envelope"]["counts"]["included"]
    assert "demo-hyd-pm-1" in revised["deliverable"]["markdown_content"]
