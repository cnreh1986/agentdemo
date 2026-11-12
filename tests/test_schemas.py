from src.demo.fixtures import build_demo_packets
from src.models.deliverable import Deliverable
from src.models.plan import Plan
from src.models.research import ResearchPacket
from src.models.review import ReviewReport
from src.models.task import TaskSpec
from src.orchestration.events import make_event, sanitize_value


def test_fixtures_validate_against_schemas():
    packets = build_demo_packets(task="Plan my next productive week.")
    TaskSpec.model_validate(packets["task_specification"])
    ResearchPacket.model_validate(packets["research"])
    Plan.model_validate(packets["plan"])
    Deliverable.model_validate(packets["deliverable_v1"])
    ReviewReport.model_validate(packets["review_v1"])
    ReviewReport.model_validate(packets["review_v2"])


def test_out_of_range_review_score_is_clamped():
    report = ReviewReport.model_validate(
        {"status": "approved", "quality_score": 150, "reviewer_summary": "ok"}
    )
    assert report.quality_score == 100
    low = ReviewReport.model_validate(
        {"status": "approved", "quality_score": -5, "reviewer_summary": "ok"}
    )
    assert low.quality_score == 0


def test_event_sanitises_secrets():
    event = make_event(
        run_id="r1",
        stage="system",
        event_type="test",
        status="ok",
        message="Using api_key=sk-abcdefghijklmnop",
        metadata={"OPENAI_API_KEY": "sk-secret", "model": "gpt"},
    )
    assert "sk-abcdefghijklmnop" not in event["message"]
    assert "OPENAI_API_KEY" not in event["metadata"]
    assert event["metadata"]["model"] == "gpt"
    assert "[REDACTED]" in sanitize_value("Bearer abcdefghijklmnop")
