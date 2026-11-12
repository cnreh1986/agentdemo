from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

from src.models.coerce import as_str, as_str_list


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
    claim: str = ""
    source_title: str = ""
    source_url: str | None = None
    source_domain: str = ""
    retrieved_at: datetime | str | None = None
    supporting_excerpt_or_summary: str = ""
    evidence_type: EvidenceType = EvidenceType.model_synthesis
    confidence: Confidence = Confidence.unknown

    @field_validator("claim", "source_title", "source_domain", "supporting_excerpt_or_summary", mode="before")
    @classmethod
    def coerce_str(cls, value: object) -> object:
        if value is None:
            return ""
        return str(value)

    @field_validator("source_url", mode="before")
    @classmethod
    def empty_or_invalid_url_to_none(cls, value: object) -> object:
        if value == "" or value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        parsed = urlparse(text)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        return text

    @field_validator("evidence_type", mode="before")
    @classmethod
    def soften_evidence_type(cls, value: object) -> object:
        if value is None or value == "":
            return EvidenceType.model_synthesis
        text = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "model": "model_synthesis",
            "synthesis": "model_synthesis",
            "llm": "model_synthesis",
            "user": "user_supplied",
            "supplied": "user_supplied",
        }
        text = aliases.get(text, text)
        try:
            return EvidenceType(text)
        except ValueError:
            return EvidenceType.model_synthesis

    @field_validator("confidence", mode="before")
    @classmethod
    def soften_confidence(cls, value: object) -> object:
        if value is None or value == "":
            return Confidence.unknown
        if isinstance(value, (int, float)):
            score = float(value)
            if score >= 0.75:
                return Confidence.high
            if score >= 0.4:
                return Confidence.medium
            if score > 0:
                return Confidence.low
            return Confidence.unknown
        text = str(value).strip().lower()
        try:
            return Confidence(text)
        except ValueError:
            return Confidence.unknown


class ResearchPacket(BaseModel):
    run_id: str = ""
    research_question: str = ""
    key_findings: list[str] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    research_limitations: list[str] = Field(default_factory=list)
    status: str = "completed"
    agent_summary: str = ""

    @field_validator(
        "key_findings",
        "assumptions",
        "uncertainties",
        "risks",
        "open_questions",
        "research_limitations",
        mode="before",
    )
    @classmethod
    def coerce_string_lists(cls, value: object) -> list[str]:
        return as_str_list(value)

    @field_validator("research_question", "agent_summary", "status", "run_id", mode="before")
    @classmethod
    def coerce_simple_str(cls, value: object) -> object:
        return as_str(value)

    @field_validator("evidence_items", mode="before")
    @classmethod
    def drop_invalid_evidence(cls, value: object) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            return []
        cleaned: list[Any] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, str):
                text = item.strip()
                if text:
                    cleaned.append({"claim": text})
                continue
            if isinstance(item, dict):
                try:
                    cleaned.append(EvidenceItem.model_validate(item).model_dump(mode="json"))
                except Exception:
                    # Keep a minimal claim if possible
                    claim = item.get("claim") or item.get("text") or item.get("finding")
                    if claim:
                        cleaned.append({"claim": str(claim)})
                continue
        return cleaned

    @model_validator(mode="after")
    def ensure_question(self) -> ResearchPacket:
        if not self.research_question.strip() and self.key_findings:
            self.research_question = "Research findings"
        if not self.status:
            self.status = "completed"
        return self
