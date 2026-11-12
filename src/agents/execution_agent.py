from __future__ import annotations

from typing import Any

from src.agents.base import Agent
from src.models.deliverable import Deliverable
from src.models.task import TaskSpec


class ExecutionAgent(Agent):
    name = "execution"
    schema_name = "deliverable"
    output_model = Deliverable

    def build_user_prompt(self, task: TaskSpec, context: dict[str, Any]) -> str:
        return self.dumps(
            {
                "run_id": task.run_id,
                "task": task.original_task,
                "objective": task.objective,
                "requested_output": task.requested_output,
                "research": context.get("research"),
                "plan": context.get("plan"),
                "revision_instructions": context.get("revision_instructions"),
                "prior_deliverable": context.get("prior_deliverable"),
            }
        )

    def summarise(self, output: dict[str, Any]) -> str:
        return f"Deliverable ready: {output.get('title', 'untitled')}"
