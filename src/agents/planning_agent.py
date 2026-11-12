from __future__ import annotations

from typing import Any

from src.agents.base import Agent
from src.models.plan import Plan
from src.models.task import TaskSpec


class PlanningAgent(Agent):
    name = "planning"
    schema_name = "plan"
    output_model = Plan

    def build_user_prompt(self, task: TaskSpec, context: dict[str, Any]) -> str:
        return self.dumps(
            {
                "run_id": task.run_id,
                "task": task.original_task,
                "objective": task.objective,
                "constraints": task.constraints,
                "time_horizon": task.time_horizon,
                "research": context.get("research"),
            }
        )

    def prepare_raw_output(self, raw: dict[str, Any], task: TaskSpec, context: dict[str, Any]) -> dict[str, Any]:
        data = dict(raw or {})
        if not str(data.get("objective") or "").strip():
            data["objective"] = task.objective or task.original_task
        return data

    def summarise(self, output: dict[str, Any]) -> str:
        n = len(output.get("actions") or [])
        return f"Created plan with {n} actions."
