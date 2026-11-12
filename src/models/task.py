from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TaskInput(BaseModel):
    task: str = Field(min_length=1)
    background: str = ""
    constraints: str = ""
    time_horizon: str = ""
    output_format: str = "Briefing"


class TaskSpec(BaseModel):
    run_id: str
    original_task: str
    objective: str
    background: str = ""
    constraints: str = ""
    time_horizon: str = "Not specified"
    requested_output: str = "Briefing"
    success_criteria: list[str] = Field(default_factory=list)
    created_at: datetime | str
    execution_mode: Literal["demo", "live"]
    model_configuration: dict[str, Any] = Field(default_factory=dict)
