from __future__ import annotations

from pydantic import BaseModel, Field


class Deliverable(BaseModel):
    title: str
    executive_summary: str
    objective: str
    key_findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    action_plan: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    markdown_content: str = ""
    status: str = "draft"
