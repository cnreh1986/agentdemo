from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    approved = "approved"
    revision_required = "revision_required"
    rejected = "rejected"
    unable_to_review = "unable_to_review"


class CriterionResult(BaseModel):
    criterion: str
    passed: bool
    note: str = ""


class ReviewReport(BaseModel):
    status: ReviewStatus
    quality_score: int = Field(ge=0, le=100)
    criteria_results: list[CriterionResult] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    revision_targets: list[str] = Field(default_factory=list)
    reviewer_summary: str = ""
