"""Render job and comparison envelopes as table rows, Markdown, and CSV.

Markdown is a view of the structured envelope (newehancement.md 10.4): when the two
disagree, the envelope wins.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from src.models.competitive_analysis import ComparisonEnvelope
from src.models.job_search import JobRecord, JobSearchEnvelope

ILLUSTRATIVE_JOBS_BANNER = (
    "Illustrative, not live openings: Demo Mode fixtures with fake ids. No search was run."
)
ILLUSTRATIVE_COMPARISON_BANNER = (
    "Illustrative example: fictional company context. No live research was performed "
    "and no real company was analysed."
)

CONFIDENCE_BY_BASIS = {
    "user_supplied": "high",
    "public_source": "medium",
    "domain_default": "medium",
    "inference": "low",
    "unknown": "",
}


def _cell(text: Any) -> str:
    return str(text if text is not None else "").replace("|", "/").replace("\n", " ").strip()


def experience_label(job: JobRecord) -> str:
    if job.experience_min is None and job.experience_max is None:
        return "not stated"
    if job.experience_max is None:
        band = f"{job.experience_min}+ yrs"
    elif job.experience_min is None:
        band = f"up to {job.experience_max} yrs"
    else:
        band = f"{job.experience_min}-{job.experience_max} yrs"
    return f"{band} ({job.experience_match})"


def job_table_rows(jobs: list[JobRecord], *, description_chars: int = 400) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for job in jobs:
        desc = job.job_description or ""
        short = desc if len(desc) <= description_chars else desc[:description_chars].rstrip() + "…"
        rows.append(
            {
                "Job id": job.job_id,
                "Title": job.title,
                "Company": job.company_name or "",
                "Location": job.city or job.location_text,
                "Posted": (job.date_posted or "")[:10] or (job.posted_label or ""),
                "Experience": experience_label(job),
                "Match": job.match_status,
                "Reason": "; ".join(job.match_reasons[:2]),
                "Description": short,
                "Apply URL": job.apply_url or "",
            }
        )
    return rows


def excluded_reason_groups(envelope: JobSearchEnvelope) -> dict[str, list[JobRecord]]:
    groups: dict[str, list[JobRecord]] = {}
    for job in envelope.excluded:
        code = job.match_reasons[0] if job.match_reasons else "excluded"
        groups.setdefault(code, []).append(job)
    return groups


def job_summary_line(envelope: JobSearchEnvelope) -> str:
    c = envelope.counts
    parts = [
        f"{c.get('retrieved', 0)} retrieved",
        f"{len(envelope.jobs)} included",
        f"{len(envelope.needs_review)} need review",
        f"{len(envelope.excluded)} excluded",
    ]
    reasons = [
        f"{n} {k.removeprefix('excluded_').replace('_', ' ')}"
        for k, n in sorted(c.items())
        if k.startswith("excluded_")
    ]
    line = ", ".join(parts)
    if reasons:
        line += " (excluded: " + ", ".join(reasons) + ")"
    return line


def _md_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    out.extend("| " + " | ".join(_cell(c) for c in row) + " |" for row in rows)
    return out


def _echo_lines(envelope: JobSearchEnvelope) -> list[str]:
    e = envelope.query_echo
    exp = (
        f"{e.experience_min if e.experience_min is not None else '?'}-"
        f"{e.experience_max if e.experience_max is not None else '+'} years ({e.range_policy})"
        if e.experience_min is not None or e.experience_max is not None
        else "not applied"
    )
    posted = (
        f"posted after {e.posted_after[:10]} (last {e.posted_within_days} days)"
        if e.posted_after
        else "not applied"
    )
    return [
        f"- **Role family:** {e.role_family} (`{e.role_query}`)",
        f"- **Location:** {e.city or 'not applied'}"
        + (f", radius {e.radius_km} km" if e.city else ""),
        f"- **Experience:** {exp}",
        f"- **Recency:** {posted}",
        f"- **Source:** {e.source_name or 'n/a'} · **Retrieved:** {e.retrieved_at}",
    ]


def render_job_markdown(
    envelope: JobSearchEnvelope,
    *,
    title: str = "Job search results",
    executive_summary: str = "",
    recommendations: list[str] | None = None,
) -> str:
    lines = [f"# {title}", ""]
    if envelope.illustrative:
        lines += [f"> **{ILLUSTRATIVE_JOBS_BANNER}**", ""]
    if executive_summary:
        lines += ["## Summary", executive_summary, ""]
    lines += ["## Query echo", *_echo_lines(envelope), ""]
    lines += [f"**Coverage:** {job_summary_line(envelope)}", ""]
    if envelope.sources_failed:
        lines += ["**Sources failed:** " + "; ".join(envelope.sources_failed), ""]

    lines += ["## Included jobs"]
    if envelope.jobs:
        rows = job_table_rows(envelope.jobs)
        lines += _md_table(
            ["Job id", "Title", "Company", "Location", "Posted", "Experience", "Match", "Description"],
            [[r["Job id"], r["Title"], r["Company"], r["Location"], r["Posted"], r["Experience"], r["Match"], r["Description"]] for r in rows],
        )
    else:
        lines.append("_No jobs met every filter. See the exclusion counts above; nothing was invented._")
    lines.append("")

    lines += ["## Needs review (experience not stated)"]
    if envelope.needs_review:
        rows = job_table_rows(envelope.needs_review)
        lines += _md_table(
            ["Job id", "Title", "Company", "Location", "Posted", "Experience"],
            [[r["Job id"], r["Title"], r["Company"], r["Location"], r["Posted"], r["Experience"]] for r in rows],
        )
    else:
        lines.append("_None._")
    lines.append("")

    lines += ["## Excluded"]
    groups = excluded_reason_groups(envelope)
    if groups:
        for code, jobs in sorted(groups.items()):
            lines.append(f"**{code.replace('_', ' ')}** ({len(jobs)})")
            for job in jobs:
                lines.append(f"- `{job.job_id}` {job.title} — {job.company_name or 'unknown company'}")
            lines.append("")
    else:
        lines += ["_None._", ""]

    if envelope.coverage_notes:
        lines += ["## Coverage notes", *[f"- {n}" for n in envelope.coverage_notes], ""]
    if recommendations:
        lines += ["## How to read this set", *[f"- {r}" for r in recommendations], ""]
    lines += [
        "## Boundaries",
        "- The workforce retrieved and structured listings only. It did not apply, email a recruiter, or schedule anything.",
        "- Human approval accepts this result set; it does not submit applications.",
    ]
    return "\n".join(lines).strip() + "\n"


def jobs_csv(envelope: JobSearchEnvelope | dict[str, Any]) -> str:
    """CSV of included rows: job id, title, company, city, date posted, experience, apply URL."""
    env = envelope if isinstance(envelope, JobSearchEnvelope) else JobSearchEnvelope.model_validate(envelope)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["job_id", "title", "company", "city", "date_posted", "experience", "apply_url"])
    for job in env.jobs:
        writer.writerow(
            [
                job.job_id,
                job.title,
                job.company_name or "",
                job.city or job.location_text,
                (job.date_posted or "")[:10],
                job.experience_text or experience_label(job),
                job.apply_url or "",
            ]
        )
    return buf.getvalue()


# ---------------------------------------------------------------- comparison


def comparison_rows(envelope: ComparisonEnvelope) -> tuple[list[str], list[list[str]]]:
    """Pivot cells into (headers, rows): one row per criterion, one column per subject."""
    intent = envelope.intent_echo
    subjects = [(s.subject_id, s.label) for s in (intent.subjects if intent else [])]
    if not subjects and envelope.matrix:
        seen: dict[str, str] = {}
        for c in envelope.matrix:
            seen.setdefault(c.subject_id, c.subject_label)
        subjects = list(seen.items())
    criteria: dict[str, str] = {}
    for c in envelope.matrix:
        criteria.setdefault(c.criterion_id, c.criterion_label)
    headers = ["Criterion"] + [label for _, label in subjects]
    rows: list[list[str]] = []
    for crit_id, crit_label in criteria.items():
        row = [crit_label]
        for sid, _ in subjects:
            cell = next((c for c in envelope.matrix if c.criterion_id == crit_id and c.subject_id == sid), None)
            if cell is None or cell.basis == "unknown" or not cell.value:
                row.append("— (unknown)")
            else:
                row.append(f"[{cell.basis}] {cell.value}")
        rows.append(row)
    return headers, rows


def render_comparison_markdown(
    envelope: ComparisonEnvelope,
    *,
    title: str = "Comparison",
    executive_summary: str = "",
) -> str:
    extra = envelope.extra or {}
    lines = [f"# {title}", ""]
    if envelope.illustrative:
        lines += [f"> **{ILLUSTRATIVE_COMPARISON_BANNER}**", ""]
    if executive_summary:
        lines += ["## Summary", executive_summary, ""]
    intent = envelope.intent_echo
    lines += ["## Context echo"]
    if intent:
        lines.append(f"- **Subjects:** {', '.join(s.label for s in intent.subjects) or 'not parsed'}")
        lines.append(f"- **Decision:** {intent.decision.question or 'not stated'}")
        if intent.decision.audience:
            lines.append(f"- **Audience:** {intent.decision.audience}")
        for c in intent.decision.constraints:
            lines.append(f"- **Constraint:** {c}")
    for line in extra.get("context_echo") or []:
        lines.append(f"- {line}")
    lines.append("")

    if envelope.status == "needs_context":
        lines += ["## Status: needs context", ""]
        if envelope.domain_frame_banner:
            lines += [f"> **{envelope.domain_frame_banner}**", ""]
        frame = extra.get("domain_frame") or []
        if frame:
            subjects = []
            for cell in frame:
                if cell["subject_label"] not in subjects:
                    subjects.append(cell["subject_label"])
            crits: dict[str, dict[str, str]] = {}
            for cell in frame:
                crits.setdefault(cell["criterion_label"], {})[cell["subject_label"]] = cell["value"]
            lines += _md_table(
                ["Criterion"] + [f"{s} (domain default)" for s in subjects],
                [[crit] + [vals.get(s, "") for s in subjects] for crit, vals in crits.items()],
            )
            lines.append("")
        lines += ["## Questions that unblock a real run", *[f"- {q}" for q in envelope.open_questions], ""]
    else:
        headers, rows = comparison_rows(envelope)
        lines += ["## Comparison matrix"]
        if rows:
            lines += _md_table(headers, rows)
        else:
            lines.append("_No matrix rows._")
        lines.append("")
        if envelope.criteria_not_used:
            lines += ["**Criteria not used:** " + ", ".join(envelope.criteria_not_used), ""]
        if extra.get("conflicts"):
            lines += ["## Tensions to weigh", *[f"- {c}" for c in extra["conflicts"]], ""]
        lines += ["## Options for the decision"]
        deps = extra.get("option_cell_dependencies") or {}
        blocked = extra.get("blocked_options") or {}
        for opt in envelope.options:
            lines.append(f"### {opt.label} (`{opt.option_id}`)")
            lines.append(opt.implication)
            for t in opt.tradeoffs:
                lines.append(f"- Stays uncovered: {t}")
            if deps.get(opt.option_id):
                lines.append(f"- Depends on cells: {', '.join(deps[opt.option_id])}")
            if opt.option_id in blocked:
                lines.append(f"- **blocked_by_unknown:** {blocked[opt.option_id]}")
            lines.append("")
        if extra.get("unknowns"):
            lines += ["## Unknowns (left blank on purpose)", *[f"- {u}" for u in extra["unknowns"]], ""]
    if extra.get("limitations"):
        lines += ["## Limitations", *[f"- {x}" for x in extra["limitations"]], ""]
    lines += [
        "## Boundaries",
        "- This is a draft comparison. Nothing was hired, posted, or published, and no candidate is named.",
        "- Human approval accepts the draft; it does not open a requisition.",
    ]
    return "\n".join(lines).strip() + "\n"


def comparison_csv(envelope: ComparisonEnvelope | dict[str, Any]) -> str:
    """CSV of cells: criterion, subject, finding, basis, confidence."""
    env = (
        envelope
        if isinstance(envelope, ComparisonEnvelope)
        else ComparisonEnvelope.model_validate(envelope)
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["criterion", "subject", "finding", "basis", "confidence"])
    for cell in env.matrix:
        writer.writerow(
            [
                cell.criterion_label,
                cell.subject_label,
                cell.value,
                cell.basis,
                CONFIDENCE_BY_BASIS.get(cell.basis, ""),
            ]
        )
    return buf.getvalue()


# ------------------------------------------------------- prompt-size helpers


def compact_job_envelope(envelope: dict[str, Any] | None, *, description_chars: int = 200) -> dict[str, Any] | None:
    """Same schema as JobSearchEnvelope with shortened descriptions (for LLM prompts)."""
    if not envelope:
        return None
    out = dict(envelope)
    for key in ("jobs", "needs_review", "excluded"):
        rows = []
        for row in envelope.get(key) or []:
            r = dict(row)
            desc = str(r.get("job_description") or "")
            if len(desc) > description_chars:
                r["job_description"] = desc[:description_chars] + "…"
            rows.append(r)
        out[key] = rows
    out.pop("extra", None)
    return out


def compact_comparison_envelope(envelope: dict[str, Any] | None) -> dict[str, Any] | None:
    """Same schema as ComparisonEnvelope without per-cell evidence (for LLM prompts)."""
    if not envelope:
        return None
    out = dict(envelope)
    out["matrix"] = [{**c, "evidence": []} for c in envelope.get("matrix") or []]
    return out
