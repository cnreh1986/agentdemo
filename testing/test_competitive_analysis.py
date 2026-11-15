"""Unit tests for the competitive_analysis task class (newehancement.md sections 17-26)."""

from __future__ import annotations

import csv
import io
import json

import pytest

from src.agents.reviewer_agent import ReviewerAgent
from src.agents.research_agent import ResearchAgent
from src.config.samples import (
    SAMPLE_COMPARE_RICH_LABEL,
    SAMPLE_COMPARE_THIN_LABEL,
    SAMPLE_TASKS,
)
from src.demo.fixtures import build_demo_comparison_envelope
from src.models.competitive_analysis import ComparisonEnvelope
from src.models.task import TaskSpec
from src.orchestration.runner import WorkforceRunner
from src.providers.demo_provider import DemoProvider
from src.providers.search_base import SearchResult
from src.services.comparison_intent import (
    DOMAIN_FRAME_BANNER,
    HIRING_CRITERIA,
    ROLE_CATALOG,
    build_comparison_envelope,
    build_demo_matrix,
    build_domain_frame,
    canonical_subject,
    cell_id,
    comparison_needs_context,
    format_context_echo,
    parse_competitive_analysis_intent,
    rebuild_comparison_intent,
    split_comparison_subjects,
)
from src.services.export_service import ExportService
from src.services.job_intent import classify_task_class
from src.services.task_class_render import comparison_csv, render_comparison_markdown
from src.services.task_class_review import check_comparison

RICH = SAMPLE_TASKS[SAMPLE_COMPARE_RICH_LABEL]
THIN = SAMPLE_TASKS[SAMPLE_COMPARE_THIN_LABEL]


def rich_intent():
    return parse_competitive_analysis_intent(RICH["task"], RICH["background"], RICH["constraints"], RICH["time_horizon"])


def thin_intent():
    return parse_competitive_analysis_intent(THIN["task"], THIN["background"], THIN["constraints"], THIN["time_horizon"])


# ----------------------------------------------------------------- subjects


@pytest.mark.parametrize(
    "task,expected",
    [
        ("Compare product manager and product marketer for our next hire.", ["product manager", "product marketer"]),
        ("Compare a product manager and a product marketer. I will provide the context.", ["product manager", "product marketer"]),
        ("PM vs PMM for my situation", ["PM", "PMM"]),
        ("Compare RazorpayX and Cashfree for our payouts page.", ["RazorpayX", "Cashfree"]),
        ("What is the difference between a product manager and a product marketing manager?", ["product manager", "product marketing manager"]),
        ("Plan my next productive week.", []),
    ],
)
def test_split_subjects(task, expected):
    assert split_comparison_subjects(task) == expected


def test_canonical_subjects_map_synonyms_and_flag_lookalikes():
    assert canonical_subject("PM")[0].subject_id == "pm"
    assert canonical_subject("Product Management")[0].subject_id == "pm"
    for alias in ("product marketer", "Product Marketing Manager", "PMM"):
        s, confirm = canonical_subject(alias)
        assert (s.subject_id, s.label, confirm) == ("pmm", "Product Marketer", False)
    s, confirm = canonical_subject("Project Manager")
    assert s.subject_id == "project_manager" and confirm is True


def test_project_manager_is_not_silently_accepted_as_pm():
    i = parse_competitive_analysis_intent("Compare project manager and product marketer for our next hire.", "We are 10 people.")
    assert [s.subject_id for s in i.subjects] == ["project_manager", "pmm"]
    assert any("Project and program managers" in q for q in i.unblock_questions)


# ----------------------------------------------------------------- intent


def test_rich_context_intent_matches_section_19():
    i = rich_intent()
    assert i.task_class == "competitive_analysis" and i.comparison_kind == "role"
    assert [(s.subject_id, s.label) for s in i.subjects] == [("pm", "Product Manager"), ("pmm", "Product Marketer")]
    assert i.status == "ready" and i.unblock_questions == []
    d = i.decision
    assert d.question == "Which single role should we hire next quarter, and what does the current team keep owning?"
    assert d.audience == "founder"
    assert d.time_horizon == "Next quarter"
    assert any("headcount" in c.lower() for c in d.constraints)
    assert any("candidate" in c.lower() for c in d.constraints)
    assert any("advertisement" in c.lower() for c in d.constraints)
    c = i.user_context
    assert c.company_stage == "about 80 people"
    assert c.business_model == "B2B SaaS"
    assert c.location == "Hyderabad, India"
    assert c.product == "accounts-payable software"
    assert c.customer == "mid-market finance teams in India"
    assert c.go_to_market == "founder-led sales"
    assert c.current_team == "one technical product manager, no product marketer"
    assert c.current_ownership == [
        "release notes: existing product manager",
        "first sales call: existing product manager",
    ]
    assert "release notes" in i.subjects[0].user_notes
    assert "no product marketer" in i.subjects[1].user_notes.lower()


def test_thin_context_needs_context_with_unblock_questions():
    i = thin_intent()
    assert i.status == "needs_context" and comparison_needs_context(i)
    assert [s.subject_id for s in i.subjects] == ["pm", "pmm"]
    assert len(i.unblock_questions) == 4
    assert any("decision" in q.lower() for q in i.unblock_questions)
    assert any("sell" in q.lower() for q in i.unblock_questions)


def test_decision_without_context_is_still_thin():
    i = parse_competitive_analysis_intent("Compare product manager and product marketer for our next hire.")
    assert i.decision.question and i.status == "needs_context"


def test_context_without_decision_is_thin():
    i = parse_competitive_analysis_intent(
        "Compare product manager and product marketer.", "We are a 50-person B2B SaaS company in Pune."
    )
    assert i.decision.question == "" and i.status == "needs_context"
    assert i.user_context.company_stage == "about 50 people"


def test_single_subject_needs_context():
    i = parse_competitive_analysis_intent("Compare product manager for our next hire", "We are 10 people.")
    assert i.status == "needs_context"


def test_rebuild_after_user_corrections_clears_needs_context():
    base = parse_competitive_analysis_intent(
        "Compare product manager and product marketer.", "We are a 50-person B2B SaaS company in Pune."
    )
    fixed = rebuild_comparison_intent(
        base,
        subject_labels=["Product Manager", "Product Marketer"],
        decision_question="Which role should we hire next quarter?",
        audience="founder",
    )
    assert fixed.status == "ready" and fixed.decision.audience == "founder"


def test_classification_comparison_vs_job_search():
    assert classify_task_class(RICH["task"], RICH["background"], RICH["constraints"]) == "competitive_analysis"
    assert classify_task_class("Find product manager jobs in Hyderabad, 5-10 years, last 7 days") == "job_search"


def test_context_echo_lines():
    lines = format_context_echo(rich_intent())
    joined = "\n".join(lines)
    assert "About 80 people" in joined and "Founder-led sales" in joined
    assert "release notes: existing product manager" in joined


# ----------------------------------------------------------------- matrix


def cell(env, subject, criterion):
    return next(c for c in env.matrix if c.subject_id == subject and c.criterion_id == criterion)


def test_demo_matrix_has_one_cell_per_criterion_per_subject():
    matrix, not_used = build_demo_matrix(rich_intent())
    subjects = {"pm", "pmm"}
    criteria = {c.criterion_id for c in matrix}
    assert criteria == {"current_ownership", *HIRING_CRITERIA}
    for crit in criteria:
        assert {c.subject_id for c in matrix if c.criterion_id == crit} == subjects
    assert len(matrix) == len(criteria) * 2
    assert set(not_used) == {"Problem ownership", "Discovery", "Artifacts", "Horizon"}


def test_user_context_outranks_domain_default():
    env = build_comparison_envelope(rich_intent(), illustrative=True)
    pm = cell(env, "pm", "current_ownership")
    pmm = cell(env, "pmm", "current_ownership")
    assert pm.basis == "user_supplied" and "release notes" in pm.value and "first sales call" in pm.value
    assert pm.evidence and all(e.basis == "user_supplied" and e.source_title == "User context" for e in pm.evidence)
    assert pmm.basis == "user_supplied" and "No Product Marketer" in pmm.value
    positioning = cell(env, "pmm", "positioning")
    assert positioning.basis == "domain_default" and "positioning" in positioning.value.lower()
    assert positioning.evidence[0].source_title.startswith("Role catalog")


def test_unknown_cells_stay_empty_and_are_listed():
    env = build_comparison_envelope(rich_intent())
    for sid in ("pm", "pmm"):
        c = cell(env, sid, "pricing")
        assert c.basis == "unknown" and c.value == "" and c.evidence == []
    assert any("Pricing" in u for u in env.extra["unknowns"])
    # A usual-pattern note may exist, but only outside the company-current cells and labelled.
    assert all("not a fact about this company" in n["note"] for n in env.extra["domain_notes"])


def test_every_non_empty_cell_has_a_basis_and_no_numeric_scores():
    env = build_comparison_envelope(rich_intent())
    for c in env.matrix:
        assert c.basis in {"user_supplied", "domain_default", "unknown", "public_source", "inference"}
        assert (c.value == "") == (c.basis == "unknown")
        assert c.score is None


def test_options_address_the_decision_without_naming_candidates_or_ads():
    env = build_comparison_envelope(rich_intent())
    assert {o.option_id for o in env.options} == {"hire_pmm", "hire_pm", "defer"}
    deps = env.extra["option_cell_dependencies"]
    ids = {cell_id(c) for c in env.matrix}
    assert all(set(v) <= ids for v in deps.values())
    text = json.dumps([o.model_dump() for o in env.options]).lower()
    assert "job advertisement" not in text and "we are hiring" not in text
    assert "release notes need an explicit handoff" in text


def test_thin_context_returns_labelled_domain_frame_and_empty_matrix():
    env = build_comparison_envelope(thin_intent())
    assert env.status == "needs_context"
    assert env.matrix == [] and env.options == []
    assert env.domain_frame_banner == DOMAIN_FRAME_BANNER
    assert len(env.open_questions) == 4
    frame = env.extra["domain_frame"]
    assert len(frame) == len(ROLE_CATALOG) * 2
    assert {c["basis"] for c in frame} == {"domain_default"}
    # Nothing about a specific company may be invented.
    blob = json.dumps(env.model_dump(mode="json")).lower()
    for invented in ("80 people", "hyderabad", "accounts-payable", "founder-led"):
        assert invented not in blob


def test_domain_frame_empty_for_non_catalog_subjects():
    i = parse_competitive_analysis_intent("Compare RazorpayX and Cashfree for our payouts page.")
    assert build_domain_frame(i) == []
    assert i.comparison_kind == "product" and i.status == "needs_context"
    assert any("criteria" in q.lower() for q in i.unblock_questions)


def test_product_comparison_uses_user_listed_criteria_with_unknown_cells():
    i = parse_competitive_analysis_intent(
        "Compare RazorpayX and Cashfree for our payouts page.",
        "We sell to the same mid-market finance buyer. The decision is what to say on our pricing page this quarter. "
        "Here are the three criteria I care about: settlement time, who the buyer is, and what they charge for vendor payouts.",
    )
    assert i.comparison_kind == "product" and i.status == "ready"
    env = build_comparison_envelope(i)
    assert {c.criterion_label for c in env.matrix} == {
        "settlement time", "who the buyer is", "what they charge for vendor payouts",
    }
    assert all(c.basis == "unknown" and c.value == "" for c in env.matrix)
    assert not any(c.criterion_id in {r["id"] for r in ROLE_CATALOG} for c in env.matrix)


def test_demo_fixture_defaults_to_rich_sample_and_is_illustrative():
    env = ComparisonEnvelope.model_validate(build_demo_comparison_envelope())
    assert env.illustrative and env.status == "ready"
    assert cell(env, "pm", "current_ownership").basis == "user_supplied"


# ----------------------------------------------------------------- render / csv


def test_markdown_and_csv_render_from_envelope():
    env = build_comparison_envelope(rich_intent(), illustrative=True)
    md = render_comparison_markdown(env, title="Comparison", executive_summary="Summary.")
    assert "Illustrative example" in md and "[user_supplied]" in md and "[domain_default]" in md
    assert "— (unknown)" in md and "Options for the decision" in md
    rows = list(csv.reader(io.StringIO(comparison_csv(env))))
    assert rows[0] == ["criterion", "subject", "finding", "basis", "confidence"]
    assert len(rows) == 1 + len(env.matrix)
    by = {(r[0], r[1]): r for r in rows[1:]}
    assert by[("Current ownership at this company", "Product Manager")][4] == "high"
    assert by[("Positioning", "Product Marketer")][4] == "medium"
    assert by[("Pricing owner at this company", "Product Manager")][3] == "unknown"


def test_needs_context_markdown_labels_frame_as_generic():
    md = render_comparison_markdown(build_comparison_envelope(thin_intent()))
    assert "needs context" in md and "not an analysis of your company" in md
    assert "domain default" in md and "Questions that unblock" in md


# ----------------------------------------------------------------- reviewer checks


def checks(env, deliverable=None, intent=None):
    return check_comparison(env.model_dump(mode="json"), (intent or env.intent_echo).model_dump(mode="json"), deliverable)


def test_review_passes_rich_and_thin_envelopes():
    assert checks(build_comparison_envelope(rich_intent())) == []
    assert checks(build_comparison_envelope(thin_intent())) == []


def test_review_subjects_and_coverage():
    env = build_comparison_envelope(rich_intent())
    missing = env.model_copy(update={"matrix": [c for c in env.matrix if c.subject_id != "pmm"]})
    assert any("Subjects" in i for i in checks(missing))
    extra_col = env.model_copy(update={"matrix": env.matrix + [env.matrix[0].model_copy(update={"subject_id": "designer"})]})
    assert any("extra column" in i for i in checks(extra_col))
    gap = env.model_copy(update={"matrix": [c for c in env.matrix if cell_id(c) != "pmm:metrics"]})
    assert any("Coverage" in i for i in checks(gap))


def test_review_basis_blanks_and_precedence():
    env = build_comparison_envelope(rich_intent())
    filled_unknown = [c.model_copy(update={"value": "Maybe PM"}) if cell_id(c) == "pm:pricing" else c for c in env.matrix]
    assert any("basis 'unknown'" in i for i in checks(env.model_copy(update={"matrix": filled_unknown})))
    unquoted = [c.model_copy(update={"evidence": []}) if cell_id(c) == "pm:current_ownership" else c for c in env.matrix]
    assert any("user_supplied cell" in i for i in checks(env.model_copy(update={"matrix": unquoted})))
    overwritten = [
        c.model_copy(update={"basis": "domain_default", "value": "Product managers own the roadmap."})
        if cell_id(c) == "pm:current_ownership" else c
        for c in env.matrix
    ]
    assert any("Precedence" in i for i in checks(env.model_copy(update={"matrix": overwritten})))
    no_url = [c.model_copy(update={"basis": "public_source"}) if cell_id(c) == "pm:positioning" else c for c in env.matrix]
    assert any("public_source" in i for i in checks(env.model_copy(update={"matrix": no_url})))


def test_review_ready_with_empty_matrix_or_no_options_fails():
    env = build_comparison_envelope(rich_intent())
    assert any("matrix is empty" in i for i in checks(env.model_copy(update={"matrix": []})))
    assert any("no option" in i.lower() for i in checks(env.model_copy(update={"options": []})))


def test_review_needs_context_rules():
    env = build_comparison_envelope(thin_intent())
    assert any("empty" in i for i in checks(env.model_copy(update={"matrix": build_comparison_envelope(rich_intent()).matrix[:2]})))
    assert any("questions" in i for i in checks(env.model_copy(update={"open_questions": []})))
    assert any("generic" in i for i in checks(env.model_copy(update={"domain_frame_banner": None})))


def test_review_safety_job_ad_and_opened_role():
    env = build_comparison_envelope(rich_intent())
    assert any("Safety" in i for i in checks(env, {"markdown_content": "The requisition has been opened for the PM role."}))
    assert any("job advertisement" in i for i in checks(env, {"markdown_content": "Requirements: 5 years. We are hiring a Product Manager. Apply now."}))


def test_reviewer_agent_forces_revision_on_failed_checks():
    env = build_comparison_envelope(rich_intent())
    broken = env.model_copy(update={"matrix": []})
    context = {
        "comparison_envelope": broken.model_dump(mode="json"),
        "comparison_intent": rich_intent().model_dump(mode="json"),
        "deliverable": {"markdown_content": "An essay about roles."},
    }
    spec = TaskSpec(run_id="r", original_task="t", objective="t", created_at="now", execution_mode="demo", task_class="competitive_analysis")
    result = ReviewerAgent(DemoProvider()).run(spec, context)
    assert result.status == "needs_revision"
    assert any("Coverage" in i for i in result.output["issues"])


# ----------------------------------------------------------------- research agent


class FakeSearch:
    def __init__(self, fail=False):
        self.queries, self.fail = [], fail

    def is_configured(self):
        return True

    def search(self, query, max_results=5):
        self.queries.append(query)
        if self.fail:
            raise RuntimeError("search down")
        return [SearchResult("PMM role", f"https://example.test/{len(self.queries)}", "example.test", "Product marketers own positioning and launch.", "now")]


class ExplodingProvider(DemoProvider):
    def complete_json(self, **kwargs):  # pragma: no cover
        raise AssertionError("LLM must not run for comparison research")


def spec(mode):
    return TaskSpec(run_id="r", original_task=RICH["task"], objective=RICH["task"], created_at="now", execution_mode=mode, task_class="competitive_analysis")


def test_live_research_without_search_labels_defaults_and_keeps_user_cells():
    agent = ResearchAgent(ExplodingProvider())
    result = agent.run(spec("live"), {"mode": "live", "comparison_intent": rich_intent().model_dump(mode="json")})
    env = ComparisonEnvelope.model_validate(result.artifacts["comparison_envelope"])
    assert result.status == "completed" and not env.illustrative
    assert cell(env, "pm", "current_ownership").basis == "user_supplied"
    assert any("not retrieved" in x for x in env.extra["limitations"])
    assert all(e["evidence_type"] == "user_supplied" for e in result.output["evidence_items"])


def test_live_research_attaches_only_tool_urls_per_criterion():
    search = FakeSearch()
    agent = ResearchAgent(ExplodingProvider(), search_provider=search)
    result = agent.run(spec("live"), {"mode": "live", "comparison_intent": rich_intent().model_dump(mode="json")})
    assert 1 <= len(search.queries) <= 4  # short per-criterion queries, not the company paragraph
    assert all("80-person" not in q for q in search.queries)
    env = ComparisonEnvelope.model_validate(result.artifacts["comparison_envelope"])
    urls = {e.source_url for c in env.matrix for e in c.evidence if e.source_url}
    assert urls and all(u.startswith("https://example.test/") for u in urls)
    assert cell(env, "pm", "current_ownership").basis == "user_supplied"
    assert checks(env) == []


def test_live_research_search_failure_keeps_user_cells():
    agent = ResearchAgent(ExplodingProvider(), search_provider=FakeSearch(fail=True))
    result = agent.run(spec("live"), {"mode": "live", "comparison_intent": rich_intent().model_dump(mode="json")})
    env = ComparisonEnvelope.model_validate(result.artifacts["comparison_envelope"])
    assert result.status == "completed"
    assert cell(env, "pm", "current_ownership").basis == "user_supplied"
    assert any("failed" in x.lower() for x in env.extra["limitations"])


def test_demo_research_makes_no_search_calls():
    search = FakeSearch()
    agent = ResearchAgent(ExplodingProvider(), search_provider=search)
    result = agent.run(spec("demo"), {"mode": "demo", "comparison_intent": rich_intent().model_dump(mode="json")})
    assert search.queries == []
    assert ComparisonEnvelope.model_validate(result.artifacts["comparison_envelope"]).illustrative
    assert any("Demo Mode" in x for x in result.output["research_limitations"])


# ----------------------------------------------------------------- orchestration / export


def test_demo_graph_rich_comparison_end_to_end():
    state = WorkforceRunner(DemoProvider(), max_revisions=1).run(mode="demo", **RICH)
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    assert state["task_specification"]["task_class"] == "competitive_analysis"
    assert state["comparison_intent"]["decision"]["audience"] == "founder"
    env = ComparisonEnvelope.model_validate(state["comparison_envelope"])
    assert env.status == "ready" and env.illustrative
    assert state["review"]["status"] == "approved" and state["approval_status"] is None
    assert "[user_supplied]" in state["deliverable"]["markdown_content"]
    assert state.get("job_envelope") is None
    crit = " ".join(state["task_specification"]["success_criteria"])
    assert "Product Manager and Product Marketer" in crit and "no candidate names" in crit


def test_demo_graph_thin_comparison_waits_for_context_and_passes_review():
    state = WorkforceRunner(DemoProvider(), max_revisions=1).run(mode="demo", **THIN)
    env = ComparisonEnvelope.model_validate(state["comparison_envelope"])
    assert env.status == "needs_context" and env.matrix == []
    assert state["review"]["status"] == "approved"
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    assert "needs context" in state["deliverable"]["markdown_content"]
    assert all(a["owner"] == "user" for a in state["plan"]["actions"])


def test_user_confirmed_comparison_intent_is_used():
    corrected = rebuild_comparison_intent(thin_intent(), decision_question="Which role first?").model_dump(mode="json")
    state = WorkforceRunner(DemoProvider(), max_revisions=1).run(mode="demo", comparison_intent=corrected, **THIN)
    assert state["comparison_intent"]["decision"]["question"] == "Which role first?"


def test_comparison_csv_and_bundle_export():
    state = WorkforceRunner(DemoProvider(), max_revisions=1).run(mode="demo", **RICH)
    exporter = ExportService()
    name, text = exporter.comparison_csv(state)
    assert name.startswith("comparison_") and text.splitlines()[0] == "criterion,subject,finding,basis,confidence"
    bundle = json.loads(exporter.json_bundle(state)[1])
    assert bundle["comparison_envelope"]["status"] == "ready"
    assert bundle["comparison_intent"]["subjects"][0]["subject_id"] == "pm"
