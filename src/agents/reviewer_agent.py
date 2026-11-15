from __future__ import annotations

from typing import Any

from src.agents.base import Agent
from src.models.agent import AgentResult
from src.models.review import ReviewReport, ReviewStatus
from src.models.task import TaskSpec
from src.services.task_class_render import compact_comparison_envelope, compact_job_envelope
from src.services.task_class_review import class_review_issues


class ReviewerAgent(Agent):
    name = "reviewer"
    schema_name = "review"
    output_model = ReviewReport

    def build_user_prompt(self, task: TaskSpec, context: dict[str, Any]) -> str:
        payload = {
            "run_id": task.run_id,
            "task": task.original_task,
            "success_criteria": task.success_criteria,
            "research": context.get("research"),
            "plan": context.get("plan"),
            "deliverable": context.get("deliverable"),
        }
        if task.task_class != "briefing":
            payload["task_class"] = task.task_class
            payload["job_envelope"] = compact_job_envelope(context.get("job_envelope"))
            payload["comparison_envelope"] = compact_comparison_envelope(context.get("comparison_envelope"))
        return self.dumps(payload)

    def _apply_class_checks(
        self, task: TaskSpec, context: dict[str, Any], output: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge deterministic job / comparison checks into the review (newehancement 10.5, 23.5)."""
        envelope = (
            context.get("job_envelope")
            if task.task_class == "job_search"
            else context.get("comparison_envelope")
        )
        intent = (
            context.get("job_intent")
            if task.task_class == "job_search"
            else context.get("comparison_intent")
        )
        issues = class_review_issues(
            task.task_class,
            envelope=envelope,
            intent=intent,
            deliverable=context.get("deliverable"),
        )
        out = dict(output)
        criteria = list(out.get("criteria_results") or [])
        if issues:
            criteria.append(
                {
                    "criterion": f"{task.task_class} envelope checks",
                    "passed": False,
                    "note": "; ".join(issues[:3]),
                }
            )
            out["criteria_results"] = criteria
            out["status"] = "revision_required"
            out["issues"] = list(out.get("issues") or []) + issues
            out["recommendations"] = list(out.get("recommendations") or []) + [
                "Fix the envelope or deliverable so every check passes; do not invent rows or cells."
            ]
            out["revision_targets"] = list(out.get("revision_targets") or []) or ["execution"]
            out["reviewer_summary"] = (
                f"Deterministic {task.task_class} checks failed: " + "; ".join(issues[:3])
            )
        else:
            criteria.append(
                {
                    "criterion": f"{task.task_class} envelope checks",
                    "passed": True,
                    "note": "Identity, grounding, filters, completeness, and safety checks passed.",
                }
            )
            out["criteria_results"] = criteria
        return out

    def run(self, task: TaskSpec, context: dict[str, Any] | None = None) -> AgentResult:
        context = context or {}
        result = super().run(task, context)
        if result.status != "completed":
            return result
        if task.task_class != "briefing":
            result.output = self._apply_class_checks(task, context, result.output)
        report = ReviewReport.model_validate(result.output)
        if report.status == ReviewStatus.revision_required:
            result.status = "needs_revision"
        result.summary = report.reviewer_summary or result.summary
        return result

    def summarise(self, output: dict[str, Any]) -> str:
        return output.get("reviewer_summary") or f"Review status: {output.get('status')}"
