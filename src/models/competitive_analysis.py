"""Typed competitive-analysis intent and comparison envelope."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ComparisonKind = Literal["role", "product"]
CellBasis = Literal["user_supplied", "public_source", "domain_default", "inference", "unknown"]
SubjectKind = Literal["role", "product"]


class ComparisonSubject(BaseModel):
    subject_id: str
    label: str
    kind: SubjectKind = "role"
    user_notes: str = ""


class ComparisonDecision(BaseModel):
    question: str = ""
    audience: str = ""
    time_horizon: str = ""
    constraints: list[str] = Field(default_factory=list)


class UserContextSlots(BaseModel):
    company_stage: str = ""
    business_model: str = ""
    location: str = ""
    product: str = ""
    customer: str = ""
    go_to_market: str = ""
    current_team: str = ""
    current_ownership: list[str] = Field(default_factory=list)


class CompetitiveAnalysisIntent(BaseModel):
    task_class: Literal["competitive_analysis"] = "competitive_analysis"
    comparison_kind: ComparisonKind = "role"
    subjects: list[ComparisonSubject] = Field(default_factory=list)
    decision: ComparisonDecision = Field(default_factory=ComparisonDecision)
    user_context: UserContextSlots = Field(default_factory=UserContextSlots)
    criteria_policy: str = "select rows that change the hiring decision; list unused catalog rows"
    scoring: str = "describe first; score only if the user asked for scores"
    status: Literal["ready", "needs_context"] = "ready"
    unblock_questions: list[str] = Field(default_factory=list)
    unparsed_remainder: str = ""
    original_task: str = ""


class ComparisonEvidenceItem(BaseModel):
    claim: str = ""
    source_url: str | None = None
    source_title: str | None = None
    basis: CellBasis = "unknown"


class ComparisonCell(BaseModel):
    criterion_id: str
    criterion_label: str
    subject_id: str
    subject_label: str
    value: str = ""
    basis: CellBasis = "unknown"
    evidence: list[ComparisonEvidenceItem] = Field(default_factory=list)
    score: float | None = None


class ComparisonOption(BaseModel):
    option_id: str
    label: str
    implication: str = ""
    tradeoffs: list[str] = Field(default_factory=list)


class ComparisonEnvelope(BaseModel):
    task_class: Literal["competitive_analysis"] = "competitive_analysis"
    comparison_kind: ComparisonKind = "role"
    status: Literal["ready", "needs_context"] = "ready"
    intent_echo: CompetitiveAnalysisIntent | None = None
    domain_frame_banner: str | None = None
    matrix: list[ComparisonCell] = Field(default_factory=list)
    criteria_not_used: list[str] = Field(default_factory=list)
    options: list[ComparisonOption] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    illustrative: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)
