from pydantic import BaseModel, Field

from src.agents.base import Agent
from src.agents.research_agent import ResearchAgent
from src.demo.fixtures import build_task_spec
from src.models.research import ResearchPacket
from src.models.task import TaskSpec
from src.orchestration.runner import WorkforceRunner
from src.providers.demo_provider import DemoProvider
from src.providers.llm_base import LLMProvider, ProviderStatus


class StrictPacket(BaseModel):
    run_id: str
    research_question: str
    key_findings: list[str] = Field(min_length=1)


def _task(text: str = "Arrange a birthday party") -> TaskSpec:
    return TaskSpec.model_validate(
        build_task_spec(run_id="run-123", task=text, execution_mode="live")
    )


def test_coerce_string_findings_and_soft_evidence():
    packet = ResearchPacket.model_validate(
        {
            "run_id": "r1",
            "research_question": "Where to host a birthday?",
            "key_findings": "Book a venue early",
            "assumptions": {"text": "Guests prefer evenings"},
            "evidence_items": [
                {
                    "claim": "Hall X seats 150",
                    "source_url": "not-a-url",
                    "evidence_type": "model",
                    "confidence": 0.9,
                },
                "plain string evidence",
                {"claim": "bad", "evidence_type": "totally_invalid"},
            ],
            "research_limitations": "Model knowledge only",
        }
    )
    assert packet.key_findings == ["Book a venue early"]
    assert packet.assumptions == ["Guests prefer evenings"]
    assert packet.research_limitations == ["Model knowledge only"]
    assert len(packet.evidence_items) >= 2
    assert packet.evidence_items[0].source_url is None
    assert packet.evidence_items[0].evidence_type.value == "model_synthesis"
    assert packet.evidence_items[0].confidence.value == "high"


def test_research_agent_fills_missing_run_id():
    class Provider(LLMProvider):
        def status(self) -> ProviderStatus:
            return ProviderStatus(True, "mock", "mock", "ok")

        def complete_json(self, **kwargs):
            return {
                "research_question": "Birthday venue options",
                "key_findings": ["Book early"],
                "evidence_items": [],
                "assumptions": [],
                "uncertainties": [],
                "risks": [],
                "open_questions": [],
                "research_limitations": ["No live search"],
                "status": "completed",
                "agent_summary": "Draft research",
            }

    result = ResearchAgent(Provider()).run(_task(), {})
    assert result.status == "completed"
    assert result.output["run_id"] == "run-123"


def test_agent_retries_on_validation_error():
    class RetryProvider(LLMProvider):
        def __init__(self):
            self.calls = 0

        def status(self) -> ProviderStatus:
            return ProviderStatus(True, "mock", "mock", "ok")

        def complete_json(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return {"run_id": "r1", "research_question": "q", "key_findings": []}
            return {"run_id": "r1", "research_question": "q", "key_findings": ["one"]}

    class StrictAgent(Agent):
        name = "research"
        schema_name = "research"
        output_model = StrictPacket

        def build_user_prompt(self, task, context):
            return "{}"

    provider = RetryProvider()
    result = StrictAgent(provider).run(_task(), {})
    assert result.status == "completed"
    assert provider.calls == 2
    assert result.output["key_findings"] == ["one"]


def test_agent_surfaces_detailed_validation_issues():
    class BadProvider(LLMProvider):
        def status(self) -> ProviderStatus:
            return ProviderStatus(True, "mock", "mock", "ok")

        def complete_json(self, **kwargs):
            return {"run_id": "r1", "research_question": "q", "key_findings": []}

    class StrictAgent(Agent):
        name = "research"
        schema_name = "research"
        output_model = StrictPacket

        def build_user_prompt(self, task, context):
            return "{}"

    result = StrictAgent(BadProvider()).run(_task(), {})
    assert result.status == "failed"
    assert result.issues
    assert any("key_findings" in issue for issue in result.issues)


def test_demo_research_still_completes():
    state = WorkforceRunner(DemoProvider(), max_revisions=1).run(
        task="Arrange a birthday party for 20 guests",
        mode="demo",
    )
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    assert state["research"] is not None
