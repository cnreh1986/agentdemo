from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    action_id: str
    title: str
    description: str
    priority: Literal["high", "medium", "low"] = "medium"
    estimated_effort: str = "unknown (estimate)"
    suggested_timing: str = "unspecified"
    dependency_ids: list[str] = Field(default_factory=list)
    expected_outcome: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    owner: str = "user"


class Plan(BaseModel):
    objective: str
    strategic_rationale: str = ""
    priorities: list[str] = Field(default_factory=list)
    actions: list[ActionItem] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    open_decisions: list[str] = Field(default_factory=list)
