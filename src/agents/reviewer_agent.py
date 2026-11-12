from __future__ import annotations

from typing import Any

from src.agents.base import Agent
from src.models.agent import AgentResult
from src.models.review import ReviewReport, ReviewStatus
from src.models.task import TaskSpec


class ReviewerAgent(Agent):
    name = "reviewer"
    schema_name = "review"
    output_model = ReviewReport

    def build_user_prompt(self, task: TaskSpec, context: dict[str, Any]) -> str:
        return self.dumps(
            {
                "run_id": task.run_id,
                "task": task.original_task,
                "success_criteria": task.success_criteria,
                "research": context.get("research"),
                "plan": context.get("plan"),
                "deliverable": context.get("deliverable"),
            }
        )

    def run(self, task: TaskSpec, context: dict[str, Any] | None = None) -> AgentResult:
        result = super().run(task, context)
        if result.status != "completed":
            return result
        report = ReviewReport.model_validate(result.output)
        if report.status == ReviewStatus.revision_required:
            result.status = "needs_revision"
        result.summary = report.reviewer_summary or result.summary
        return result

    def summarise(self, output: dict[str, Any]) -> str:
        return output.get("reviewer_summary") or f"Review status: {output.get('status')}"
