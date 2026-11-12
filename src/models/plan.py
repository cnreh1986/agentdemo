from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.models.coerce import as_action_list, as_dict_list, as_str, as_str_list, soften_priority


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

    @field_validator("action_id", "title", "description", "estimated_effort", "suggested_timing", "expected_outcome", "owner", mode="before")
    @classmethod
    def coerce_str(cls, value: object) -> object:
        if value is None:
            return ""
        return str(value)

    @field_validator("priority", mode="before")
    @classmethod
    def coerce_priority(cls, value: object) -> object:
        return soften_priority(value)

    @field_validator("dependency_ids", "evidence_refs", mode="before")
    @classmethod
    def coerce_id_lists(cls, value: object) -> list[str]:
        return as_str_list(value)


class Plan(BaseModel):
    objective: str = ""
    strategic_rationale: str = ""
    priorities: list[str] = Field(default_factory=list)
    actions: list[ActionItem] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    open_decisions: list[str] = Field(default_factory=list)

    @field_validator("objective", "strategic_rationale", mode="before")
    @classmethod
    def coerce_simple_str(cls, value: object) -> object:
        return as_str(value)

    @field_validator(
        "priorities",
        "dependencies",
        "risks",
        "assumptions",
        "success_metrics",
        "open_decisions",
        mode="before",
    )
    @classmethod
    def coerce_string_lists(cls, value: object) -> list[str]:
        return as_str_list(value)

    @field_validator("timeline", mode="before")
    @classmethod
    def coerce_timeline(cls, value: object) -> list[dict[str, Any]]:
        return as_dict_list(value)

    @field_validator("actions", mode="before")
    @classmethod
    def coerce_actions(cls, value: object) -> list[dict[str, Any]]:
        return as_action_list(value)

    @model_validator(mode="after")
    def ensure_defaults(self) -> Plan:
        if not self.objective.strip() and self.actions:
            self.objective = self.actions[0].title or "Plan"
        return self
