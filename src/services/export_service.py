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


def _add_bullet_section(doc: Document, heading: str, items: list[Any]) -> None:
    doc.add_heading(heading, level=1)
    if not items:
        doc.add_paragraph("None.")
        return
    for item in items:
        doc.add_paragraph(str(item), style="List Bullet")


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

    def research_docx(self, run_state: dict[str, Any]) -> tuple[str, bytes]:
        safe = sanitize_value(run_state)
        research = safe.get("research") or {}
        if not research:
            raise ValueError("No research packet available to export.")

        doc = Document()
        doc.add_heading("Research Packet", level=0)
        question = research.get("research_question") or "Research"
        doc.add_heading(str(question), level=1)
        if research.get("agent_summary"):
            doc.add_paragraph(str(research["agent_summary"]))
        doc.add_paragraph(f"Status: {research.get('status', 'unknown')}")
        doc.add_paragraph(f"Run ID: {safe.get('run_id', '')}")

        _add_bullet_section(doc, "Key findings", list(research.get("key_findings") or []))
        _add_bullet_section(doc, "Research limitations", list(research.get("research_limitations") or []))
        _add_bullet_section(doc, "Assumptions", list(research.get("assumptions") or []))
        _add_bullet_section(doc, "Uncertainties", list(research.get("uncertainties") or []))
        _add_bullet_section(doc, "Risks", list(research.get("risks") or []))
        _add_bullet_section(doc, "Open questions", list(research.get("open_questions") or []))

        doc.add_heading("Evidence items", level=1)
        evidence = list(research.get("evidence_items") or [])
        if not evidence:
            doc.add_paragraph("No source-backed evidence items.")
        else:
            for idx, item in enumerate(evidence, start=1):
                if not isinstance(item, dict):
                    doc.add_paragraph(str(item), style="List Bullet")
                    continue
                title = item.get("source_title") or item.get("source_domain") or f"Evidence {idx}"
                doc.add_heading(str(title), level=2)
                doc.add_paragraph(f"Claim: {item.get('claim', '')}")
                if item.get("source_url"):
                    doc.add_paragraph(f"URL: {item.get('source_url')}")
                if item.get("source_domain"):
                    doc.add_paragraph(f"Domain: {item.get('source_domain')}")
                doc.add_paragraph(
                    f"Type: {item.get('evidence_type', '')} · Confidence: {item.get('confidence', '')}"
                )
                if item.get("supporting_excerpt_or_summary"):
                    doc.add_paragraph(f"Excerpt: {item.get('supporting_excerpt_or_summary')}")

        buf = io.BytesIO()
        doc.save(buf)
        safe_id, ts = _stamp(safe)
        return f"research_{safe_id}_{ts}.docx", buf.getvalue()

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
                    docx_name, docx_bytes = self.research_docx(run_state)
                    zf.writestr(docx_name, docx_bytes)
                except ValueError:
                    pass
            if safe.get("plan"):
                zf.writestr("plan.json", json.dumps(safe["plan"], indent=2, default=str))
            if safe.get("review"):
                zf.writestr("review.json", json.dumps(safe["review"], indent=2, default=str))
            zf.writestr("events.json", json.dumps(safe.get("events") or [], indent=2, default=str))
        return f"workforce_export_{safe_id}_{ts}.zip", buf.getvalue()
