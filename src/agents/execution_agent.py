from __future__ import annotations

from typing import Any

from src.agents.base import Agent
from src.models.deliverable import Deliverable
from src.models.agent import AgentResult
from src.models.competitive_analysis import ComparisonEnvelope
from src.models.job_search import JobSearchEnvelope
from src.models.task import TaskSpec
from src.services.job_intent import ground_job_envelope, scrub_ungrounded_refs, text_has_ungrounded_refs
from src.services.task_class_render import (
    compact_comparison_envelope,
    compact_job_envelope,
    job_summary_line,
    render_comparison_markdown,
    render_job_markdown,
)


class ExecutionAgent(Agent):
    name = "execution"
    schema_name = "deliverable"
    output_model = Deliverable

    def build_user_prompt(self, task: TaskSpec, context: dict[str, Any]) -> str:
        payload = {
            "run_id": task.run_id,
            "task": task.original_task,
            "objective": task.objective,
            "requested_output": task.requested_output,
            "research": context.get("research"),
            "plan": context.get("plan"),
            "revision_instructions": context.get("revision_instructions"),
            "prior_deliverable": context.get("prior_deliverable"),
        }
        if task.task_class != "briefing":
            payload["task_class"] = task.task_class
            payload["job_envelope"] = compact_job_envelope(context.get("job_envelope"))
            payload["comparison_envelope"] = compact_comparison_envelope(context.get("comparison_envelope"))
        return self.dumps(payload)

    def run(self, task: TaskSpec, context: dict[str, Any] | None = None) -> AgentResult:
        context = context or {}
        result = super().run(task, context)
        if result.status != "completed" or task.task_class == "briefing":
            return result
        if task.task_class == "job_search":
            return self._finish_job_search(result, context)
        return self._finish_comparison(result, context)

    def _finish_job_search(self, result: AgentResult, context: dict[str, Any]) -> AgentResult:
        raw = context.get("job_envelope")
        if not raw:
            return AgentResult(
                agent_name=self.name,
                status="failed",
                summary="Job envelope missing; execution cannot render job results.",
                issues=["No job envelope was handed off from research."],
                duration_ms=result.duration_ms,
            )
        envelope, dropped = ground_job_envelope(JobSearchEnvelope.model_validate(raw))
        ids = set(envelope.raw_tool_job_ids)
        urls = set((envelope.extra or {}).get("allowed_urls") or [])
        out = dict(result.output)
        # Drop model text that cites ids or URLs the tool never returned.
        for key in ("key_findings", "recommendations", "action_plan", "resources",
                    "assumptions", "unresolved_questions", "evidence_references"):
            out[key] = scrub_ungrounded_refs(list(out.get(key) or []), allowed_ids=ids, allowed_urls=urls)
        summary = str(out.get("executive_summary") or "")
        if not summary or text_has_ungrounded_refs(summary, allowed_ids=ids, allowed_urls=urls):
            summary = job_summary_line(envelope) + "."
        out["executive_summary"] = summary
        out["evidence_references"] = [j.job_id for j in envelope.jobs]
        out["markdown_content"] = render_job_markdown(
            envelope,
            title=out.get("title") or "Job search results",
            executive_summary=summary,
            recommendations=list(out.get("recommendations") or []),
        )
        result.output = out
        result.artifacts = {**result.artifacts, "job_envelope": envelope.model_dump(mode="json")}
        return result

    def _finish_comparison(self, result: AgentResult, context: dict[str, Any]) -> AgentResult:
        raw = context.get("comparison_envelope")
        if not raw:
            return AgentResult(
                agent_name=self.name,
                status="failed",
                summary="Comparison envelope missing; execution cannot render the matrix.",
                issues=["No comparison envelope was handed off from research."],
                duration_ms=result.duration_ms,
            )
        envelope = ComparisonEnvelope.model_validate(raw)
        out = dict(result.output)
        out["markdown_content"] = render_comparison_markdown(
            envelope,
            title=out.get("title") or "Comparison",
            executive_summary=str(out.get("executive_summary") or ""),
        )
        result.output = out
        result.artifacts = {**result.artifacts, "comparison_envelope": envelope.model_dump(mode="json")}
        return result

    def prepare_raw_output(self, raw: dict[str, Any], task: TaskSpec, context: dict[str, Any]) -> dict[str, Any]:
        data = dict(raw or {})
        if not str(data.get("objective") or "").strip():
            data["objective"] = task.objective or task.original_task
        if not str(data.get("title") or "").strip():
            data["title"] = f"{task.requested_output or 'Briefing'}: {task.objective or task.original_task}"
        if not str(data.get("executive_summary") or "").strip():
            data["executive_summary"] = (
                f"Draft deliverable for: {task.objective or task.original_task}"
            )
        return data

    def summarise(self, output: dict[str, Any]) -> str:
        return f"Deliverable ready: {output.get('title', 'untitled')}"
