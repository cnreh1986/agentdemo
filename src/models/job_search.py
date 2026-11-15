"""Typed job-search intent, records, and result envelope."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ExperienceMatch = Literal["exact", "overlap", "unknown", "exclude"]
RoleMatch = Literal["in_family", "out_of_family"]
LocationMatch = Literal["city", "locality_alias", "mismatch", "unknown"]
RecencyMatch = Literal["within_window", "stale", "unknown"]
MatchStatus = Literal["included", "needs_review", "excluded"]
DescriptionCompleteness = Literal["full", "truncated"]


class JobLocationIntent(BaseModel):
    city: str = "Hyderabad"
    region: str = "Telangana"
    country_code: str = "IN"
    aliases: list[str] = Field(default_factory=list)
    radius_km: int = 40
    accept_remote: bool = False


class JobExperienceIntent(BaseModel):
    min_years: int | None = None
    max_years: int | None = None
    range_policy: Literal["overlap"] = "overlap"


class JobSearchIntent(BaseModel):
    task_class: Literal["job_search"] = "job_search"
    role_query: str = ""
    role_family: str = "product_management"
    title_include: list[str] = Field(default_factory=list)
    title_exclude: list[str] = Field(default_factory=list)
    location: JobLocationIntent = Field(default_factory=JobLocationIntent)
    experience: JobExperienceIntent = Field(default_factory=JobExperienceIntent)
    posted_within_days: int | None = 7
    employment_type: str | None = None
    workplace: str | None = None
    limit: int = 20
    open_filters: list[str] = Field(default_factory=list)
    unparsed_remainder: str = ""
    original_task: str = ""


class JobRecord(BaseModel):
    job_id: str
    source: str
    source_job_id: str
    title: str
    company_name: str | None = None
    job_description: str = ""
    description_completeness: DescriptionCompleteness = "truncated"
    location_text: str = ""
    city: str | None = None
    country_code: str | None = None
    date_posted: str | None = None
    posted_label: str | None = None
    experience_text: str | None = None
    experience_min: int | None = None
    experience_max: int | None = None
    experience_match: ExperienceMatch = "unknown"
    role_match: RoleMatch = "out_of_family"
    location_match: LocationMatch = "unknown"
    recency_match: RecencyMatch = "unknown"
    match_status: MatchStatus = "excluded"
    match_reasons: list[str] = Field(default_factory=list)
    employment_type: str | None = None
    workplace: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_is_predicted: bool = False
    apply_url: str | None = None
    retrieved_at: str = ""
    why_it_matched: str | None = None


class JobQueryEcho(BaseModel):
    role_family: str = ""
    role_query: str = ""
    city: str = ""
    country_code: str = "IN"
    radius_km: int = 40
    experience_min: int | None = None
    experience_max: int | None = None
    range_policy: str = "overlap"
    posted_within_days: int | None = None
    posted_after: str | None = None
    retrieved_at: str = ""
    source_name: str = ""
    open_filters: list[str] = Field(default_factory=list)


class JobSearchEnvelope(BaseModel):
    task_class: Literal["job_search"] = "job_search"
    query_echo: JobQueryEcho = Field(default_factory=JobQueryEcho)
    jobs: list[JobRecord] = Field(default_factory=list)
    needs_review: list[JobRecord] = Field(default_factory=list)
    excluded: list[JobRecord] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    coverage_notes: list[str] = Field(default_factory=list)
    sources_failed: list[str] = Field(default_factory=list)
    illustrative: bool = False
    raw_tool_job_ids: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)
