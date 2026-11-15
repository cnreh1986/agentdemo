"""Deterministic reviewer checks for job_search and competitive_analysis runs.

These checks run in code after (or beside) the LLM review so a fluent essay cannot pass
when the structured envelope is wrong (newehancement.md 10.5 and 23.5).
"""

from __future__ import annotations

import re
from typing import Any

from src.models.competitive_analysis import (
    CompetitiveAnalysisIntent,
    ComparisonEnvelope,
)
from src.models.job_search import JobSearchEnvelope, JobSearchIntent
from src.services.job_intent import (
    _parse_iso,
    text_has_ungrounded_refs,
    title_in_family,
)

_SAFETY_JOB = re.compile(
    r"\b(?:i|we|the workforce|the agents?)\s+(?:have\s+|has\s+)?(?:already\s+)?"
    r"(?:applied|emailed|e-mailed|messaged|contacted|scheduled|booked)\b"
    r"|\bapplications?\s+(?:were|have been|has been)\s+(?:submitted|sent)\b"
    r"|\binterviews?\s+(?:were|have been)\s+(?:scheduled|booked)\b",
    re.I,
)
_SAFETY_COMPARISON = re.compile(
    r"\b(?:requisition|role|position|job)\s+(?:has been|was|have been)\s+(?:opened|posted|published)\b"
    r"|\b(?:i|we|the workforce)\s+(?:have\s+)?(?:already\s+)?(?:opened|posted|published|hired|emailed)\b",
    re.I,
)
_JOB_AD_DRAFT = re.compile(
    r"\b(?:responsibilities|requirements|qualifications)\s*:\s*|\bwe are (?:hiring|looking for)\b|\bapply (?:now|today)\b",
    re.I,
)


def _deliverable_text(deliverable: dict[str, Any] | None) -> str:
    d = deliverable or {}
    parts = [str(d.get("markdown_content") or ""), str(d.get("executive_summary") or "")]
    for key in ("recommendations", "key_findings", "action_plan", "resources"):
        parts.extend(str(x) for x in (d.get(key) or []))
    return "\n".join(parts)


def check_job_search(
    envelope_dict: dict[str, Any] | None,
    intent_dict: dict[str, Any] | None,
    deliverable: dict[str, Any] | None = None,
) -> list[str]:
    """Return a list of failure messages (empty means pass)."""
    if not envelope_dict:
        return ["Completeness: no job envelope was produced for this job_search run."]
    envelope = JobSearchEnvelope.model_validate(envelope_dict)
    intent = JobSearchIntent.model_validate(intent_dict or {})
    issues: list[str] = []
    allowed_ids = set(envelope.raw_tool_job_ids)
    allowed_urls = set((envelope.extra or {}).get("allowed_urls") or [])
    posted_after = _parse_iso(envelope.query_echo.posted_after)
    exp_filter = intent.experience.min_years is not None or intent.experience.max_years is not None

    for job in envelope.jobs:
        label = job.job_id or "<missing id>"
        if not job.job_id.strip() or not (job.company_name or "").strip() or not job.job_description.strip():
            issues.append(f"Identity: included row {label} has an empty job id, company, or description.")
        if job.job_id not in allowed_ids:
            issues.append(f"Grounding: job id {label} is not in the research tool payload.")
        if job.apply_url and job.apply_url not in allowed_urls:
            issues.append(f"Grounding: apply URL for {label} is not in the research tool payload.")
        ok, _ = title_in_family(job.title, intent)
        if not ok:
            issues.append(f"Role: included title '{job.title}' ({label}) is out of the role family.")
        if intent.location.city and job.location_match not in {"city", "locality_alias"}:
            issues.append(f"Place: included row {label} is not in {intent.location.city} or a listed locality.")
        if intent.posted_within_days is not None:
            posted = _parse_iso(job.date_posted)
            if posted is None:
                issues.append(f"Recency: included row {label} has no date_posted.")
            elif posted_after and posted < posted_after:
                issues.append(f"Recency: included row {label} was posted before {posted_after.date()}.")
        if exp_filter and job.experience_match not in {"exact", "overlap"}:
            issues.append(
                f"Experience: included row {label} has experience_match '{job.experience_match}'."
            )

    # Completeness: summary counts must equal the arrays.
    c = envelope.counts
    for key, arr in (("included", envelope.jobs), ("needs_review", envelope.needs_review), ("excluded", envelope.excluded)):
        if key in c and c[key] != len(arr):
            issues.append(f"Completeness: counts.{key}={c[key]} but the array has {len(arr)} rows.")
    if allowed_ids and not (envelope.jobs or envelope.needs_review or envelope.excluded):
        issues.append("Completeness: the tool returned listings but the envelope shows none of them.")

    text = _deliverable_text(deliverable)
    if deliverable and text_has_ungrounded_refs(text, allowed_ids=allowed_ids, allowed_urls=allowed_urls):
        issues.append("Grounding: the deliverable text cites a job id or URL that the tool never returned.")
    if _SAFETY_JOB.search(text):
        issues.append("Safety: the deliverable says an application, email, or interview was already done.")
    if deliverable and envelope.jobs:
        md = str(deliverable.get("markdown_content") or "")
        missing = [j.job_id for j in envelope.jobs if j.job_id not in md]
        if md and missing:
            issues.append("Completeness: the deliverable markdown drifted from the structured jobs array.")
    return issues


def check_comparison(
    envelope_dict: dict[str, Any] | None,
    intent_dict: dict[str, Any] | None,
    deliverable: dict[str, Any] | None = None,
) -> list[str]:
    if not envelope_dict:
        return ["Completeness: no comparison envelope was produced for this competitive_analysis run."]
    envelope = ComparisonEnvelope.model_validate(envelope_dict)
    intent = CompetitiveAnalysisIntent.model_validate(intent_dict or envelope_dict.get("intent_echo") or {})
    issues: list[str] = []
    text = _deliverable_text(deliverable)
    allowed_urls = set((envelope.extra or {}).get("allowed_urls") or [])
    role_catalog_ids = {
        "problem_ownership", "roadmap", "positioning", "launch", "pricing",
        "enablement", "discovery", "metrics", "artifacts", "horizon", "current_ownership",
    }

    if envelope.status == "needs_context":
        if envelope.matrix:
            issues.append("Decision: needs_context run must leave the contextual matrix empty.")
        if not envelope.open_questions:
            issues.append("Decision: needs_context run must list the questions that unblock it.")
        if not envelope.domain_frame_banner:
            issues.append("Basis: the domain frame is not labelled as generic.")
        frame = (envelope.extra or {}).get("domain_frame") or []
        if any(c.get("basis") != "domain_default" for c in frame):
            issues.append("Basis: every domain-frame cell must be labelled domain_default.")
    else:
        if not envelope.matrix:
            issues.append("Coverage: status is ready but the comparison matrix is empty.")
        intent_subjects = {s.subject_id for s in intent.subjects}
        matrix_subjects = {c.subject_id for c in envelope.matrix}
        missing = intent_subjects - matrix_subjects
        extra = matrix_subjects - intent_subjects
        if missing:
            issues.append(f"Subjects: named subject(s) missing from the matrix: {', '.join(sorted(missing))}.")
        if extra:
            issues.append(f"Subjects: extra column(s) not named by the user: {', '.join(sorted(extra))}.")
        criteria = {c.criterion_id for c in envelope.matrix}
        for crit in sorted(criteria):
            have = {c.subject_id for c in envelope.matrix if c.criterion_id == crit}
            if intent_subjects - have:
                issues.append(f"Coverage: criterion '{crit}' lacks a cell for every subject.")
        if intent.comparison_kind == "product":
            # Role-catalog rows that the user did not name as product criteria.
            user_crit = set()
            policy = intent.criteria_policy or ""
            if policy.startswith("user_listed:"):
                for part in policy[len("user_listed:") :].split(";"):
                    cid = re.sub(r"[^a-z0-9]+", "_", part.strip().lower()).strip("_")
                    if cid:
                        user_crit.add(cid)
            catalog_on_product = sorted(
                c for c in criteria if c in role_catalog_ids and c not in user_crit
            )
            if catalog_on_product:
                issues.append(
                    "Subjects: role-catalog rows must not appear on a product matrix: "
                    + ", ".join(catalog_on_product)
                )
        for cell in envelope.matrix:
            tag = f"{cell.subject_id}:{cell.criterion_id}"
            if cell.basis == "unknown" and cell.value.strip():
                issues.append(f"Basis: cell {tag} has text but basis 'unknown'.")
            if cell.basis != "unknown" and not cell.value.strip():
                issues.append(f"Basis: cell {tag} is empty but basis is '{cell.basis}'.")
            if cell.basis == "public_source" and not any(e.source_url for e in cell.evidence):
                issues.append(f"Basis: public_source cell {tag} has no source URL.")
            if cell.basis == "public_source":
                for ev in cell.evidence:
                    if ev.basis != "public_source":
                        continue
                    if not ev.source_url:
                        issues.append(f"Basis: public_source cell {tag} has no source URL.")
                    elif allowed_urls and ev.source_url not in allowed_urls:
                        issues.append(
                            f"Basis: public_source cell {tag} cites a URL not returned by the search tool."
                        )
            if cell.basis == "user_supplied" and not any(e.basis == "user_supplied" and e.claim.strip() for e in cell.evidence):
                issues.append(f"Blanks: user_supplied cell {tag} quotes no user statement.")
            if cell.basis == "unknown" and cell.criterion_id == "pricing" and cell.value:
                issues.append(f"Blanks: pricing fact in {tag} was never stated by the user.")
        unknowns = (envelope.extra or {}).get("unknowns")
        if unknowns is None:
            issues.append("Blanks: envelope must list unknown cells under extra.unknowns.")
        # Precedence: user ownership notes must survive as user_supplied cells.
        for note in intent.user_context.current_ownership:
            obj = note.split(":")[0].strip().lower()
            if not any(
                c.basis == "user_supplied" and obj in c.value.lower()
                for c in envelope.matrix
            ):
                issues.append(f"Precedence: user-stated ownership '{note}' is missing as a user_supplied cell.")
        if not envelope.options:
            issues.append("Decision: no option addresses the decision.")

    low = text.lower()
    constraints = " ".join(intent.decision.constraints).lower()
    if "candidate" in constraints and re.search(r"\bcandidate\s+(?:name|named)\b|\bhire\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b", text):
        issues.append("Safety: the deliverable names a candidate.")
    if _JOB_AD_DRAFT.search(text) and ("job ad" in constraints or "advertisement" in constraints or "job advertisement" in low):
        issues.append("Decision: the deliverable drafts a job advertisement the user asked not to produce.")
    if _SAFETY_COMPARISON.search(text):
        issues.append("Safety: the deliverable says a role was opened, posted, or a hire made.")
    return issues


def class_review_issues(
    task_class: str,
    *,
    envelope: dict[str, Any] | None,
    intent: dict[str, Any] | None,
    deliverable: dict[str, Any] | None,
) -> list[str]:
    if task_class == "job_search":
        return check_job_search(envelope, intent, deliverable)
    if task_class == "competitive_analysis":
        return check_comparison(envelope, intent, deliverable)
    return []

