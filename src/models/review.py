from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from src.models.coerce import as_str, as_str_list, soften_quality_score


class ReviewStatus(str, Enum):
    approved = "approved"
    revision_required = "revision_required"
    rejected = "rejected"
    unable_to_review = "unable_to_review"


class CriterionResult(BaseModel):
    criterion: str = ""
    passed: bool = False
    note: str = ""

    @field_validator("criterion", "note", mode="before")
    @classmethod
    def coerce_str(cls, value: object) -> object:
        return as_str(value)

    @field_validator("passed", mode="before")
    @classmethod
    def coerce_passed(cls, value: object) -> object:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in {"true", "yes", "y", "pass", "passed", "ok", "1"}:
            return True
        if text in {"false", "no", "n", "fail", "failed", "0"}:
            return False
        return False


class ReviewReport(BaseModel):
    status: ReviewStatus = ReviewStatus.unable_to_review
    quality_score: int = Field(default=50, ge=0, le=100)
    criteria_results: list[CriterionResult] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    revision_targets: list[str] = Field(default_factory=list)
    reviewer_summary: str = ""

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, value: object) -> object:
        if value is None or value == "":
            return ReviewStatus.unable_to_review
        if isinstance(value, ReviewStatus):
            return value
        text = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "approve": "approved",
            "ok": "approved",
            "pass": "approved",
            "passed": "approved",
            "revise": "revision_required",
            "needs_revision": "revision_required",
            "revision": "revision_required",
            "request_revision": "revision_required",
            "reject": "rejected",
            "unable": "unable_to_review",
            "unknown": "unable_to_review",
        }
        text = aliases.get(text, text)
        try:
            return ReviewStatus(text)
        except ValueError:
            return ReviewStatus.unable_to_review

    @field_validator("quality_score", mode="before")
    @classmethod
    def coerce_score(cls, value: object) -> object:
        return soften_quality_score(value)

    @field_validator(
        "issues",
        "missing_information",
        "unsupported_claims",
        "recommendations",
        "revision_targets",
        mode="before",
    )
    @classmethod
    def coerce_string_lists(cls, value: object) -> list[str]:
        return as_str_list(value)

    @field_validator("reviewer_summary", mode="before")
    @classmethod
    def coerce_summary(cls, value: object) -> object:
        return as_str(value)

    @field_validator("criteria_results", mode="before")
    @classmethod
    def coerce_criteria(cls, value: object) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, dict):
            value = [value]
        if isinstance(value, str):
            text = value.strip()
            return [{"criterion": text, "passed": False}] if text else []
        if not isinstance(value, list):
            return []
        cleaned: list[Any] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, str):
                text = item.strip()
                if text:
                    cleaned.append({"criterion": text, "passed": False})
                continue
            if isinstance(item, dict):
                d = dict(item)
                if not d.get("criterion"):
                    d["criterion"] = str(d.get("name") or d.get("check") or "criterion")
                cleaned.append(d)
        return cleaned

    @model_validator(mode="after")
    def ensure_summary(self) -> ReviewReport:
        if not self.reviewer_summary.strip():
            self.reviewer_summary = f"Review status: {self.status.value}"
        return self
