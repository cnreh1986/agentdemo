"""Deterministic Demo Mode packets. Field names match PRD schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_task_spec(
    *,
    run_id: str,
    task: str,
    background: str = "",
    constraints: str = "",
    time_horizon: str = "",
    output_format: str = "Briefing",
    execution_mode: str = "demo",
    model_configuration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    objective = task if len(task) <= 120 else task[:117] + "..."
    return {
        "run_id": run_id,
        "original_task": task,
        "objective": objective,
        "background": background,
        "constraints": constraints,
        "time_horizon": time_horizon or "Not specified",
        "requested_output": output_format,
        "success_criteria": [
            "Addresses the stated objective",
            "Produces a readable deliverable in the requested format",
            "Separates evidence, recommendations, and assumptions",
            "Leaves final approval to the human",
        ],
        "created_at": _now(),
        "execution_mode": execution_mode,
        "model_configuration": model_configuration
        or {"provider": "demo", "model": "fixtures", "live": False},
    }


def build_research_packet(run_id: str, task: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "research_question": f"What evidence and themes support: {task}",
        "key_findings": [
            "Specialised agent roles improve clarity of ownership compared with a single chatbot.",
            "Human approval gates reduce unintended external actions in workshop settings.",
            "Time-boxed plans with explicit constraints are more actionable for busy professionals.",
        ],
        "evidence_items": [],
        "assumptions": [
            "The user can act on recommendations within the stated time horizon.",
            "No confidential enterprise data is required for this illustrative run.",
        ],
        "uncertainties": [
            "Live market data was not retrieved in Demo Mode.",
            "Individual capacity and calendar conflicts are unknown.",
        ],
        "risks": [
            "Overcommitting the plan without protecting focus blocks.",
            "Treating illustrative findings as verified research.",
        ],
        "open_questions": [
            "Which constraint is non-negotiable if time runs short?",
            "What does 'done' look like for the primary objective?",
        ],
        "research_limitations": [
            "Demo Mode: illustrative output only. No live web research was performed.",
            "Findings are model-knowledge synthesis fixtures and are not live-verified.",
            "No source URLs are cited because no search tool ran.",
        ],
        "status": "completed",
        "agent_summary": "Organised themes, assumptions, and gaps without fabricating citations.",
    }


def build_plan(task: str) -> dict[str, Any]:
    return {
        "objective": task,
        "strategic_rationale": (
            "Sequence discovery, prioritisation, and delivery so the user keeps control "
            "while agents produce inspectable intermediate packets."
        ),
        "priorities": [
            "Clarify the objective and constraints",
            "Protect high-impact focus time",
            "Ship a reviewable briefing and action list",
        ],
        "actions": [
            {
                "action_id": "a1",
                "title": "Frame the week or initiative",
                "description": "Write a one-paragraph objective and list hard constraints.",
                "priority": "high",
                "estimated_effort": "45 minutes (estimate)",
                "suggested_timing": "Day 1 morning",
                "dependency_ids": [],
                "expected_outcome": "Shared definition of done",
                "evidence_refs": [],
                "owner": "user",
            },
            {
                "action_id": "a2",
                "title": "Block deep-work sessions",
                "description": "Reserve two 90-minute focus blocks on the three highest-impact days.",
                "priority": "high",
                "estimated_effort": "30 minutes (estimate)",
                "suggested_timing": "Day 1 afternoon",
                "dependency_ids": ["a1"],
                "expected_outcome": "Calendar reflects priorities",
                "evidence_refs": [],
                "owner": "user",
            },
            {
                "action_id": "a3",
                "title": "Produce the briefing draft",
                "description": "Assemble findings, recommendations, and open questions into the requested format.",
                "priority": "medium",
                "estimated_effort": "2 hours (estimate)",
                "suggested_timing": "Day 2–3",
                "dependency_ids": ["a1"],
                "expected_outcome": "Readable draft ready for human review",
                "evidence_refs": [],
                "owner": "user",
            },
            {
                "action_id": "a4",
                "title": "Review and decide",
                "description": "Inspect assumptions, revise if needed, then approve or reject the deliverable.",
                "priority": "high",
                "estimated_effort": "30 minutes (estimate)",
                "suggested_timing": "Day 4–5",
                "dependency_ids": ["a3"],
                "expected_outcome": "Explicit human decision recorded",
                "evidence_refs": [],
                "owner": "user",
            },
        ],
        "timeline": [
            {"day": "Day 1", "focus": "Frame and schedule"},
            {"day": "Day 2–3", "focus": "Research synthesis and draft"},
            {"day": "Day 4", "focus": "Challenge and revise"},
            {"day": "Day 5", "focus": "Approve and export"},
        ],
        "dependencies": ["a2 depends on a1", "a3 depends on a1", "a4 depends on a3"],
        "risks": [
            "Meetings crowd out focus blocks",
            "Recommendations outrun available evidence",
        ],
        "assumptions": [
            "User owns final calendar changes",
            "Effort figures are estimates, not commitments",
        ],
        "success_metrics": [
            "Deliverable covers objective, findings, recommendations, and next steps",
            "At least one revision cycle is inspectable when requested",
            "Human approval is explicit",
        ],
        "open_decisions": [
            "Which priority drops first if capacity shrinks?",
            "Is the requested output format still preferred?",
        ],
    }


def build_deliverable(
    task: str,
    *,
    revised: bool = False,
    revision_note: str | None = None,
) -> dict[str, Any]:
    title = "Personal Productivity Workforce Briefing"
    if revised:
        title += " (Revised)"
    revision_blurb = ""
    if revised:
        revision_blurb = (
            f"\n\n### Revision notes\nAddressed reviewer feedback"
            + (f": {revision_note}" if revision_note else ".")
            + " Unsupported absolute claims were softened and labelled as estimates.\n"
        )
    markdown = f"""# {title}

## Executive summary
This **Demo Mode** briefing is an illustrative deliverable for: *{task}*.
It demonstrates agent handoffs. It did **not** perform live web research.

## Objective
{task}

## Key findings
1. Clear agent roles make ownership visible.
2. Evidence gaps should be stated explicitly.
3. Human approval remains the final gate.

## Recommendations
1. Protect two deep-work blocks before adding meetings.
2. Keep recommendations tied to stated constraints.
3. Export the run report after approval for workshop notes.
{revision_blurb}
## Next steps
- Inspect Research, Plan, Deliverable, and Review tabs.
- Approve, request a revision, or reject.
- Download the Markdown briefing when ready.

## Unresolved questions
- Which constraint is non-negotiable?
- What evidence would you add from your own context?
"""
    return {
        "title": title,
        "executive_summary": (
            "Illustrative Demo Mode briefing showing research → plan → deliverable → review "
            "with a human approval gate. Not live-verified."
            + (" Revised after reviewer feedback." if revised else "")
        ),
        "objective": task,
        "key_findings": [
            "Specialised agents improve observability of work.",
            "Demo Mode never implies live research.",
            "Human approval is required before a run is marked approved.",
        ],
        "recommendations": [
            "Use Demo Mode to learn the workflow before enabling Live LLM Mode.",
            "Treat effort and timing as estimates.",
            "Record an explicit approve/reject decision.",
        ],
        "action_plan": [
            "Frame objective and constraints",
            "Schedule focus blocks",
            "Draft briefing",
            "Human review and decision",
        ],
        "resources": [
            "Personal AI Workforce Studio (this workshop app)",
            "Local run export (Markdown / JSON)",
        ],
        "assumptions": [
            "Workshop laptop has dependencies installed",
            "No confidential data was submitted",
        ],
        "unresolved_questions": [
            "Which success metric matters most to you?",
            "Do you need Live LLM Mode for this exercise?",
        ],
        "evidence_references": [],
        "markdown_content": markdown,
        "status": "revised" if revised else "draft",
    }


def build_review(
    *,
    revision_required: bool,
    quality_score: int,
) -> dict[str, Any]:
    if revision_required:
        return {
            "status": "revision_required",
            "quality_score": quality_score,
            "criteria_results": [
                {"criterion": "Task alignment", "passed": True, "note": "Objective is reflected."},
                {
                    "criterion": "Evidence quality",
                    "passed": False,
                    "note": "One recommendation read as absolute without evidence.",
                },
                {"criterion": "Actionability", "passed": True, "note": "Actions are concrete."},
                {"criterion": "Assumption transparency", "passed": True, "note": "Assumptions listed."},
                {"criterion": "Safety / human approval", "passed": True, "note": "No external actions."},
            ],
            "issues": [
                "Deliverable includes a recommendation that sounds definitive without live evidence.",
            ],
            "missing_information": [
                "User-specific capacity details",
            ],
            "unsupported_claims": [
                "Absolute wording around guaranteed productivity gains.",
            ],
            "recommendations": [
                "Soften absolute claims and label estimates clearly.",
                "Restate Demo Mode research limitations in the executive summary.",
            ],
            "revision_targets": ["execution"],
            "reviewer_summary": (
                "Independent review requests one bounded revision to soften unsupported "
                "absolute claims. Score is an LLM-style assessment fixture, not objective truth."
            ),
        }
    return {
        "status": "approved",
        "quality_score": quality_score,
        "criteria_results": [
            {"criterion": "Task alignment", "passed": True, "note": "Aligned."},
            {"criterion": "Completeness", "passed": True, "note": "Core sections present."},
            {"criterion": "Evidence quality", "passed": True, "note": "Limitations disclosed."},
            {"criterion": "Actionability", "passed": True, "note": "Next steps clear."},
            {"criterion": "Clarity", "passed": True, "note": "Readable for workshop use."},
            {"criterion": "Assumption transparency", "passed": True, "note": "Assumptions listed."},
            {"criterion": "Safety / human approval", "passed": True, "note": "No side effects."},
        ],
        "issues": [],
        "missing_information": ["Live sources (expected in Demo Mode)"],
        "unsupported_claims": [],
        "recommendations": [
            "Ready for human review. Human must still approve or reject.",
        ],
        "revision_targets": [],
        "reviewer_summary": (
            "Reviewer passes the revised deliverable for human approval. "
            "This is not automatic human approval."
        ),
    }


def build_demo_packets(
    *,
    task: str,
    background: str = "",
    constraints: str = "",
    time_horizon: str = "",
    output_format: str = "Briefing",
    run_id: str | None = None,
) -> dict[str, Any]:
    rid = run_id or str(uuid4())
    return {
        "run_id": rid,
        "task_specification": build_task_spec(
            run_id=rid,
            task=task,
            background=background,
            constraints=constraints,
            time_horizon=time_horizon,
            output_format=output_format,
            execution_mode="demo",
        ),
        "research": build_research_packet(rid, task),
        "plan": build_plan(task),
        "deliverable_v1": build_deliverable(task, revised=False),
        "review_v1": build_review(revision_required=True, quality_score=68),
        "deliverable_v2": build_deliverable(
            task,
            revised=True,
            revision_note="softened absolute claims; restated Demo Mode limitations",
        ),
        "review_v2": build_review(revision_required=False, quality_score=86),
    }


# --------------------------------------------------------------------------- #
# Task-class fixtures (job_search / competitive_analysis). No network, no model.
# --------------------------------------------------------------------------- #

DEMO_JOB_SOURCE = "demo"
_DEMO_URL_BASE = "https://example.invalid/jobs/"


def build_demo_job_records(retrieved_at: datetime | None = None) -> list:
    """Illustrative rows with obvious fake ids and example.invalid URLs.

    Mix is chosen so the filters are visible: included (exact + overlap), needs-review,
    and several excluded reasons (wrong role, wrong city, stale, no band overlap).
    """
    from datetime import timedelta

    from src.models.job_search import JobRecord

    now = retrieved_at or datetime.now(timezone.utc)

    def rec(
        n: str,
        title: str,
        company: str,
        loc: str,
        days_ago: int,
        exp_text: str | None,
        desc: str,
        *,
        city: str | None = None,
    ) -> JobRecord:
        job_id = f"demo-{n}"
        return JobRecord(
            job_id=job_id,
            source=DEMO_JOB_SOURCE,
            source_job_id=job_id,
            title=title,
            company_name=company,
            job_description=f"{desc} (Illustrative demo description, not a real posting.)",
            description_completeness="full",
            location_text=loc,
            city=city or loc.split(",")[0],
            country_code="IN",
            date_posted=(now - timedelta(days=days_ago)).isoformat(),
            experience_text=exp_text,
            employment_type="Full-time",
            workplace="onsite",
            apply_url=f"{_DEMO_URL_BASE}{job_id}",
            retrieved_at=now.isoformat(),
        )

    return [
        rec("hyd-pm-1", "Senior Product Manager", "Example Software Pvt Ltd", "Hyderabad, Telangana", 2, "6-9 years",
            "Own the roadmap for a B2B workflow product and partner with engineering and design."),
        rec("hyd-pm-2", "Lead Product Manager - Platform", "Sample Cloud Labs", "Gachibowli, Hyderabad, Telangana", 4, "4-7 years",
            "Lead platform product strategy and developer experience.", city="Hyderabad"),
        rec("hyd-pm-3", "Product Manager, Payments", "Placeholder Fintech Pvt Ltd", "HITEC City, Hyderabad, Telangana", 5, "8-12 years",
            "Drive payments product discovery and delivery.", city="Hyderabad"),
        rec("hyd-pm-4", "Group Product Manager", "Illustrative Retail Tech", "Hyderabad, Telangana", 3, None,
            "Lead a group of product managers across the commerce suite."),
        rec("hyd-prj-5", "Project Manager", "Example Software Pvt Ltd", "Hyderabad, Telangana", 1, "6-9 years",
            "Manage delivery timelines and vendor coordination."),
        rec("blr-pm-6", "Product Manager", "Demo Analytics Co", "Bengaluru, Karnataka", 2, "6-8 years",
            "Own analytics product experience."),
        rec("hyd-pm-7", "Product Manager", "Fixture Systems", "Hyderabad, Telangana", 20, "5-8 years",
            "Posted well outside the requested window."),
        rec("hyd-apm-8", "Associate Product Manager", "Mock Learning Pvt Ltd", "Hyderabad, Telangana", 2, "1-3 years",
            "Entry-level product role."),
    ]


def build_demo_job_envelope(
    intent: Any | None = None,
    *,
    retrieved_at: datetime | None = None,
) -> dict[str, Any]:
    """Illustrative job envelope run through the real filters (include/needs_review/exclude)."""
    from src.models.job_search import JobSearchIntent
    from src.services.job_intent import apply_job_filters, parse_job_search_intent

    now = retrieved_at or datetime.now(timezone.utc)
    if intent is None:
        intent = parse_job_search_intent(
            "Find product manager jobs in Hyderabad, 5-10 years of experience, posted in the last 7 days."
        )
    elif isinstance(intent, dict):
        intent = JobSearchIntent.model_validate(intent)
    envelope = apply_job_filters(
        build_demo_job_records(now),
        intent,
        retrieved_at=now,
        source_name=DEMO_JOB_SOURCE,
        illustrative=True,
        extra_notes=["Demo Mode fixtures: no network call was made."],
    )
    return envelope.model_dump(mode="json")


def build_demo_comparison_envelope(intent: Any | None = None) -> dict[str, Any]:
    """Illustrative comparison envelope; defaults to the PM vs Product Marketer sample context."""
    from src.models.competitive_analysis import CompetitiveAnalysisIntent
    from src.services.comparison_intent import (
        build_comparison_envelope,
        parse_competitive_analysis_intent,
    )

    if intent is None:
        from src.config.samples import SAMPLE_TASKS, SAMPLE_COMPARE_RICH_LABEL

        packet = SAMPLE_TASKS[SAMPLE_COMPARE_RICH_LABEL]
        intent = parse_competitive_analysis_intent(
            packet["task"], packet["background"], packet["constraints"], packet["time_horizon"]
        )
    elif isinstance(intent, dict):
        intent = CompetitiveAnalysisIntent.model_validate(intent)
    envelope = build_comparison_envelope(intent, illustrative=True)
    return envelope.model_dump(mode="json")
