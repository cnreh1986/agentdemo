from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    agent_name: str
    status: Literal["completed", "failed", "needs_revision"]
    summary: str
    output: dict[str, Any] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    # Typed side outputs (e.g. job_envelope) that the node stores beside the main output.
    artifacts: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int | None = None
