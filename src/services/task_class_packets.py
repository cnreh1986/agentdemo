"""Research / plan / deliverable packets derived from typed envelopes.

Used by the research agent (live and demo) and by the Demo provider so the packets for
job_search and competitive_analysis are built from the envelope, not from free text.
"""

from __future__ import annotations

from typing import Any

from src.models.competitive_analysis import ComparisonEnvelope
from src.models.job_search import JobSearchEnvelope
from src.services.task_class_render import job_summary_line

DEMO_JOB_LIMITATIONS = [
    "Demo Mode: illustrative records with fake ids. No search was run and no live openings were retrieved.",
    "Records are fixtures run through the same role, place, recency, and experience filters as a live run.",
]
DEMO_COMPARISON_LIMITATIONS = [
    "Demo Mode: illustrative comparison. The company context is fictional and no public pages were retrieved.",
    "Domain-default cells describe the usual split between the roles, not a study of any real company.",
]


def _action(aid: str, title: str, desc: str, priority: str, deps: list[str], outcome: str) -> dict[str, Any]:
    return {
        "action_id": aid,
        "title": title,
        "description": desc,
        "priority": priority,
        "estimated_effort": "15 minutes (estimate)",
        "suggested_timing": "After approval",
        "dependency_ids": deps,
        "expected_outcome": outcome,
        "evidence_refs": [],
        "owner": "user",
    }


# ----------------------------------------------------------------------- jobs


def job_research_packet(
    run_id: str, task: str, envelope: JobSearchEnvelope, *, mode: str
) -> dict[str, Any]:
    limitations = list(DEMO_JOB_LIMITATIONS if mode == "demo" else [])
    if mode != "demo":
        limitations.append(
            f"Live job search via {envelope.query_echo.source_name or 'SerpAPI Google Jobs'}; "
            "rows are copied from the tool payload and filtered in code."
        )
    limitations.extend(envelope.coverage_notes)
    for failed in envelope.sources_failed:
        limitations.append(f"Source failed: {failed}")
    return {
        "run_id": run_id,
        "research_question": f"Which listings match: {task}",
        "key_findings": [job_summary_line(envelope)],
        "evidence_items": [],
        "assumptions": [
            "Filters were applied exactly as shown in the query echo.",
            "Experience overlap with the requested band counts as a match; unstated years go to review.",
        ],
        "uncertainties": [
            "Experience is parsed from source text and may be missing or approximate.",
        ],
        "risks": [
            "Coverage on a single jobs source can be thin; an empty table is reported honestly.",
        ],
        "open_questions": [f"Filter not stated in the task: {f}" for f in envelope.query_echo.open_filters],
        "research_limitations": limitations,
        "status": "completed",
        "agent_summary": job_summary_line(envelope) + ".",
    }


def job_plan(task: str, envelope: JobSearchEnvelope) -> dict[str, Any]:
    exact = [j for j in envelope.jobs if j.experience_match == "exact"]
    overlap = [j for j in envelope.jobs if j.experience_match == "overlap"]
    actions = [
        _action(
            "a1",
            "Review the exact-band rows first",
            f"{len(exact)} included row(s) sit fully inside the requested experience band.",
            "high",
            [],
            "Shortlist of strongest matches",
        ),
        _action(
            "a2",
            "Judge the borderline overlaps",
            f"{len(overlap)} included row(s) only overlap the band (for example 4-7 or 8-12 years).",
            "medium",
            ["a1"],
            "Decision on which overlaps are worth a closer look",
        ),
        _action(
            "a3",
            "Resolve rows with no stated experience",
            f"{len(envelope.needs_review)} in-family row(s) were held back because years were not stated.",
            "medium",
            ["a1"],
            "Needs-review rows confirmed or dropped",
        ),
        _action(
            "a4",
            "Decide what the set means for you",
            "Check specialisation, salary (source estimate versus disclosed), and truncated descriptions. "
            "Nothing was applied to; any application is your own step.",
            "high",
            ["a2", "a3"],
            "Explicit human decision recorded",
        ),
    ]
    return {
        "objective": task,
        "strategic_rationale": (
            "A short decision plan for reading the retrieved set. The workforce did not apply to any job."
        ),
        "priorities": ["Read exact matches", "Judge overlaps", "Resolve missing experience"],
        "actions": actions,
        "timeline": [{"day": "Review", "focus": "Read the included and needs-review tables"}],
        "dependencies": ["a2 depends on a1", "a3 depends on a1", "a4 depends on a2 and a3"],
        "risks": ["Descriptions may be truncated at the source", "Source coverage may be thin"],
        "assumptions": ["Owner is the user for every action"],
        "success_metrics": ["Included rows match every filter", "Exclusions are explained"],
        "open_decisions": ["Which specialisation matters?", "Is predicted salary acceptable as a signal?"],
    }


def job_deliverable_fields(envelope: JobSearchEnvelope, *, revised: bool = False) -> dict[str, Any]:
    exact = sum(1 for j in envelope.jobs if j.experience_match == "exact")
    overlap = sum(1 for j in envelope.jobs if j.experience_match == "overlap")
    truncated = sum(1 for j in envelope.jobs if j.description_completeness == "truncated")
    summary = job_summary_line(envelope) + "."
    if envelope.illustrative:
        summary += " Illustrative fixtures, not live openings."
    recs = [
        f"{exact} exact match(es), {overlap} overlap(s) with the requested experience band.",
        f"{truncated} included description(s) are truncated at the source; they were not completed.",
        f"{len(envelope.needs_review)} row(s) await a human check on experience.",
    ]
    return {
        "title": "Job search results" + (" (revised)" if revised else ""),
        "executive_summary": summary,
        "objective": envelope.query_echo.role_query or "Job search",
        "key_findings": [job_summary_line(envelope)],
        "recommendations": recs,
        "action_plan": [
            "Read the included table, then needs-review",
            "Decide which rows deserve a closer look",
        ],
        "resources": [],
        "assumptions": ["Filters were applied in code exactly as shown in the query echo."],
        "unresolved_questions": ["Which specialisation matters most?"],
        "evidence_references": [j.job_id for j in envelope.jobs],
        "status": "revised" if revised else "draft",
    }


# ----------------------------------------------------------- comparison


def _basis_counts(envelope: ComparisonEnvelope) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in envelope.matrix:
        counts[c.basis] = counts.get(c.basis, 0) + 1
    return counts


def comparison_research_packet(
    run_id: str,
    task: str,
    envelope: ComparisonEnvelope,
    *,
    mode: str,
    public_items: list[dict[str, Any]] | None = None,
    search_note: str | None = None,
) -> dict[str, Any]:
    extra = envelope.extra or {}
    evidence: list[dict[str, Any]] = []
    for line in extra.get("context_echo") or []:
        evidence.append(
            {
                "claim": line,
                "source_title": "User context",
                "source_url": None,
                "evidence_type": "user_supplied",
                "confidence": "high",
                "supporting_excerpt_or_summary": "Quoted from the user's task context.",
            }
        )
    evidence.extend(public_items or [])
    counts = _basis_counts(envelope)
    if envelope.status == "needs_context":
        findings = ["Context is thin: returned a labelled domain frame and the questions that unblock a real run."]
    else:
        findings = [
            f"Matrix has {len(envelope.matrix)} cells: "
            + ", ".join(f"{n} {b.replace('_', ' ')}" for b, n in sorted(counts.items()))
            + "."
        ]
    limitations = list(DEMO_COMPARISON_LIMITATIONS if mode == "demo" else [])
    limitations.extend(extra.get("limitations") or [])
    if search_note:
        limitations.append(search_note)
    return {
        "run_id": run_id,
        "research_question": f"What does the user's context say about: {task}",
        "key_findings": findings,
        "evidence_items": evidence,
        "assumptions": ["User-supplied context is treated as true and outranks generic articles."],
        "uncertainties": list(extra.get("unknowns") or [])[:8],
        "risks": ["Domain defaults can be mistaken for facts about the company; cells are labelled."],
        "open_questions": list(envelope.open_questions),
        "research_limitations": list(dict.fromkeys(limitations)),
        "status": "completed",
        "agent_summary": findings[0],
    }


def comparison_plan(task: str, envelope: ComparisonEnvelope) -> dict[str, Any]:
    if envelope.status == "needs_context":
        actions = [
            _action(
                f"a{i}",
                q,
                "Answer this in the task background or constraints, then run again.",
                "high",
                [],
                "Context provided",
            )
            for i, q in enumerate(envelope.open_questions[:5], start=1)
        ] or [_action("a1", "Provide context", "Add decision and situation.", "high", [], "Context provided")]
        rationale = "The comparison waits for your context. No analysis was invented."
    else:
        actions = [
            _action("a1", "Resolve the unknown cells", "; ".join((envelope.extra or {}).get("unknowns", [])[:4]) or "None.", "high", [], "Blanks answered or accepted"),
            _action("a2", "Weigh the options against your constraint", "Pick the option whose uncovered gap you can live with.", "high", ["a1"], "Option chosen"),
            _action("a3", "Check domain-default cells against your reality", "Replace any default that does not match your team.", "medium", [], "Defaults corrected"),
        ]
        rationale = "Options are tied to matrix cells. The human decides; nothing is hired or posted."
    return {
        "objective": task,
        "strategic_rationale": rationale,
        "priorities": ["Answer open questions", "Choose among options"],
        "actions": actions,
        "timeline": [{"day": "Review", "focus": "Read the matrix and options"}],
        "dependencies": [],
        "risks": ["Domain defaults may not match your organisation"],
        "assumptions": ["Owner is the user for every action"],
        "success_metrics": ["Every filled cell has a basis", "Unknowns are listed"],
        "open_decisions": list(envelope.open_questions[:3]),
    }


def comparison_deliverable_fields(envelope: ComparisonEnvelope, *, revised: bool = False) -> dict[str, Any]:
    intent = envelope.intent_echo
    names = " vs ".join(s.label for s in intent.subjects) if intent else "comparison"
    if envelope.status == "needs_context":
        summary = (
            "Status: needs context. A generic domain frame is shown and the contextual matrix is "
            "intentionally empty until you provide the decision and the situation."
        )
        recs = ["Answer the listed questions and run again; no recommendation was invented."]
    else:
        counts = _basis_counts(envelope)
        summary = (
            f"Comparison of {names} for: {intent.decision.question if intent else ''} "
            + "Cells by basis: "
            + ", ".join(f"{n} {b.replace('_', ' ')}" for b, n in sorted(counts.items()))
            + "."
        )
        recs = [f"{o.label}: {o.implication}" for o in envelope.options]
    return {
        "title": f"Comparison: {names}" + (" (revised)" if revised else ""),
        "executive_summary": summary,
        "objective": (intent.decision.question if intent else "") or "Comparison",
        "key_findings": [summary],
        "recommendations": recs,
        "action_plan": ["Review the matrix", "Resolve unknowns", "Decide among options"],
        "resources": [],
        "assumptions": ["User-supplied context is treated as true; domain defaults are labelled."],
        "unresolved_questions": list(envelope.open_questions),
        "evidence_references": [],
        "status": "revised" if revised else "draft",
    }
