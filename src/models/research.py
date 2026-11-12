from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl, field_validator


class EvidenceType(str, Enum):
    primary = "primary"
    secondary = "secondary"
    model_synthesis = "model_synthesis"
    user_supplied = "user_supplied"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    unknown = "unknown"


class EvidenceItem(BaseModel):
    claim: str
    source_title: str = ""
    source_url: str | None = None
    source_domain: str = ""
    retrieved_at: datetime | str | None = None
    supporting_excerpt_or_summary: str = ""
    evidence_type: EvidenceType = EvidenceType.model_synthesis
    confidence: Confidence = Confidence.unknown

    @field_validator("source_url", mode="before")
    @classmethod
    def empty_url_to_none(cls, value: object) -> object:
        if value == "" or value is None:
            return None
        return value


class ResearchPacket(BaseModel):
    run_id: str
    research_question: str
    key_findings: list[str] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    research_limitations: list[str] = Field(default_factory=list)
    status: str = "completed"
    agent_summary: str = ""
