"""Export Markdown, JSON run bundle, ZIP, and Research Word."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

from docx import Document

from src.orchestration.events import sanitize_value


def _stamp(run_state: dict[str, Any]) -> tuple[str, str]:
    safe_id = (run_state.get("run_id") or "run").replace("-", "")[:8]
    raw = run_state.get("updated_at") or run_state.get("created_at") or datetime.now(timezone.utc).isoformat()
    ts = (
        str(raw)
        .replace(":", "")
        .replace("-", "")
        .replace(".", "")
        .replace("+", "")[:15]
    )
    return safe_id, ts


def _add_bullet_section(doc: Document, heading: str, items: list[Any], *, skip_if_empty: bool = False) -> None:
    cleaned = [str(item).strip() for item in (items or []) if str(item).strip()]
    if skip_if_empty and not cleaned:
        return
    doc.add_heading(heading, level=1)
    if not cleaned:
        doc.add_paragraph("None.")
        return
    for item in cleaned:
        doc.add_paragraph(item, style="List Bullet")


def _add_paragraph_section(doc: Document, heading: str, text: str | None, *, skip_if_empty: bool = True) -> None:
    body = (text or "").strip()
    if skip_if_empty and not body:
        return
    doc.add_heading(heading, level=1)
    if not body:
        doc.add_paragraph("None.")
        return
    for block in body.split("\n\n"):
        block = block.strip()
        if block:
            doc.add_paragraph(block)


def _render_markdown_body(doc: Document, markdown: str) -> None:
    """Lightweight markdown → Word (headings + paragraphs + bullets)."""
    text = (markdown or "").strip()
    if not text:
        doc.add_paragraph("None.")
        return
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            doc.add_heading(stripped[4:].strip(), level=3)
        elif stripped.startswith("## "):
            doc.add_heading(stripped[3:].strip(), level=2)
        elif stripped.startswith("# "):
            doc.add_heading(stripped[2:].strip(), level=1)
        elif stripped.startswith(("- ", "* ")):
            doc.add_paragraph(stripped[2:].strip(), style="List Bullet")
        elif len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in {".", ")"}:
            doc.add_paragraph(stripped, style="List Number")
        else:
            # Strip simple bold markers for readability
            cleaned = stripped.replace("**", "")
            doc.add_paragraph(cleaned)


def _merge_unique(*lists: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for items in lists:
        for item in items or []:
            text = str(item).strip()
            if text and text not in seen:
                seen.add(text)
                out.append(text)
    return out


def _job_row_paragraph(doc: Document, row: dict[str, Any], *, index: int) -> None:
    title = row.get("title") or f"Job {index}"
    company = row.get("company_name") or "(no company)"
    doc.add_heading(f"{index}. {title} — {company}", level=2)
    doc.add_paragraph(f"Job id: {row.get('job_id') or ''}")
    doc.add_paragraph(f"Location: {row.get('location_text') or row.get('city') or ''}")
    posted = row.get("date_posted") or row.get("posted_label") or ""
    if posted:
        doc.add_paragraph(f"Posted: {posted}")
    exp = row.get("experience_text") or ""
    if not exp and (row.get("experience_min") is not None or row.get("experience_max") is not None):
        exp = f"{row.get('experience_min')}-{row.get('experience_max')} years"
    if exp:
        doc.add_paragraph(f"Experience: {exp} ({row.get('experience_match') or ''})")
    doc.add_paragraph(
        f"Match: role={row.get('role_match')}, location={row.get('location_match')}, "
        f"recency={row.get('recency_match')}, status={row.get('match_status')}"
    )
    reasons = row.get("match_reasons") or []
    if reasons:
        doc.add_paragraph(f"Reasons: {', '.join(str(r) for r in reasons)}")
    desc = (row.get("job_description") or "").strip()
    if desc:
        excerpt = desc if len(desc) <= 400 else desc[:397] + "..."
        completeness = row.get("description_completeness") or ""
        label = f"Description ({completeness})" if completeness else "Description"
        doc.add_paragraph(f"{label}: {excerpt}")
    if row.get("apply_url"):
        doc.add_paragraph(f"Apply URL: {row.get('apply_url')}")
    if row.get("salary_is_predicted"):
        doc.add_paragraph("Salary note: source estimate (predicted), not an employer offer.")


def _append_job_envelope(doc: Document, envelope: dict[str, Any]) -> None:
    doc.add_heading("Job search results", level=0)
    if envelope.get("illustrative"):
        doc.add_paragraph(
            "Illustrative Demo Mode listings — not live openings. Fake ids; no network call."
        )
    echo = envelope.get("query_echo") or {}
    doc.add_heading("Query echo", level=1)
    doc.add_paragraph(
        f"Role: {echo.get('role_query') or ''} ({echo.get('role_family') or ''})"
    )
    doc.add_paragraph(
        f"Location: {echo.get('city') or ''} ({echo.get('country_code') or ''}), "
        f"radius {echo.get('radius_km') or ''} km"
    )
    doc.add_paragraph(
        f"Experience: {echo.get('experience_min')}–{echo.get('experience_max')} "
        f"({echo.get('range_policy') or 'overlap'})"
    )
    doc.add_paragraph(
        f"Posted within {echo.get('posted_within_days')} days "
        f"(after {echo.get('posted_after') or 'n/a'}); "
        f"retrieved {echo.get('retrieved_at') or ''}; source {echo.get('source_name') or ''}"
    )
    counts = envelope.get("counts") or {}
    doc.add_paragraph(
        f"Counts — included: {counts.get('included', 0)}, "
        f"needs review: {counts.get('needs_review', 0)}, "
        f"excluded: {counts.get('excluded', 0)}, "
        f"retrieved: {counts.get('retrieved', 0)}"
    )
    notes = list(envelope.get("coverage_notes") or [])
    if notes:
        _add_bullet_section(doc, "Coverage notes", notes)
    failed = list(envelope.get("sources_failed") or [])
    if failed:
        _add_bullet_section(doc, "Sources failed", failed)

    included = list(envelope.get("jobs") or [])
    doc.add_heading("Included jobs", level=1)
    if not included:
        doc.add_paragraph("None.")
    else:
        for i, row in enumerate(included, start=1):
            if isinstance(row, dict):
                _job_row_paragraph(doc, row, index=i)

    needs = list(envelope.get("needs_review") or [])
    doc.add_heading("Needs review", level=1)
    if not needs:
        doc.add_paragraph("None.")
    else:
        for i, row in enumerate(needs, start=1):
            if isinstance(row, dict):
                _job_row_paragraph(doc, row, index=i)

    excluded = list(envelope.get("excluded") or [])
    doc.add_heading("Excluded", level=1)
    if not excluded:
        doc.add_paragraph("None.")
    else:
        for i, row in enumerate(excluded, start=1):
            if isinstance(row, dict):
                _job_row_paragraph(doc, row, index=i)


def _append_comparison_envelope(doc: Document, envelope: dict[str, Any]) -> None:
    doc.add_heading("Competitive analysis", level=0)
    if envelope.get("illustrative"):
        doc.add_paragraph("Illustrative Demo Mode comparison — not a live company audit.")
    if envelope.get("domain_frame_banner"):
        doc.add_paragraph(str(envelope["domain_frame_banner"]))
    doc.add_paragraph(f"Status: {envelope.get('status') or ''} · Kind: {envelope.get('comparison_kind') or ''}")
    intent = envelope.get("intent_echo") or {}
    if intent:
        doc.add_heading("Context echo", level=1)
        subjects = intent.get("subjects") or []
        if subjects:
            labels = ", ".join(
                str(s.get("label") or s.get("subject_id") or "") for s in subjects if isinstance(s, dict)
            )
            doc.add_paragraph(f"Subjects: {labels}")
        decision = intent.get("decision") or {}
        if isinstance(decision, dict) and decision.get("question"):
            doc.add_paragraph(f"Decision: {decision.get('question')}")
        ctx = intent.get("user_context") or {}
        if isinstance(ctx, dict):
            for key in (
                "company_stage",
                "business_model",
                "location",
                "product",
                "customer",
                "go_to_market",
                "current_team",
            ):
                if ctx.get(key):
                    doc.add_paragraph(f"{key}: {ctx.get(key)}")
    matrix = list(envelope.get("matrix") or [])
    doc.add_heading("Matrix", level=1)
    if not matrix:
        doc.add_paragraph("Empty contextual matrix.")
    else:
        for cell in matrix:
            if not isinstance(cell, dict):
                continue
            doc.add_paragraph(
                f"{cell.get('criterion_label') or cell.get('criterion_id')} · "
                f"{cell.get('subject_label') or cell.get('subject_id')} "
                f"[{cell.get('basis') or 'unknown'}]: {cell.get('value') or '(blank)'}",
                style="List Bullet",
            )
    unused = list(envelope.get("criteria_not_used") or [])
    if unused:
        _add_bullet_section(doc, "Criteria not used", unused)
    options = list(envelope.get("options") or [])
    if options:
        doc.add_heading("Options", level=1)
        for opt in options:
            if not isinstance(opt, dict):
                continue
            doc.add_paragraph(
                f"{opt.get('label') or opt.get('option_id')}: {opt.get('implication') or ''}",
                style="List Bullet",
            )
    questions = list(envelope.get("open_questions") or [])
    if questions:
        _add_bullet_section(doc, "Open questions", questions)


class ExportService:
    def markdown_briefing(self, run_state: dict[str, Any]) -> tuple[str, str]:
        safe = sanitize_value(run_state)
        deliverable = safe.get("deliverable") or {}
        content = deliverable.get("markdown_content") or deliverable.get("executive_summary") or ""
        safe_id, ts = _stamp(safe)
        return f"briefing_{safe_id}_{ts}.md", content

    def json_bundle(self, run_state: dict[str, Any]) -> tuple[str, str]:
        safe = sanitize_value(run_state)
        bundle = {
            "run_id": safe.get("run_id"),
            "mode": safe.get("mode"),
            "status": safe.get("status"),
            "task_input": safe.get("task_input"),
            "task_specification": safe.get("task_specification"),
            "job_intent": safe.get("job_intent"),
            "job_envelope": safe.get("job_envelope"),
            "comparison_intent": safe.get("comparison_intent"),
            "comparison_envelope": safe.get("comparison_envelope"),
            "research": safe.get("research"),
            "plan": safe.get("plan"),
            "deliverable": safe.get("deliverable"),
            "review": safe.get("review"),
            "events": safe.get("events"),
            "revision_count": safe.get("revision_count"),
            "approval_status": safe.get("approval_status"),
            "approval_note": safe.get("approval_note"),
            "approval_at": safe.get("approval_at"),
            "model_configuration": safe.get("model_configuration"),
        }
        safe_id, ts = _stamp(safe)
        return f"run_bundle_{safe_id}_{ts}.json", json.dumps(bundle, indent=2, default=str)

    def jobs_csv(self, run_state: dict[str, Any]) -> tuple[str, str]:
        """CSV of included jobs (job id, title, company, city, date posted, experience, apply URL)."""
        from src.services.task_class_render import jobs_csv

        safe = sanitize_value(run_state)
        envelope = safe.get("job_envelope")
        if not envelope:
            raise ValueError("No job envelope available to export.")
        safe_id, ts = _stamp(safe)
        return f"jobs_{safe_id}_{ts}.csv", jobs_csv(envelope)

    def comparison_csv(self, run_state: dict[str, Any]) -> tuple[str, str]:
        """CSV of matrix cells (criterion, subject, finding, basis, confidence)."""
        from src.services.task_class_render import comparison_csv

        safe = sanitize_value(run_state)
        envelope = safe.get("comparison_envelope")
        if not envelope:
            raise ValueError("No comparison envelope available to export.")
        safe_id, ts = _stamp(safe)
        return f"comparison_{safe_id}_{ts}.csv", comparison_csv(envelope)

    def research_docx(self, run_state: dict[str, Any]) -> tuple[str, bytes]:
        """Build a PRD-style Word report for the whole run (alias: run_docx)."""
        return self.run_docx(run_state)

    def run_docx(self, run_state: dict[str, Any]) -> tuple[str, bytes]:
        safe = sanitize_value(run_state)
        research = safe.get("research") or {}
        deliverable = safe.get("deliverable") or {}
        plan = safe.get("plan") or {}
        review = safe.get("review") or {}
        task_spec = safe.get("task_specification") or {}
        task_input = safe.get("task_input") or {}
        job_envelope = safe.get("job_envelope")
        comparison_envelope = safe.get("comparison_envelope")
        events = list(safe.get("events") or [])

        if not any([research, deliverable, plan, job_envelope, comparison_envelope]):
            raise ValueError("No run content available to export as a Word report.")

        title = (
            (deliverable.get("title") or "").strip()
            or (task_spec.get("objective") or "").strip()
            or (task_input.get("task") or "").strip()
            or "Workforce Studio run report"
        )
        task_class = (
            (task_spec.get("task_class") or "")
            or ("job_search" if job_envelope else "")
            or ("competitive_analysis" if comparison_envelope else "briefing")
        )

        doc = Document()
        doc.add_heading(title, level=0)

        # Document meta
        doc.add_heading("Document information", level=1)
        doc.add_paragraph(f"Run ID: {safe.get('run_id') or ''}")
        doc.add_paragraph(f"Mode: {safe.get('mode') or ''}")
        doc.add_paragraph(f"Task class: {task_class}")
        doc.add_paragraph(f"Run status: {safe.get('status') or ''}")
        approval = safe.get("approval_status") or "not decided"
        doc.add_paragraph(f"Human approval: {approval}")
        if safe.get("approval_note"):
            doc.add_paragraph(f"Approval note: {safe.get('approval_note')}")
        if safe.get("approval_at"):
            doc.add_paragraph(f"Approved at: {safe.get('approval_at')}")
        if safe.get("demo_disclaimer"):
            doc.add_paragraph(str(safe["demo_disclaimer"]))
        model_cfg = safe.get("model_configuration") or {}
        if model_cfg:
            doc.add_paragraph(
                f"Model: {model_cfg.get('provider') or ''} / {model_cfg.get('model') or ''}"
            )

        # Executive Summary
        exec_summary = (deliverable.get("executive_summary") or "").strip()
        if not exec_summary and research.get("agent_summary"):
            exec_summary = str(research.get("agent_summary") or "").strip()
        _add_paragraph_section(doc, "Executive Summary", exec_summary, skip_if_empty=False)

        # Objective
        objective = (
            (deliverable.get("objective") or "").strip()
            or (task_spec.get("objective") or "").strip()
            or (task_input.get("task") or "").strip()
        )
        doc.add_heading("Objective", level=1)
        doc.add_paragraph(objective or "None.")
        background = (task_spec.get("background") or task_input.get("background") or "").strip()
        constraints = (task_spec.get("constraints") or task_input.get("constraints") or "").strip()
        horizon = (task_spec.get("time_horizon") or task_input.get("time_horizon") or "").strip()
        if background:
            doc.add_paragraph(f"Background: {background}")
        if constraints:
            doc.add_paragraph(f"Constraints: {constraints}")
        if horizon:
            doc.add_paragraph(f"Time horizon: {horizon}")
        criteria = list(task_spec.get("success_criteria") or [])
        if criteria:
            doc.add_paragraph("Success criteria:")
            for c in criteria:
                doc.add_paragraph(str(c), style="List Bullet")

        # Key Findings — deliverable first, then research
        findings = _merge_unique(
            list(deliverable.get("key_findings") or []),
            list(research.get("key_findings") or []),
        )
        _add_bullet_section(doc, "Key Findings", findings, skip_if_empty=False)

        # Recommendations
        recommendations = _merge_unique(list(deliverable.get("recommendations") or []))
        _add_bullet_section(doc, "Recommendations", recommendations, skip_if_empty=False)

        # Action Plan — deliverable.action_plan strings + plan.actions
        doc.add_heading("Action Plan", level=1)
        action_lines = [str(a).strip() for a in (deliverable.get("action_plan") or []) if str(a).strip()]
        plan_actions = list(plan.get("actions") or [])
        if plan.get("strategic_rationale"):
            doc.add_paragraph(str(plan["strategic_rationale"]))
        priorities = list(plan.get("priorities") or [])
        if priorities:
            doc.add_paragraph("Priorities:")
            for p in priorities:
                doc.add_paragraph(str(p), style="List Bullet")
        if action_lines:
            for line in action_lines:
                doc.add_paragraph(line, style="List Bullet")
        if plan_actions:
            for action in plan_actions:
                if not isinstance(action, dict):
                    doc.add_paragraph(str(action), style="List Bullet")
                    continue
                label = action.get("title") or action.get("action_id") or "Action"
                detail = action.get("description") or ""
                meta = " · ".join(
                    filter(
                        None,
                        [
                            f"priority: {action.get('priority')}" if action.get("priority") else "",
                            f"effort: {action.get('estimated_effort')}" if action.get("estimated_effort") else "",
                            f"timing: {action.get('suggested_timing')}" if action.get("suggested_timing") else "",
                            f"owner: {action.get('owner')}" if action.get("owner") else "",
                        ],
                    )
                )
                doc.add_paragraph(f"{label}: {detail}".strip(), style="List Bullet")
                if meta:
                    doc.add_paragraph(meta)
                if action.get("expected_outcome"):
                    doc.add_paragraph(f"Expected outcome: {action.get('expected_outcome')}")
        timeline = list(plan.get("timeline") or [])
        if timeline:
            doc.add_paragraph("Timeline:")
            for row in timeline:
                if isinstance(row, dict):
                    doc.add_paragraph(
                        f"{row.get('day') or ''}: {row.get('focus') or ''}".strip(": "),
                        style="List Bullet",
                    )
                else:
                    doc.add_paragraph(str(row), style="List Bullet")
        if not action_lines and not plan_actions and not priorities and not timeline:
            doc.add_paragraph("None.")

        # Resources (deliverable) + Evidence References (research)
        resources = _merge_unique(list(deliverable.get("resources") or []))
        _add_bullet_section(doc, "Resources", resources, skip_if_empty=True)

        evidence = list(research.get("evidence_items") or [])
        evidence_refs = list(deliverable.get("evidence_references") or [])
        doc.add_heading("Evidence References", level=1)
        wrote_evidence = False
        for idx, item in enumerate(evidence, start=1):
            wrote_evidence = True
            if not isinstance(item, dict):
                doc.add_paragraph(str(item), style="List Bullet")
                continue
            claim = item.get("claim") or ""
            source = item.get("source_title") or item.get("source_domain") or f"Source {idx}"
            url = item.get("source_url")
            line = f"{claim} (Source: {source})" if claim else str(source)
            if url:
                line = f"{line} — {url}"
            doc.add_paragraph(line, style="List Bullet")
            if item.get("supporting_excerpt_or_summary"):
                doc.add_paragraph(f"Excerpt: {item.get('supporting_excerpt_or_summary')}")
        for ref in evidence_refs:
            wrote_evidence = True
            doc.add_paragraph(str(ref), style="List Bullet")
        if not wrote_evidence:
            doc.add_paragraph("None.")

        # Assumptions
        assumptions = _merge_unique(
            list(deliverable.get("assumptions") or []),
            list(research.get("assumptions") or []),
            list(plan.get("assumptions") or []),
        )
        _add_bullet_section(doc, "Assumptions", assumptions, skip_if_empty=False)

        # Unresolved Questions
        unresolved = _merge_unique(
            list(deliverable.get("unresolved_questions") or []),
            list(research.get("open_questions") or []),
            list(plan.get("open_decisions") or []),
            list(review.get("missing_information") or []),
            list(safe.get("unresolved_issues") or []),
        )
        _add_bullet_section(doc, "Unresolved Questions", unresolved, skip_if_empty=False)

        # Risks / Limitations
        risks = _merge_unique(
            list(research.get("risks") or []),
            list(plan.get("risks") or []),
        )
        _add_bullet_section(doc, "Risks", risks, skip_if_empty=True)
        _add_bullet_section(
            doc,
            "Research Limitations",
            list(research.get("research_limitations") or []),
            skip_if_empty=True,
        )
        _add_bullet_section(
            doc,
            "Uncertainties",
            list(research.get("uncertainties") or []),
            skip_if_empty=True,
        )

        # Deliverable body (full markdown)
        doc.add_heading("Deliverable", level=1)
        md = (deliverable.get("markdown_content") or "").strip()
        if md:
            _render_markdown_body(doc, md)
        elif exec_summary or recommendations:
            doc.add_paragraph(
                "See Executive Summary and Recommendations above "
                "(no separate markdown_content on this run)."
            )
        else:
            doc.add_paragraph("None.")

        # Reviewer notes
        if review:
            doc.add_heading("Reviewer notes", level=1)
            doc.add_paragraph(f"Review status: {review.get('status') or ''}")
            if review.get("quality_score") is not None:
                doc.add_paragraph(f"Quality score: {review.get('quality_score')}")
            if review.get("summary"):
                doc.add_paragraph(str(review.get("summary")))
            criteria_results = list(review.get("criteria_results") or [])
            if criteria_results:
                doc.add_paragraph("Criteria:")
                for row in criteria_results:
                    if not isinstance(row, dict):
                        doc.add_paragraph(str(row), style="List Bullet")
                        continue
                    passed = "pass" if row.get("passed") else "fail"
                    note = row.get("note") or ""
                    doc.add_paragraph(
                        f"{row.get('criterion') or ''}: {passed}" + (f" — {note}" if note else ""),
                        style="List Bullet",
                    )
            _add_bullet_section(doc, "Issues", list(review.get("issues") or []), skip_if_empty=True)
            if review.get("revision_instructions"):
                doc.add_paragraph(f"Revision instructions: {review.get('revision_instructions')}")

        # Activity log
        doc.add_heading("Activity log", level=1)
        if not events:
            doc.add_paragraph("None.")
        else:
            for ev in events:
                if not isinstance(ev, dict):
                    doc.add_paragraph(str(ev), style="List Bullet")
                    continue
                stage = ev.get("stage") or ""
                etype = ev.get("event_type") or ev.get("type") or ""
                message = ev.get("message") or ""
                status = ev.get("status") or ""
                stamp = ev.get("timestamp") or ev.get("created_at") or ""
                parts = [p for p in (stage, etype, status, message) if p]
                line = " — ".join(parts)
                if stamp:
                    line = f"[{stamp}] {line}"
                doc.add_paragraph(line, style="List Bullet")

        # Task-class appendices
        if isinstance(job_envelope, dict) and job_envelope:
            _append_job_envelope(doc, job_envelope)
        if isinstance(comparison_envelope, dict) and comparison_envelope:
            _append_comparison_envelope(doc, comparison_envelope)

        buf = io.BytesIO()
        doc.save(buf)
        safe_id, ts = _stamp(safe)
        if job_envelope:
            prefix = "jobs"
        elif comparison_envelope:
            prefix = "comparison"
        else:
            prefix = "prd"
        return f"{prefix}_{safe_id}_{ts}.docx", buf.getvalue()

    def zip_bundle(self, run_state: dict[str, Any]) -> tuple[str, bytes]:
        md_name, md = self.markdown_briefing(run_state)
        json_name, js = self.json_bundle(run_state)
        safe = sanitize_value(run_state)
        safe_id, ts = _stamp(safe)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(md_name, md)
            zf.writestr(json_name, js)
            if safe.get("research"):
                zf.writestr("research.json", json.dumps(safe["research"], indent=2, default=str))
            try:
                docx_name, docx_bytes = self.run_docx(run_state)
                zf.writestr(docx_name, docx_bytes)
            except ValueError:
                pass
            if safe.get("job_envelope"):
                zf.writestr("job_envelope.json", json.dumps(safe["job_envelope"], indent=2, default=str))
                csv_name, csv_text = self.jobs_csv(run_state)
                zf.writestr(csv_name, csv_text)
            if safe.get("comparison_envelope"):
                zf.writestr(
                    "comparison_envelope.json", json.dumps(safe["comparison_envelope"], indent=2, default=str)
                )
                csv_name, csv_text = self.comparison_csv(run_state)
                zf.writestr(csv_name, csv_text)
            if safe.get("plan"):
                zf.writestr("plan.json", json.dumps(safe["plan"], indent=2, default=str))
            if safe.get("review"):
                zf.writestr("review.json", json.dumps(safe["review"], indent=2, default=str))
            zf.writestr("events.json", json.dumps(safe.get("events") or [], indent=2, default=str))
        return f"workforce_export_{safe_id}_{ts}.zip", buf.getvalue()
