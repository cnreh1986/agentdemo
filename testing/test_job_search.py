"""Unit tests for the job_search task class (newehancement.md sections 2-16, SerpAPI build)."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.agents.execution_agent import ExecutionAgent
from src.agents.research_agent import LIVE_JOBS_REQUIRED_MESSAGE, ResearchAgent
from src.agents.reviewer_agent import ReviewerAgent
from src.config.samples import (
    SAMPLE_COMPARE_RICH_LABEL,
    SAMPLE_COMPARE_THIN_LABEL,
    SAMPLE_JOBS_LABEL,
    SAMPLE_TASKS,
)
from src.config.settings import Settings
from src.demo.fixtures import build_demo_job_envelope, build_demo_job_records
from src.models.job_search import JobRecord, JobSearchEnvelope
from src.models.task import TaskSpec
from src.orchestration.runner import WorkforceRunner
from src.providers.demo_provider import DemoProvider
from src.providers.serpapi_jobs import (
    SERPAPI_SEARCH_URL,
    JobsFetchResult,
    JobsProviderError,
    SerpApiJobsProvider,
)
from src.services.export_service import ExportService
from src.services.job_intent import (
    apply_job_filters,
    classify_task_class,
    experience_match_for,
    ground_job_envelope,
    location_match_for,
    parse_experience_from_source,
    parse_experience_range,
    parse_job_search_intent,
    parse_location,
    parse_posted_label,
    parse_posted_within_days,
    scrub_ungrounded_refs,
    title_in_family,
)
from src.services.run_service import RunService
from src.services.task_class_review import check_job_search

TASK = "Find product manager jobs in Hyderabad, 5–10 years of experience, posted in the last 7 days."
NOW = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)


def rec(
    job_id="x-1",
    title="Senior Product Manager",
    company="Acme Pvt Ltd",
    loc="Hyderabad, Telangana, India",
    days_ago=2,
    exp="6-9 years",
    desc="Own the roadmap.",
    **kw,
) -> JobRecord:
    base = dict(
        job_id=job_id,
        source="serpapi",
        source_job_id=job_id,
        title=title,
        company_name=company,
        job_description=desc,
        description_completeness="full",
        location_text=loc,
        city=loc.split(",")[0],
        country_code="IN",
        date_posted=(NOW - timedelta(days=days_ago)).isoformat(),
        experience_text=exp,
        apply_url=f"https://jobs.example.test/{job_id}",
        retrieved_at=NOW.isoformat(),
    )
    base.update(kw)
    return JobRecord(**base)


def intent(task=TASK):
    return parse_job_search_intent(task)


def run(records, task=TASK, **kw):
    return apply_job_filters(records, intent(task), retrieved_at=NOW, source_name="serpapi", **kw)


# ----------------------------------------------------------------- classification


@pytest.mark.parametrize(
    "task,expected",
    [
        (TASK, "job_search"),
        ("Create a task: product manager jobs in Hyderabad with 5-10 years", "job_search"),
        ("Search for senior product manager openings in Pune", "job_search"),
        ("Compare product manager and product marketer for our next hire.", "competitive_analysis"),
        ("PM vs PMM for my situation", "competitive_analysis"),
        ("Plan my next productive week.", "briefing"),
        ("Research a product opportunity and prepare a brief.", "briefing"),
        ("Create a learning roadmap for a new skill.", "briefing"),
        ("", "briefing"),
    ],
)
def test_classify_task_class(task, expected):
    assert classify_task_class(task) == expected


def test_samples_classify_as_designed():
    jobs = SAMPLE_TASKS[SAMPLE_JOBS_LABEL]
    assert classify_task_class(jobs["task"], jobs["background"], jobs["constraints"]) == "job_search"
    for label in (SAMPLE_COMPARE_RICH_LABEL, SAMPLE_COMPARE_THIN_LABEL):
        p = SAMPLE_TASKS[label]
        assert classify_task_class(p["task"], p["background"], p["constraints"]) == "competitive_analysis"


# ----------------------------------------------------------------- intent parsing


def test_parse_intent_target_sentence():
    i = intent()
    assert i.task_class == "job_search"
    assert i.role_query == "product manager"
    assert i.role_family == "product_management"
    assert i.location.city == "Hyderabad"
    assert i.location.region == "Telangana"
    assert i.location.country_code == "IN"
    assert i.location.radius_km == 40
    assert i.location.accept_remote is False
    assert (i.experience.min_years, i.experience.max_years) == (5, 10)
    assert i.experience.range_policy == "overlap"
    assert i.posted_within_days == 7
    assert i.open_filters == []
    for alias in ("hyd", "cyberabad", "hitec city", "gachibowli", "madhapur", "kondapur"):
        assert alias in i.location.aliases
    assert "project manager" in i.title_exclude
    assert "product marketing" in i.title_exclude
    assert "technical product manager" in i.title_include


def test_open_filters_listed_when_slots_missing():
    i = parse_job_search_intent("Find product manager jobs")
    assert set(i.open_filters) == {"location", "experience", "recency"}
    assert i.posted_within_days is None
    assert i.experience.min_years is None


def test_industry_words_become_remainder_not_dropped():
    i = parse_job_search_intent("Find fintech product manager jobs in Hyderabad, 5-10 years")
    assert "fintech" in i.unparsed_remainder


def test_remote_only_when_user_asks():
    assert parse_job_search_intent("Find PM jobs in Hyderabad, remote ok").location.accept_remote is True
    assert parse_job_search_intent(TASK).location.accept_remote is False


def test_hyderabad_sindh_country_wins():
    city, region, cc, _ = parse_location("product manager jobs in Hyderabad, Sindh")
    assert (city, region, cc) == ("Hyderabad", "Sindh", "PK")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("last 7 days", 7),
        ("posted in the past week", 7),
        ("posted this week", 7),
        ("last 3 days", 3),
        ("past 2 weeks", 14),
        ("last 24 hours", 1),
        ("no recency here", None),
    ],
)
def test_parse_posted_within_days(text, expected):
    assert parse_posted_within_days(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("5–10 years of experience", (5, 10)),
        ("5-10 years", (5, 10)),
        ("6 to 9 yrs", (6, 9)),
        ("minimum 5 years", (5, None)),
        ("at least 5 years", (5, None)),
        ("8+ years", (8, None)),
        ("experience: 5-10", (5, 10)),
        ("senior product manager", (None, None)),
    ],
)
def test_parse_experience_range(text, expected):
    assert parse_experience_range(text) == expected


def test_source_experience_conflict_keeps_nearest_to_experience_no_average():
    lo, hi, notes = parse_experience_from_source(
        "Company founded 20-30 years ago. Requirements: experience of 6-9 years in product."
    )
    assert (lo, hi) == (6, 9)
    assert any("conflict" in n for n in notes)


# ----------------------------------------------------------------- experience overlap


@pytest.mark.parametrize(
    "lo,hi,expected",
    [
        (6, 9, "exact"),
        (4, 7, "overlap"),
        (8, 12, "overlap"),
        (2, 4, "exclude"),
        (12, 15, "exclude"),
        (5, None, "overlap"),
        (None, None, "unknown"),
    ],
)
def test_experience_overlap_table(lo, hi, expected):
    assert experience_match_for(lo, hi, intent())[0] == expected


# ----------------------------------------------------------------- role family


@pytest.mark.parametrize(
    "title",
    [
        "Product Manager",
        "Senior Product Manager",
        "Sr. Product Manager",
        "Lead Product Manager",
        "Group Product Manager",
        "Principal Product Manager",
        "Staff Product Manager",
        "Technical Product Manager",
        "Product Owner",
        "Product Manager, Payments",
        "B2B SaaS Product Manager",
        "Sr PM",
        "GPM",
    ],
)
def test_pm_family_included(title):
    assert title_in_family(title, intent())[0], title


@pytest.mark.parametrize(
    "title",
    [
        "Project Manager",
        "Program Manager",
        "Technical Program Manager",
        "Product Marketing Manager",
        "Product Designer",
        "Production Manager",
        "Product Support Engineer",
        "Product Analyst",
        "Category Manager",
        "Brand Manager",
        "Engineering Manager",
        "Software Engineer",
    ],
)
def test_pm_family_excluded(title):
    assert not title_in_family(title, intent())[0], title


# ----------------------------------------------------------------- place and recency


def test_location_uses_job_fields_not_employer_text():
    r = rec(loc="Bengaluru, Karnataka, India", desc="Our headquarters are in Hyderabad.")
    assert location_match_for(r, intent())[0] == "mismatch"


def test_location_locality_alias_and_city():
    assert location_match_for(rec(loc="Gachibowli, Telangana, India", city=None), intent())[0] == "locality_alias"
    assert location_match_for(rec(loc="Secunderabad, Telangana", city=None), intent())[0] == "locality_alias"
    assert location_match_for(rec(), intent())[0] == "city"


def test_hyderabad_sindh_is_not_hyderabad_telangana():
    r = rec(loc="Hyderabad, Sindh, Pakistan", country_code=None, city="Hyderabad")
    assert location_match_for(r, intent())[0] == "mismatch"


def test_relative_posted_labels_use_retrieval_time():
    assert parse_posted_label("3 days ago", NOW) == NOW - timedelta(days=3)
    assert parse_posted_label("1 week ago", NOW) == NOW - timedelta(weeks=1)
    assert parse_posted_label("yesterday", NOW) == NOW - timedelta(days=1)
    assert parse_posted_label("whenever", NOW) is None


def test_recency_boundary_and_stale():
    env = run([rec("a", days_ago=7), rec("b", days_ago=8)])
    assert [j.job_id for j in env.jobs] == ["a"]
    assert env.excluded[0].match_reasons[0] == "stale"


# ----------------------------------------------------------------- filter pipeline


def test_apply_job_filters_split_and_counts():
    records = [
        rec("inc-exact", exp="6-9 years", days_ago=1),
        rec("inc-overlap", title="Lead Product Manager", exp="4-7 years", days_ago=3),
        rec("review", title="Group Product Manager", exp=None, desc="No years stated here."),
        rec("proj", title="Project Manager"),
        rec("pmm", title="Product Marketing Manager"),
        rec("blr", loc="Bengaluru, Karnataka, India"),
        rec("old", days_ago=20),
        rec("junior", title="Associate Product Manager", exp="1-3 years"),
        rec("nocompany", company=None),
    ]
    env = run(records)
    assert [j.job_id for j in env.jobs] == ["inc-exact", "inc-overlap"]
    assert [j.job_id for j in env.needs_review] == ["review"]
    reasons = {j.job_id: j.match_reasons[0] for j in env.excluded}
    assert reasons == {
        "proj": "out_of_family",
        "pmm": "out_of_family",
        "blr": "wrong_city",
        "old": "stale",
        "junior": "experience_no_overlap",
        "nocompany": "missing_company",
    }
    assert env.counts["retrieved"] == 9
    assert env.counts["included"] == 2 and env.counts["needs_review"] == 1 and env.counts["excluded"] == 6
    assert env.counts["excluded_out_of_family"] == 2
    assert {j.experience_match for j in env.jobs} == {"exact", "overlap"}
    assert env.query_echo.posted_after.startswith("2026-11-08")
    assert env.raw_tool_job_ids and "proj" in env.raw_tool_job_ids


def test_unknown_experience_never_in_main_table():
    env = run([rec("review", exp=None, desc="Senior role, no years.")])
    assert env.jobs == [] and len(env.needs_review) == 1
    assert env.needs_review[0].experience_match == "unknown"


def test_experience_parsed_from_description_when_not_structured():
    env = run([rec("d", exp=None, desc="We need 6-9 years of experience in product.")])
    assert env.jobs and env.jobs[0].experience_min == 6 and env.jobs[0].experience_max == 9


def test_remote_not_requested_excluded_unless_in_city():
    remote = rec("rem", loc="Anywhere", city="Anywhere", country_code=None, workplace="remote")
    env = run([remote])
    assert env.excluded and env.excluded[0].match_reasons[0] in {"wrong_city", "remote_not_requested"}


def test_included_sorted_by_date_desc_then_title_and_limited():
    i = intent().model_copy(update={"limit": 2})
    env = apply_job_filters(
        [rec("a", days_ago=3), rec("b", days_ago=1), rec("c", days_ago=2)], i, retrieved_at=NOW
    )
    assert [j.job_id for j in env.jobs] == ["b", "c"]
    assert env.counts["truncated_by_limit"] == 1
    assert any("capped" in n for n in env.coverage_notes)


def test_duplicate_ids_collapsed_and_empty_set_explained():
    env = run([rec("same"), rec("same")])
    assert env.counts["retrieved"] == 1
    empty = run([])
    assert empty.jobs == [] and any("nothing was invented" in n for n in empty.coverage_notes)


# ----------------------------------------------------------------- grounding


def test_ground_envelope_drops_invented_ids_and_urls():
    env = run([rec("real")])
    forged = env.jobs[0].model_copy(update={"job_id": "serpapi:invented", "source_job_id": "invented"})
    tampered = env.model_copy(update={"jobs": [env.jobs[0].model_copy(update={"apply_url": "https://evil.test/x"}), forged]})
    grounded, dropped = ground_job_envelope(tampered)
    assert dropped == ["serpapi:invented"]
    assert [j.job_id for j in grounded.jobs] == ["real"]
    assert grounded.jobs[0].apply_url is None
    assert grounded.counts["included"] == 1


def test_scrub_ungrounded_refs():
    lines = [
        "Strong match: demo-hyd-pm-1",
        "Also see demo-made-up-99",
        "Apply at https://evil.test/job",
        "Link https://example.invalid/jobs/demo-hyd-pm-1",
    ]
    kept = scrub_ungrounded_refs(
        lines, allowed_ids=["demo-hyd-pm-1"], allowed_urls=["https://example.invalid/jobs/demo-hyd-pm-1"]
    )
    assert kept == [lines[0], lines[3]]


# ----------------------------------------------------------------- SerpAPI provider

SERP_PAYLOAD = {
    "jobs_results": [
        {
            "title": "Senior Product Manager",
            "company_name": "Acme Pvt Ltd",
            "location": "Hyderabad, Telangana, India",
            "via": "via LinkedIn",
            "description": "<p>Own the roadmap. 6-9 years of experience required.</p>",
            "job_highlights": [{"title": "Qualifications", "items": ["6-9 years of experience"]}],
            "detected_extensions": {"posted_at": "2 days ago", "schedule_type": "Full-time"},
            "apply_options": [{"title": "Company site", "link": "https://careers.example.test/apply/1"}],
            "job_id": "AbC123==",
        },
        {"title": "No id", "company_name": "X", "location": "Hyderabad"},
        {
            "title": "Product Manager",
            "location": "Anywhere",
            "description": "Remote",
            "detected_extensions": {"work_from_home": True},
            "job_id": "remote1",
        },
    ],
    "serpapi_pagination": {},
}


def serp_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def settings(**kw):
    return Settings(serpapi_api_key=kw.pop("serpapi_api_key", "test-key-123"), **kw)


def test_jobs_search_configured_property():
    assert Settings(serpapi_api_key="k").jobs_search_configured is True
    assert Settings().jobs_search_configured is False


def test_serpapi_params_come_from_intent():
    params = SerpApiJobsProvider(settings()).build_params(intent())
    assert params["engine"] == "google_jobs"
    assert params["q"] == "product manager jobs in Hyderabad"
    assert params["location"] == "Hyderabad, Telangana, India"
    assert params["gl"] == "in"
    assert params["chips"] == "date_posted:week"


def test_serpapi_maps_results_to_job_records():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=SERP_PAYLOAD)

    provider = SerpApiJobsProvider(settings(), serp_client(handler))
    result = provider.search(intent())
    assert captured["url"].startswith(SERPAPI_SEARCH_URL)
    assert "engine=google_jobs" in captured["url"]
    assert len(result.records) == 2  # row without a source id is not a record
    first = result.records[0]
    assert first.source == "serpapi"
    assert first.job_id == "serpapi:AbC123=="
    assert first.source_job_id == "AbC123=="
    assert first.company_name == "Acme Pvt Ltd"
    assert "<p>" not in first.job_description
    assert first.city == "Hyderabad" and first.country_code == "IN"
    assert first.posted_label == "2 days ago" and first.date_posted
    assert first.apply_url == "https://careers.example.test/apply/1"
    assert first.experience_text == "6-9 years"
    remote = result.records[1]
    assert remote.company_name is None and remote.workplace == "remote" and remote.apply_url is None


def test_serpapi_records_flow_through_filters():
    provider = SerpApiJobsProvider(settings(), serp_client(lambda r: httpx.Response(200, json=SERP_PAYLOAD)))
    records = provider.search(intent()).records
    env = apply_job_filters(records, intent(), retrieved_at=NOW, source_name="serpapi")
    # Posted label is relative to *now* in the provider; recompute against NOW for a stable assert.
    assert env.counts["retrieved"] == 2


def test_serpapi_http_error_does_not_leak_key():
    provider = SerpApiJobsProvider(settings(), serp_client(lambda r: httpx.Response(401, json={})))
    with pytest.raises(JobsProviderError) as exc:
        provider.search(intent())
    assert "401" in str(exc.value)
    assert "test-key-123" not in str(exc.value)


def test_serpapi_error_payload_and_empty_results():
    err = SerpApiJobsProvider(settings(), serp_client(lambda r: httpx.Response(200, json={"error": "Invalid API key."})))
    with pytest.raises(JobsProviderError):
        err.search(intent())
    empty = SerpApiJobsProvider(
        settings(),
        serp_client(lambda r: httpx.Response(200, json={"error": "Google hasn't returned any results for this query."})),
    )
    assert empty.search(intent()).records == []


def test_serpapi_not_configured_raises_clearly():
    with pytest.raises(JobsProviderError, match="SERPAPI_API_KEY"):
        SerpApiJobsProvider(Settings()).search(intent())


def test_serpapi_paginates_with_token_up_to_max_pages():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        page = {"jobs_results": [], "serpapi_pagination": {"next_page_token": "TOK"}}
        return httpx.Response(200, json=page)

    SerpApiJobsProvider(settings(), serp_client(handler), max_pages=3).search(intent())
    assert len(calls) == 3 and calls[1]["next_page_token"] == "TOK" and "next_page_token" not in calls[0]


# ----------------------------------------------------------------- demo fixtures


def test_demo_envelope_shows_the_filters_without_network():
    env = JobSearchEnvelope.model_validate(build_demo_job_envelope(retrieved_at=NOW))
    assert env.illustrative is True
    assert 2 <= len(env.jobs) <= 3
    assert len(env.needs_review) >= 1
    assert any(j.title == "Project Manager" for j in env.excluded)
    assert all(j.job_id.startswith("demo-") and j.source == "demo" for j in env.jobs)
    assert all((j.apply_url or "").startswith("https://example.invalid/") for j in build_demo_job_records(NOW))
    assert {"out_of_family", "wrong_city", "stale"} <= {j.match_reasons[0] for j in env.excluded}


# ----------------------------------------------------------------- agents


def spec(mode="live", task_class="job_search"):
    return TaskSpec(
        run_id="r1", original_task=TASK, objective=TASK, created_at="now", execution_mode=mode,
        task_class=task_class,
    )


class FakeJobs:
    source_name = "serpapi"

    def __init__(self, records=None, error=None, configured=True):
        self.records, self.error, self.configured = records or [], error, configured
        self.calls = 0

    def is_configured(self):
        return self.configured

    def search(self, intent):
        self.calls += 1
        if self.error:
            raise JobsProviderError(self.error)
        return JobsFetchResult(records=self.records, retrieved_at=NOW.isoformat())


class ExplodingProvider(DemoProvider):
    def complete_json(self, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("LLM must not be called for research in this test")


def test_live_job_search_without_key_fails_clearly():
    agent = ResearchAgent(ExplodingProvider(), jobs_provider=FakeJobs(configured=False))
    result = agent.run(spec(), {"mode": "live", "job_intent": intent().model_dump()})
    assert result.status == "failed"
    assert "SERPAPI_API_KEY" in result.summary and result.summary == LIVE_JOBS_REQUIRED_MESSAGE
    assert result.artifacts == {}


def test_live_research_builds_envelope_in_code_from_tool_payload():
    jobs = FakeJobs([rec("serpapi:1"), rec("serpapi:2", title="Project Manager")])
    agent = ResearchAgent(ExplodingProvider(), jobs_provider=jobs)
    result = agent.run(spec(), {"mode": "live", "job_intent": intent().model_dump()})
    assert result.status == "completed" and jobs.calls == 1
    env = JobSearchEnvelope.model_validate(result.artifacts["job_envelope"])
    assert [j.job_id for j in env.jobs] == ["serpapi:1"]
    assert env.excluded[0].job_id == "serpapi:2"
    assert env.illustrative is False and env.query_echo.source_name == "serpapi"
    assert result.output["evidence_items"] == []  # jobs are records, not evidence


def test_live_source_failure_is_empty_contribution_not_fabrication():
    agent = ResearchAgent(ExplodingProvider(), jobs_provider=FakeJobs(error="SerpAPI request failed (HTTP 500)."))
    result = agent.run(spec(), {"mode": "live", "job_intent": intent().model_dump()})
    env = JobSearchEnvelope.model_validate(result.artifacts["job_envelope"])
    assert result.status == "completed"
    assert env.jobs == [] and env.sources_failed == ["SerpAPI request failed (HTTP 500)."]


def test_demo_research_never_touches_jobs_provider_or_llm():
    jobs = FakeJobs([rec("never")])
    agent = ResearchAgent(ExplodingProvider(), jobs_provider=jobs)
    result = agent.run(spec("demo"), {"mode": "demo", "job_intent": intent().model_dump()})
    assert jobs.calls == 0
    env = JobSearchEnvelope.model_validate(result.artifacts["job_envelope"])
    assert env.illustrative and env.query_echo.source_name == "demo"
    assert any("Demo Mode" in x for x in result.output["research_limitations"])


class InventingExecutionProvider(DemoProvider):
    """Execution output that tries to smuggle in a made-up job id and URL."""

    def complete_json(self, *, system_prompt, user_prompt, schema_name, temperature=None):
        data = super().complete_json(
            system_prompt=system_prompt, user_prompt=user_prompt, schema_name=schema_name, temperature=temperature
        )
        if schema_name == "deliverable":
            data["recommendations"] = list(data["recommendations"]) + [
                "Also consider demo-invented-77 at https://evil.test/apply"
            ]
            data["executive_summary"] = "Great news: demo-invented-77 is a perfect fit."
            data["markdown_content"] = "| demo-invented-77 | Fake |"
        return data


def test_execution_drops_invented_refs_and_renders_markdown_from_envelope():
    env = build_demo_job_envelope(retrieved_at=NOW)
    agent = ExecutionAgent(InventingExecutionProvider())
    result = agent.run(spec("demo"), {"mode": "demo", "job_envelope": env})
    out = result.output
    assert result.status == "completed"
    assert "demo-invented-77" not in json.dumps(out)
    assert "evil.test" not in json.dumps(out)
    assert "demo-hyd-pm-1" in out["markdown_content"]
    assert out["evidence_references"] == [j["job_id"] for j in env["jobs"]]
    assert result.artifacts["job_envelope"]["counts"]["included"] == len(env["jobs"])


def test_execution_without_envelope_fails():
    result = ExecutionAgent(DemoProvider()).run(spec("demo"), {"mode": "demo"})
    assert result.status == "failed"


# ----------------------------------------------------------------- reviewer checks


def checks(env, deliverable=None, task=TASK):
    return check_job_search(env.model_dump(mode="json"), intent(task).model_dump(mode="json"), deliverable)


def test_review_passes_clean_envelope():
    assert checks(run([rec("a"), rec("b", title="Project Manager")])) == []


def test_review_identity_and_grounding_and_role_and_place():
    env = run([rec("a")])
    bad = env.jobs[0].model_copy(
        update={
            "job_id": "ghost",
            "company_name": "",
            "title": "Project Manager",
            "location_match": "mismatch",
            "apply_url": "https://evil.test",
        }
    )
    issues = "\n".join(checks(env.model_copy(update={"jobs": [bad]})))
    for needle in ("Identity", "Grounding: job id", "Grounding: apply URL", "Role", "Place"):
        assert needle in issues, needle


def test_review_recency_and_experience_and_completeness():
    env = run([rec("a")])
    stale = env.jobs[0].model_copy(update={"date_posted": (NOW - timedelta(days=30)).isoformat(), "experience_match": "unknown"})
    nodate = env.jobs[0].model_copy(update={"date_posted": None})
    issues = "\n".join(checks(env.model_copy(update={"jobs": [stale, nodate]})))
    assert "Recency" in issues and "Experience" in issues
    miscounted = env.model_copy(update={"counts": {**env.counts, "included": 5}})
    assert any("Completeness" in i for i in checks(miscounted))


def test_review_flags_safety_claims_and_invented_text():
    env = run([rec("a")])
    md = "| a |"
    deliverable = {"markdown_content": md, "executive_summary": "I have already applied to the top three roles."}
    assert any("Safety" in i for i in checks(env, deliverable))
    ghost = {"markdown_content": "| a |", "executive_summary": "See demo-ghost-1 for details."}
    assert any("not returned" in i or "never returned" in i for i in checks(env, ghost))


def test_review_empty_set_with_explanations_passes_but_dropped_rows_fail():
    env = run([rec("old", days_ago=40)])
    assert checks(env) == []
    hidden = env.model_copy(update={"excluded": [], "counts": {**env.counts, "excluded": 0}})
    assert any("Completeness" in i for i in checks(hidden))


def test_reviewer_agent_forces_revision_when_code_checks_fail():
    env = run([rec("a")])
    bad = env.jobs[0].model_copy(update={"title": "Project Manager"})
    context = {
        "job_envelope": env.model_copy(update={"jobs": [bad]}).model_dump(mode="json"),
        "job_intent": intent().model_dump(mode="json"),
        "deliverable": {"markdown_content": "a"},
    }
    result = ReviewerAgent(DemoProvider()).run(spec("demo"), context)
    assert result.status == "needs_revision"
    assert any("Role" in i for i in result.output["issues"])


# ----------------------------------------------------------------- orchestration / service / export


def test_demo_graph_job_search_end_to_end():
    state = WorkforceRunner(DemoProvider(), max_revisions=1).run(task=TASK, mode="demo")
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    assert state["task_specification"]["task_class"] == "job_search"
    assert state["job_intent"]["location"]["city"] == "Hyderabad"
    env = JobSearchEnvelope.model_validate(state["job_envelope"])
    assert env.illustrative and env.jobs
    assert state["review"]["status"] == "approved"
    assert state["approval_status"] is None
    assert "demo-hyd-pm-1" in state["deliverable"]["markdown_content"]
    assert all(a["owner"] == "user" for a in state["plan"]["actions"])
    assert not any("applied" in a["description"].lower() and "not" not in a["description"].lower() for a in state["plan"]["actions"])
    assert state.get("comparison_envelope") is None


def test_live_graph_job_search_with_fake_source():
    jobs = FakeJobs([rec("serpapi:1"), rec("serpapi:2", title="Project Manager")])
    state = WorkforceRunner(DemoProvider(), jobs_provider=jobs, max_revisions=1).run(task=TASK, mode="live")
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    env = JobSearchEnvelope.model_validate(state["job_envelope"])
    assert [j.job_id for j in env.jobs] == ["serpapi:1"] and not env.illustrative


def test_live_graph_job_search_fails_clearly_without_key():
    state = WorkforceRunner(DemoProvider(), jobs_provider=FakeJobs(configured=False), max_revisions=1).run(
        task=TASK, mode="live"
    )
    assert state["status"] == "FAILED"
    assert "SERPAPI_API_KEY" in state["error"]
    assert not state.get("job_envelope")


def test_user_confirmed_intent_is_used():
    i = intent().model_copy(update={"limit": 1})
    state = WorkforceRunner(DemoProvider(), max_revisions=1).run(
        task=TASK, mode="demo", job_intent=i.model_dump(mode="json")
    )
    assert len(state["job_envelope"]["jobs"]) == 1
    assert state["job_envelope"]["counts"]["truncated_by_limit"] >= 1


def test_run_service_blocks_live_job_search_without_serpapi_key():
    service = RunService()
    service.settings = Settings(openai_api_key="sk-test-not-real-0000000000")
    with pytest.raises(RuntimeError, match="SERPAPI_API_KEY"):
        service.begin_run(task=TASK, mode="live")
    # Briefing in live mode is not blocked by the missing jobs key.
    service._ensure_live_ready("live", task="Plan my next productive week.")


def test_briefing_path_unchanged():
    state = WorkforceRunner(DemoProvider(), max_revisions=1).run(task="Plan my next productive week.", mode="demo")
    assert state["task_specification"]["task_class"] == "briefing"
    assert state.get("job_envelope") is None and state.get("comparison_envelope") is None
    assert state["revision_count"] == 1


def test_csv_export_of_included_jobs_and_bundle():
    state = WorkforceRunner(DemoProvider(), max_revisions=1).run(task=TASK, mode="demo")
    exporter = ExportService()
    name, csv_text = exporter.jobs_csv(state)
    rows = csv_text.strip().splitlines()
    assert name.endswith(".csv")
    assert rows[0] == "job_id,title,company,city,date_posted,experience,apply_url"
    assert len(rows) == 1 + len(state["job_envelope"]["jobs"])
    assert "demo-hyd-prj-5" not in csv_text  # excluded rows are not exported
    bundle = json.loads(exporter.json_bundle(state)[1])
    assert bundle["job_envelope"]["counts"]["included"] == len(state["job_envelope"]["jobs"])
    assert bundle["job_intent"]["role_family"] == "product_management"
    _, blob = exporter.zip_bundle(state)
    names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
    assert "job_envelope.json" in names and any(n.startswith("jobs_") and n.endswith(".csv") for n in names)


def test_word_export_includes_job_envelope_details():
    from docx import Document

    state = WorkforceRunner(DemoProvider(), max_revisions=1).run(task=TASK, mode="demo")
    env = state["job_envelope"]
    assert env["jobs"], "demo fixture should include at least one job"
    name, blob = ExportService().research_docx(state)
    assert name.startswith("jobs_") and name.endswith(".docx")
    doc = Document(io.BytesIO(blob))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Executive Summary" in text
    assert "Objective" in text
    assert "Key Findings" in text
    assert "Action Plan" in text
    assert "Deliverable" in text
    assert "Activity log" in text
    assert "Job search results" in text
    assert "Included jobs" in text
    first = env["jobs"][0]
    assert first["company_name"] in text
    assert first["title"] in text
    assert first["job_id"] in text
    deliverable = state.get("deliverable") or {}
    if deliverable.get("title"):
        assert deliverable["title"] in text or "Deliverable" in text
    if deliverable.get("executive_summary"):
        assert deliverable["executive_summary"][:40] in text


def test_word_export_briefing_includes_deliverable_and_plan():
    from docx import Document

    state = WorkforceRunner(DemoProvider(), max_revisions=1).run(
        task="Plan my next productive week.", mode="demo"
    )
    assert state.get("job_envelope") is None
    deliverable = state.get("deliverable") or {}
    plan = state.get("plan") or {}
    assert deliverable, "briefing demo should produce a deliverable"
    name, blob = ExportService().research_docx(state)
    assert name.startswith("prd_") and name.endswith(".docx")
    text = "\n".join(p.text for p in Document(io.BytesIO(blob)).paragraphs)
    assert "Executive Summary" in text
    assert "Recommendations" in text
    assert "Action Plan" in text
    assert "Deliverable" in text
    assert "Activity log" in text
    if deliverable.get("executive_summary"):
        assert deliverable["executive_summary"][:50] in text
    if deliverable.get("title"):
        assert deliverable["title"] in text
    actions = plan.get("actions") or []
    if actions:
        assert actions[0].get("title") in text


def test_truncated_description_is_labelled_not_completed():
    payload = {
        "jobs_results": [
            {
                "title": "Product Manager",
                "company_name": "Acme",
                "location": "Hyderabad, Telangana, India",
                "description": "Own the roadmap and partner with engineering to ship…",
                "detected_extensions": {"posted_at": "1 day ago"},
                "job_id": "trunc1",
            }
        ]
    }
    provider = SerpApiJobsProvider(settings(), serp_client(lambda r: httpx.Response(200, json=payload)))
    record = provider.search(intent()).records[0]
    assert record.description_completeness == "truncated"
    assert record.job_description.endswith("ship…")  # source text kept verbatim, never extended
