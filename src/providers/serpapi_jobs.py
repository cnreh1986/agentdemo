"""SerpAPI Google Jobs adapter (https://serpapi.com/search.json, engine=google_jobs).

Maps ``jobs_results`` into canonical ``JobRecord`` rows (source="serpapi"). Fields the
source does not return stay null. The adapter never scrapes Naukri/LinkedIn and never
fabricates ids, companies, descriptions, or URLs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from src.config.settings import Settings, get_settings
from src.models.job_search import JobRecord, JobSearchIntent
from src.services.job_intent import parse_posted_label, strip_html

SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"
SOURCE_NAME = "serpapi"

_COUNTRY_CODES = {
    "india": "IN",
    "pakistan": "PK",
    "united states": "US",
    "usa": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "singapore": "SG",
    "united arab emirates": "AE",
}


class JobsProviderError(RuntimeError):
    """Safe-to-display provider error (never contains the API key)."""


@dataclass
class JobsFetchResult:
    records: list[JobRecord] = field(default_factory=list)
    retrieved_at: str = ""
    error: str | None = None
    query: dict[str, Any] = field(default_factory=dict)


class SerpApiJobsProvider:
    source_name = SOURCE_NAME

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        *,
        max_pages: int = 2,
    ):
        self.settings = settings or get_settings()
        self._client = client
        self.max_pages = max(1, max_pages)

    def is_configured(self) -> bool:
        return bool(self.settings.serpapi_api_key)

    # ------------------------------------------------------------------ query
    def build_params(self, intent: JobSearchIntent) -> dict[str, Any]:
        """Query parameters derived from the typed intent (not the raw sentence)."""
        city = intent.location.city
        q = f"{intent.role_query} jobs" + (f" in {city}" if city else "")
        params: dict[str, Any] = {"engine": "google_jobs", "q": q, "hl": "en"}
        if city:
            parts = [city, intent.location.region, _country_name(intent.location.country_code)]
            params["location"] = ", ".join(p for p in parts if p)
        if intent.location.country_code:
            params["gl"] = intent.location.country_code.lower()
        days = intent.posted_within_days
        # Retrieval hint only; the include decision uses each job's own posted date.
        if days is not None:
            if days <= 1:
                params["chips"] = "date_posted:today"
            elif days <= 3:
                params["chips"] = "date_posted:3days"
            elif days <= 7:
                params["chips"] = "date_posted:week"
            elif days <= 31:
                params["chips"] = "date_posted:month"
        return params

    # ------------------------------------------------------------------ fetch
    def search(self, intent: JobSearchIntent) -> JobsFetchResult:
        if not self.is_configured():
            raise JobsProviderError("SERPAPI_API_KEY is not configured.")
        retrieved = datetime.now(timezone.utc)
        params = self.build_params(intent)
        result = JobsFetchResult(retrieved_at=retrieved.isoformat(), query=dict(params))
        token: str | None = None
        for _page in range(self.max_pages):
            page_params = dict(params)
            page_params["api_key"] = self.settings.serpapi_api_key
            if token:
                page_params["next_page_token"] = token
            data = self._get(page_params)
            result.records.extend(self.map_results(data, retrieved))
            token = ((data.get("serpapi_pagination") or {}).get("next_page_token")) or None
            if not token:
                break
        return result

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            if self._client is not None:
                response = self._client.get(SERPAPI_SEARCH_URL, params=params, timeout=30)
            else:
                with httpx.Client(timeout=30) as client:
                    response = client.get(SERPAPI_SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            # Do not echo the request URL: it contains the API key.
            raise JobsProviderError(f"SerpAPI request failed (HTTP {exc.response.status_code}).") from None
        except httpx.RequestError as exc:
            raise JobsProviderError(f"SerpAPI request failed ({type(exc).__name__}).") from None
        except ValueError:
            raise JobsProviderError("SerpAPI returned a non-JSON response.") from None
        if isinstance(data, dict) and data.get("error"):
            message = str(data["error"])
            # "Google hasn't returned any results for this query." is an empty set, not a failure.
            if "hasn't returned any results" in message or "no results" in message.lower():
                return {}
            raise JobsProviderError(f"SerpAPI error: {message[:160]}")
        return data if isinstance(data, dict) else {}

    # ---------------------------------------------------------------- mapping
    def map_results(self, data: dict[str, Any], retrieved_at: datetime | str) -> list[JobRecord]:
        retrieved = (
            retrieved_at
            if isinstance(retrieved_at, datetime)
            else datetime.fromisoformat(str(retrieved_at))
        )
        records: list[JobRecord] = []
        for item in data.get("jobs_results") or []:
            if not isinstance(item, dict):
                continue
            raw_id = str(item.get("job_id") or "").strip()
            title = str(item.get("title") or "").strip()
            if not raw_id or not title:
                continue  # no source identity -> not a record
            ext = item.get("detected_extensions") or {}
            location_text = str(item.get("location") or "").strip()
            description = strip_html(str(item.get("description") or ""))
            posted_label = (str(ext.get("posted_at")).strip() if ext.get("posted_at") else None)
            posted_dt = parse_posted_label(posted_label, retrieved)
            apply_url = _first_url(item)
            wfh = bool(ext.get("work_from_home"))
            highlights_text = _highlights_text(item.get("job_highlights"))
            records.append(
                JobRecord(
                    job_id=f"{SOURCE_NAME}:{raw_id}",
                    source=SOURCE_NAME,
                    source_job_id=raw_id,
                    title=title,
                    company_name=(str(item.get("company_name")).strip() or None) if item.get("company_name") else None,
                    job_description=description,
                    description_completeness=(
                        "truncated" if description.endswith(("...", "…")) else "full"
                    ),
                    location_text=location_text,
                    city=_city_from_location(location_text),
                    country_code=_country_from_location(location_text),
                    date_posted=posted_dt.isoformat() if posted_dt else None,
                    posted_label=posted_label,
                    experience_text=_experience_phrase(highlights_text),
                    employment_type=(str(ext.get("schedule_type")) if ext.get("schedule_type") else None),
                    workplace="remote" if wfh else "unknown",
                    apply_url=apply_url,
                    retrieved_at=retrieved.isoformat(),
                )
            )
        return records


def _country_name(code: str) -> str:
    for name, cc in _COUNTRY_CODES.items():
        if cc == (code or "").upper() and len(name) > 3:
            return name.title()
    return ""


def _city_from_location(location: str) -> str | None:
    first = (location or "").split(",")[0].strip()
    return first or None


def _country_from_location(location: str) -> str | None:
    last = (location or "").split(",")[-1].strip().lower()
    return _COUNTRY_CODES.get(last)


def _first_url(item: dict[str, Any]) -> str | None:
    for opt in item.get("apply_options") or []:
        link = (opt or {}).get("link") if isinstance(opt, dict) else None
        if link and str(link).startswith(("http://", "https://")):
            return str(link)
    share = item.get("share_link")
    if share and str(share).startswith(("http://", "https://")):
        return str(share)
    return None


def _highlights_text(highlights: Any) -> str:
    parts: list[str] = []
    for section in highlights or []:
        if isinstance(section, dict):
            parts.extend(str(x) for x in section.get("items") or [])
    return " ".join(parts)


def _experience_phrase(text: str) -> str | None:
    """Only return a phrase the source literally contains."""
    m = re.search(r"\d{1,2}\s*(?:-|–|—|to)\s*\d{1,2}\s*\+?\s*(?:years?|yrs?)|\d{1,2}\s*\+\s*(?:years?|yrs?)", text or "", re.I)
    return m.group(0) if m else None
