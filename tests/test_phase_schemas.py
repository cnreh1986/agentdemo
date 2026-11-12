"""Soft coercion for Planning / Execution / Reviewer LLM JSON shapes."""

from src.agents.execution_agent import ExecutionAgent
from src.agents.planning_agent import PlanningAgent
from src.agents.reviewer_agent import ReviewerAgent
from src.demo.fixtures import build_task_spec
from src.models.deliverable import Deliverable
from src.models.plan import Plan
from src.models.review import ReviewReport, ReviewStatus
from src.models.task import TaskSpec
from src.providers.llm_base import LLMProvider, ProviderStatus


def _task() -> TaskSpec:
    return TaskSpec.model_validate(
        build_task_spec(run_id="r1", task="Arrange a birthday party", execution_mode="live")
    )


def test_plan_coerces_timeline_string_and_map():
    from_string = Plan.model_validate(
        {
            "objective": "Plan a party",
            "timeline": "Day 1: book venue; Day 2: send invites",
            "priorities": "Book venue early",
            "actions": ["Book venue", {"title": "Send invites", "description": "Email guests"}],
        }
    )
    assert isinstance(from_string.timeline, list)
    assert from_string.timeline[0]["summary"].startswith("Day 1")
    assert from_string.priorities == ["Book venue early"]
    assert len(from_string.actions) == 2
    assert from_string.actions[0].action_id == "a1"
    assert from_string.actions[1].title == "Send invites"

    from_map = Plan.model_validate(
        {
            "objective": "Plan a party",
            "timeline": {"Day 1": "Frame", "Day 2": "Execute"},
            "risks": {"text": "Budget overrun"},
        }
    )
    assert from_map.timeline == [
        {"day": "Day 1", "focus": "Frame"},
        {"day": "Day 2", "focus": "Execute"},
    ]
    assert from_map.risks == ["Budget overrun"]


def test_plan_coerces_single_timeline_object_and_priority_aliases():
    plan = Plan.model_validate(
        {
            "objective": "Ship briefing",
            "timeline": {"day": "Day 1", "focus": "Draft"},
            "actions": [
                {
                    "action_id": "a1",
                    "title": "Draft",
                    "description": "Write draft",
                    "priority": "Urgent",
                    "dependency_ids": "a0",
                }
            ],
        }
    )
    assert plan.timeline == [{"day": "Day 1", "focus": "Draft"}]
    assert plan.actions[0].priority == "high"
    assert plan.actions[0].dependency_ids == ["a0"]


def test_deliverable_coerces_string_lists_and_builds_markdown():
    doc = Deliverable.model_validate(
        {
            "title": "Birthday Briefing",
            "executive_summary": "Host a simple party.",
            "objective": "Arrange a birthday party",
            "key_findings": "Book early",
            "recommendations": {"text": "Use a checklist"},
            "action_plan": ["Invite guests", {"title": "Buy cake"}],
        }
    )
    assert doc.key_findings == ["Book early"]
    assert doc.recommendations == ["Use a checklist"]
    assert doc.action_plan == ["Invite guests", "Buy cake"]
    assert doc.markdown_content.startswith("# Birthday Briefing")


def test_review_coerces_status_score_and_criteria():
    report = ReviewReport.model_validate(
        {
            "status": "Needs Revision",
            "quality_score": "0.8",
            "criteria_results": [
                "Completeness",
                {"name": "Clarity", "passed": "yes", "note": "ok"},
            ],
            "issues": "Missing budget",
            "revision_targets": {"text": "Add budget section"},
        }
    )
    assert report.status == ReviewStatus.revision_required
    assert report.quality_score == 80
    assert report.criteria_results[0].criterion == "Completeness"
    assert report.criteria_results[1].passed is True
    assert report.issues == ["Missing budget"]
    assert report.revision_targets == ["Add budget section"]


def test_planning_agent_accepts_messy_timeline():
    class Provider(LLMProvider):
        def status(self) -> ProviderStatus:
            return ProviderStatus(True, "mock", "mock", "ok")

        def complete_json(self, **kwargs):
            return {
                "strategic_rationale": "Stay practical",
                "timeline": "Week overview as prose",
                "actions": [{"title": "Book venue", "description": "Call halls"}],
                "priorities": ["Venue first"],
            }

    result = PlanningAgent(Provider()).run(_task(), {"research": {}})
    assert result.status == "completed"
    assert result.output["objective"]
    assert isinstance(result.output["timeline"], list)


def test_execution_and_reviewer_agents_accept_messy_shapes():
    class Provider(LLMProvider):
        def __init__(self, payload):
            self.payload = payload

        def status(self) -> ProviderStatus:
            return ProviderStatus(True, "mock", "mock", "ok")

        def complete_json(self, **kwargs):
            return self.payload

    delivery = ExecutionAgent(
        Provider(
            {
                "key_findings": "Guests prefer evenings",
                "recommendations": "Keep it simple",
                "markdown_content": "# Draft\n\nHello",
            }
        )
    ).run(_task(), {"research": {}, "plan": {}})
    assert delivery.status == "completed"
    assert delivery.output["title"]
    assert delivery.output["key_findings"] == ["Guests prefer evenings"]

    review = ReviewerAgent(
        Provider(
            {
                "status": "approve",
                "quality_score": 91,
                "reviewer_summary": "Looks good",
                "criteria_results": [],
            }
        )
    ).run(
        _task(),
        {"research": {}, "plan": {}, "deliverable": delivery.output},
    )
    assert review.status == "completed"
    assert review.output["status"] == "approved"
