from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from src.models.coerce import as_str, as_str_list


class Deliverable(BaseModel):
    title: str = ""
    executive_summary: str = ""
    objective: str = ""
    key_findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    action_plan: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    markdown_content: str = ""
    status: str = "draft"

    @field_validator(
        "title",
        "executive_summary",
        "objective",
        "markdown_content",
        "status",
        mode="before",
    )
    @classmethod
    def coerce_simple_str(cls, value: object) -> object:
        return as_str(value)

    @field_validator(
        "key_findings",
        "recommendations",
        "action_plan",
        "resources",
        "assumptions",
        "unresolved_questions",
        "evidence_references",
        mode="before",
    )
    @classmethod
    def coerce_string_lists(cls, value: object) -> list[str]:
        return as_str_list(value)

    @model_validator(mode="after")
    def ensure_defaults(self) -> Deliverable:
        if not self.status:
            self.status = "draft"
        if not self.markdown_content.strip() and (self.title or self.executive_summary):
            parts = [f"# {self.title or 'Deliverable'}"]
            if self.executive_summary:
                parts.extend(["", "## Executive summary", self.executive_summary])
            if self.objective:
                parts.extend(["", "## Objective", self.objective])
            self.markdown_content = "\n".join(parts)
        return self
