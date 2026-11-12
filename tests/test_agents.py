from src.agents.execution_agent import ExecutionAgent
from src.agents.planning_agent import PlanningAgent
from src.agents.research_agent import ResearchAgent
from src.agents.reviewer_agent import ReviewerAgent
from src.demo.fixtures import build_task_spec
from src.models.task import TaskSpec
from src.providers.demo_provider import DemoProvider
from src.providers.llm_base import LLMProvider, ProviderStatus


class BadProvider(LLMProvider):
    def status(self) -> ProviderStatus:
        return ProviderStatus(True, "bad", "bad", "ok")

    def complete_json(self, **kwargs):
        return {"not": "valid for research"}


def _task() -> TaskSpec:
    return TaskSpec.model_validate(
        build_task_spec(run_id="r1", task="Plan my next productive week.", execution_mode="demo")
    )


def test_agents_complete_with_demo_provider():
    provider = DemoProvider()
    task = _task()
    research = ResearchAgent(provider).run(task, {})
    assert research.status == "completed"
    assert research.output["evidence_items"] == []
    assert any("not live-verified" in x.lower() or "Demo Mode" in x for x in research.output["research_limitations"])

    plan = PlanningAgent(provider).run(task, {"research": research.output})
    assert plan.status == "completed"
    assert plan.output["actions"]

    delivery = ExecutionAgent(provider).run(
        task, {"research": research.output, "plan": plan.output}
    )
    assert delivery.status == "completed"

    review = ReviewerAgent(provider).run(
        task,
        {"research": research.output, "plan": plan.output, "deliverable": delivery.output},
    )
    assert review.status == "needs_revision"


def test_invalid_agent_output_fails_validation():
    result = ResearchAgent(BadProvider()).run(_task(), {})
    assert result.status == "failed"
    assert result.issues
