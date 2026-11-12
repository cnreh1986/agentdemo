from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    agent_name: str
    status: Literal["completed", "failed", "needs_revision"]
    summary: str
    output: dict[str, Any] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    duration_ms: int | None = None
