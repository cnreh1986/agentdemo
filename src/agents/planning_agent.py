from __future__ import annotations

from typing import Any

from src.agents.base import Agent
from src.models.plan import Plan
from src.models.task import TaskSpec
from src.services.task_class_render import compact_comparison_envelope, compact_job_envelope


class PlanningAgent(Agent):
    name = "planning"
    schema_name = "plan"
    output_model = Plan

    def build_user_prompt(self, task: TaskSpec, context: dict[str, Any]) -> str:
        payload = {
            "run_id": task.run_id,
            "task": task.original_task,
            "objective": task.objective,
            "constraints": task.constraints,
            "time_horizon": task.time_horizon,
            "research": context.get("research"),
        }
        if task.task_class != "briefing":
            payload["task_class"] = task.task_class
            payload["job_envelope"] = compact_job_envelope(context.get("job_envelope"))
            payload["comparison_envelope"] = compact_comparison_envelope(context.get("comparison_envelope"))
        return self.dumps(payload)

    def run(self, task: TaskSpec, context: dict[str, Any] | None = None):
        result = super().run(task, context)
        if result.status == "completed" and task.task_class != "briefing":
            # Plans for these task classes never assign work to the workforce: owner is the user.
            output = dict(result.output)
            output["actions"] = [{**a, "owner": "user"} for a in output.get("actions") or []]
            result.output = output
        return result

    def prepare_raw_output(self, raw: dict[str, Any], task: TaskSpec, context: dict[str, Any]) -> dict[str, Any]:
        data = dict(raw or {})
        if not str(data.get("objective") or "").strip():
            data["objective"] = task.objective or task.original_task
        return data

    def summarise(self, output: dict[str, Any]) -> str:
        n = len(output.get("actions") or [])
        return f"Created plan with {n} actions."
