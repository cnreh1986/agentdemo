"""Job-search task classification, intent parsing, and deterministic filters.

Implements newehancement.md sections 5-7 and 9: the model never decides which rows are
included. Code parses the sentence into a ``JobSearchIntent`` and applies role, place,
recency, and experience rules to source-supplied ``JobRecord`` rows.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from src.models.job_search import (
    JobExperienceIntent,
    JobLocationIntent,
    JobQueryEcho,
    JobRecord,
    JobSearchEnvelope,
    JobSearchIntent,
)

# --------------------------------------------------------------------------- #
# Lexicons (newehancement.md sections 5, 6, 7)
# --------------------------------------------------------------------------- #

PM_TITLE_INCLUDE = [
    "product manager",
    "senior product manager",
    "lead product manager",
    "group product manager",
    "principal product manager",
    "product owner",
    "technical product manager",
]

# Section 5 list plus section 6.2 lookalikes that are out of family.
PM_TITLE_EXCLUDE = [
    "project manager",
    "program manager",
    "product marketing",
    "product designer",
    "production manager",
    "product support",
    "product analyst",
    "category manager",
    "brand manager",
    "engineering manager",
]

# Exclusions that do not apply when the title also says "product manager" (section 6.2:
# "Product Support, Product Analyst ... unless the title also says Product Manager").
_SOFT_EXCLUDES = {"product support", "product analyst"}

# Extra accepted spellings for the PM family (section 6.1), matched on whole tokens.
_PM_INCLUDE_PATTERNS = [
    r"\bproduct\s+manager\b",
    r"\bproduct\s+mgr\b",
    r"\bproduct\s+owner\b",
    r"\bproduct\s+lead\b",
    r"\bgpm\b",
    r"\bsr\.?\s+pm\b",
    r"\bpm\b",
    r"\bpo\b",
]

HYDERABAD_ALIASES = [
    "hyderabad",
    "hyd",
    "cyberabad",
    "hitec city",
    "gachibowli",
    "madhapur",
    "kondapur",
    "financial district",
    "nanakramguda",
    "secunderabad",
    "secbad",
]

# city -> (region, country_code, aliases)
CITY_TABLE: dict[str, tuple[str, str, list[str]]] = {
    "hyderabad": ("Telangana", "IN", HYDERABAD_ALIASES),
    "bengaluru": ("Karnataka", "IN", ["bengaluru", "bangalore", "blr", "whitefield", "koramangala"]),
    "pune": ("Maharashtra", "IN", ["pune", "hinjewadi", "kharadi"]),
    "mumbai": ("Maharashtra", "IN", ["mumbai", "bombay", "navi mumbai", "thane"]),
    "chennai": ("Tamil Nadu", "IN", ["chennai", "madras"]),
    "delhi": ("Delhi", "IN", ["delhi", "new delhi", "ncr"]),
    "gurgaon": ("Haryana", "IN", ["gurgaon", "gurugram"]),
    "noida": ("Uttar Pradesh", "IN", ["noida"]),
    "kolkata": ("West Bengal", "IN", ["kolkata", "calcutta"]),
}
_CITY_NAME_ALIASES = {"bangalore": "bengaluru", "gurugram": "gurgaon", "new delhi": "delhi", "bombay": "mumbai"}

_NON_IN_MARKERS = {
    "sindh": ("Sindh", "PK"),
    "pakistan": ("Sindh", "PK"),
}

INDUSTRY_TERMS = [
    "fintech",
    "payments",
    "b2b saas",
    "b2c",
    "saas",
    "healthtech",
    "edtech",
    "e-commerce",
    "ecommerce",
    "ai/ml",
    "logistics",
    "insurtech",
    "gaming",
]

_JOB_NOUNS = r"(?:jobs?|openings?|vacanc(?:y|ies)|job\s+listings?|job\s+postings?|positions?\s+(?:in|at|for))"
_JOB_SEARCH_RE = re.compile(rf"\b{_JOB_NOUNS}\b", re.I)
_JOB_ASK_RE = re.compile(r"\b(find|search|show|list|look(?:ing)?\s+for|get|fetch|create\s+a\s+task)\b", re.I)
_COMPARE_RE = re.compile(r"\b(compare|versus|vs\.?|difference\s+between)\b", re.I)


# --------------------------------------------------------------------------- #
# Task classification
# --------------------------------------------------------------------------- #


def classify_task_class(task: str, background: str = "", constraints: str = "") -> str:
    """Return ``competitive_analysis``, ``job_search`` or ``briefing``.

    Comparison wins only when the user asked to compare and two subjects were parsed
    (newehancement.md 23.1). A Hyderabad job search stays ``job_search``.
    """
    text = (task or "").strip()
    if not text:
        return "briefing"
    if _COMPARE_RE.search(text):
        from src.services.comparison_intent import split_comparison_subjects

        if len(split_comparison_subjects(text)) >= 2:
            return "competitive_analysis"
    combined = " ".join(part for part in (text, background or "") if part)
    if _JOB_SEARCH_RE.search(text) and (_JOB_ASK_RE.search(text) or _has_job_filters(text)):
        return "job_search"
    # "product manager roles in Hyderabad, 5-10 years" style without the word "jobs".
    if re.search(r"\broles?\b", text, re.I) and _has_job_filters(text) and not _COMPARE_RE.search(text):
        return "job_search"
    if _JOB_SEARCH_RE.search(text) and parse_location(combined)[0]:
        return "job_search"
    return "briefing"


def _has_job_filters(text: str) -> bool:
    return bool(
        parse_experience_range(text) != (None, None)
        or parse_posted_within_days(text) is not None
        or parse_location(text)[0]
    )


# --------------------------------------------------------------------------- #
# Slot parsers
# --------------------------------------------------------------------------- #

_EXP_RANGE_RE = re.compile(
    r"(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", re.I
)
_EXP_RANGE_BARE_RE = re.compile(
    r"experience\s*[:\-]?\s*(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})\b", re.I
)
_EXP_MIN_RE = re.compile(
    r"(?:minimum|min\.?|at\s+least|over|more\s+than)\s+(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", re.I
)
_EXP_PLUS_RE = re.compile(r"(\d{1,2})\s*\+\s*(?:years?|yrs?)\b", re.I)
_EXP_SINGLE_RE = re.compile(r"(\d{1,2})\s*(?:years?|yrs?)\b(?:\s+of)?\s+(?:relevant\s+)?experience", re.I)


def _exp_candidates(text: str) -> list[tuple[int, int, int | None, int | None]]:
    """Return (position, end, min, max) candidates from source text."""
    out: list[tuple[int, int, int | None, int | None]] = []
    seen_spans: list[tuple[int, int]] = []

    def add(m: re.Match[str], lo: int | None, hi: int | None) -> None:
        span = m.span()
        if any(s <= span[0] < e or s < span[1] <= e for s, e in seen_spans):
            return
        seen_spans.append(span)
        out.append((span[0], span[1], lo, hi))

    for m in _EXP_RANGE_RE.finditer(text):
        a, b = int(m.group(1)), int(m.group(2))
        if a <= b:
            add(m, a, b)
    for m in _EXP_RANGE_BARE_RE.finditer(text):
        a, b = int(m.group(1)), int(m.group(2))
        if a <= b:
            add(m, a, b)
    for m in _EXP_MIN_RE.finditer(text):
        add(m, int(m.group(1)), None)
    for m in _EXP_PLUS_RE.finditer(text):
        add(m, int(m.group(1)), None)
    for m in _EXP_SINGLE_RE.finditer(text):
        add(m, int(m.group(1)), None)
    out.sort(key=lambda c: c[0])
    return out


def parse_experience_range(text: str) -> tuple[int | None, int | None]:
    """Parse the first experience band in ``text``. Numbers win over adjectives."""
    cands = _exp_candidates(text or "")
    if not cands:
        return None, None
    _, _, lo, hi = cands[0]
    return lo, hi


def parse_experience_from_source(text: str) -> tuple[int | None, int | None, list[str]]:
    """Deterministic experience parse for source text (section 9.5).

    When two different ranges appear keep the one nearest an "experience" token and
    return a conflict note. Never average.
    """
    cleaned = strip_html(text or "")
    cands = _exp_candidates(cleaned)
    notes: list[str] = []
    if not cands:
        return None, None, notes
    chosen = cands[0]
    distinct = {(c[2], c[3]) for c in cands}
    if len(distinct) > 1:
        notes.append("experience_conflict: multiple ranges in source text; kept the one nearest 'experience'")
        low = cleaned.lower()
        anchors = [m.start() for m in re.finditer("experience", low)]
        best_dist = None
        for cand in cands:
            dist = (
                min(min(abs(a - cand[0]), abs(a - cand[1])) for a in anchors) if anchors else 10_000
            )
            if best_dist is None or dist < best_dist:
                best_dist, chosen = dist, cand
    return chosen[2], chosen[3], notes


def strip_html(text: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", no_tags).strip()


_POSTED_PATTERNS: list[tuple[re.Pattern[str], Any]] = [
    (re.compile(r"\b(?:last|past|previous)\s+(\d{1,3})\s+days?\b", re.I), lambda m: int(m.group(1))),
    (re.compile(r"\bwithin\s+(?:the\s+)?(?:last|past)?\s*(\d{1,3})\s+days?\b", re.I), lambda m: int(m.group(1))),
    (re.compile(r"\b(?:last|past|previous)\s+(\d{1,2})\s+weeks?\b", re.I), lambda m: int(m.group(1)) * 7),
    (re.compile(r"\b(?:last|past|previous)\s+(?:24\s*hours?|day)\b", re.I), lambda m: 1),
    (re.compile(r"\b(?:posted\s+)?today\b", re.I), lambda m: 1),
    (re.compile(r"\b(?:last|past)\s+(?:a\s+)?week\b|\bposted\s+this\s+week\b|\bthis\s+week\b", re.I), lambda m: 7),
    (re.compile(r"\b(?:last|past)\s+(?:a\s+)?month\b|\bposted\s+this\s+month\b", re.I), lambda m: 30),
]


def parse_posted_within_days(text: str) -> int | None:
    """'last 7 days', 'past week', 'posted this week' -> 7. None when not stated."""
    for pattern, fn in _POSTED_PATTERNS:
        m = pattern.search(text or "")
        if m:
            return int(fn(m))
    return None


def parse_location(text: str) -> tuple[str, str, str, list[str]]:
    """Return (city, region, country_code, aliases). Empty city when none recognised."""
    lower = (text or "").lower()
    country_override: tuple[str, str] | None = None
    for marker, (region, cc) in _NON_IN_MARKERS.items():
        if re.search(rf"\b{marker}\b", lower):
            country_override = (region, cc)
            break
    for name in sorted(CITY_TABLE, key=len, reverse=True):
        pattern = rf"\b{re.escape(name)}\b"
        alt = [k for k, v in _CITY_NAME_ALIASES.items() if v == name]
        if re.search(pattern, lower) or any(re.search(rf"\b{re.escape(a)}\b", lower) for a in alt):
            region, cc, aliases = CITY_TABLE[name]
            if country_override and name == "hyderabad":
                return "Hyderabad", country_override[0], country_override[1], ["hyderabad"]
            return name.title(), region, cc, list(aliases)
    for key, canon in _CITY_NAME_ALIASES.items():
        if re.search(rf"\b{re.escape(key)}\b", lower) and canon in CITY_TABLE:
            region, cc, aliases = CITY_TABLE[canon]
            return canon.title(), region, cc, list(aliases)
    # Hyderabad localities without the city name.
    for loc in ("hitec city", "gachibowli", "madhapur", "kondapur", "cyberabad"):
        if re.search(rf"\b{loc}\b", lower):
            region, cc, aliases = CITY_TABLE["hyderabad"]
            return "Hyderabad", region, cc, list(aliases)
    return "", "", "IN", []


_REMOTE_RE = re.compile(r"\b(remote|hybrid|work[\s-]?from[\s-]?home|wfh)\b", re.I)


def parse_workplace(text: str) -> tuple[bool, str | None]:
    m = _REMOTE_RE.search(text or "")
    if not m:
        return False, None
    word = m.group(1).lower()
    if word == "hybrid":
        return True, "hybrid"
    return True, "remote"


def parse_role_query(task: str) -> str:
    """Extract the role phrase (text before 'jobs/openings/roles')."""
    text = (task or "").strip()
    text = re.sub(r"^(?:create\s+a\s+task\s*[:\-]\s*)", "", text, flags=re.I)
    m = re.search(rf"^(.*?)\b(?:{_JOB_NOUNS[3:-1]}|roles?)\b", text, re.I)
    head = m.group(1) if m else text
    head = re.sub(
        r"^\s*(?:please\s+)?(?:find|search(?:\s+for)?|show(?:\s+me)?|list|get|fetch|look(?:ing)?\s+for)\s+(?:me\s+)?(?:the\s+)?(?:latest\s+|new\s+|open\s+)?",
        "",
        head,
        flags=re.I,
    )
    head = re.sub(r"\b(in|at|near|for|from)\s*$", "", head.strip(), flags=re.I).strip(" ,.-")
    return head.strip().lower() or "product manager"


def role_family_for(role_query: str) -> str:
    q = (role_query or "").lower()
    if re.search(r"\bproduct\s+(manager|owner|lead|mgr)\b|\bpm\b|\bgpm\b", q) and "marketing" not in q:
        return "product_management"
    return "custom"


def _industry_remainder(text: str) -> str:
    found = [t for t in INDUSTRY_TERMS if re.search(rf"(?<![\w]){re.escape(t)}(?![\w])", (text or "").lower())]
    return ", ".join(found)


# --------------------------------------------------------------------------- #
# Intent
# --------------------------------------------------------------------------- #


def parse_job_search_intent(
    task: str,
    background: str = "",
    constraints: str = "",
    *,
    limit: int = 20,
) -> JobSearchIntent:
    """Parse the task once into a typed ``JobSearchIntent`` (section 5)."""
    task = (task or "").strip()
    combined = " ".join(p for p in (task, background or "", constraints or "") if p and p.strip())
    role_query = parse_role_query(task)
    family = role_family_for(role_query)
    city, region, cc, aliases = parse_location(combined)
    accept_remote, workplace = parse_workplace(combined)
    exp_min, exp_max = parse_experience_range(combined)
    posted = parse_posted_within_days(combined)

    if family == "product_management":
        include = list(PM_TITLE_INCLUDE)
        exclude = list(PM_TITLE_EXCLUDE)
    else:
        include = [role_query] if role_query else []
        exclude = []

    open_filters: list[str] = []
    if not city:
        open_filters.append("location")
    if exp_min is None and exp_max is None:
        open_filters.append("experience")
    if posted is None:
        open_filters.append("recency")

    location = JobLocationIntent(
        city=city,
        region=region,
        country_code=cc,
        aliases=aliases,
        radius_km=40,
        accept_remote=accept_remote,
    )
    return JobSearchIntent(
        role_query=role_query,
        role_family=family,
        title_include=include,
        title_exclude=exclude,
        location=location,
        experience=JobExperienceIntent(min_years=exp_min, max_years=exp_max),
        posted_within_days=posted,
        workplace=workplace,
        limit=limit,
        open_filters=open_filters,
        unparsed_remainder=_industry_remainder(combined),
        original_task=task,
    )


def intent_from_fields(
    base: JobSearchIntent | dict[str, Any],
    *,
    role_query: str | None = None,
    city: str | None = None,
    min_years: int | None = None,
    max_years: int | None = None,
    posted_within_days: int | None = None,
    accept_remote: bool | None = None,
    clear_experience: bool = False,
    clear_recency: bool = False,
) -> JobSearchIntent:
    """Apply user corrections from the confirm panel to a parsed intent."""
    intent = base if isinstance(base, JobSearchIntent) else JobSearchIntent.model_validate(base)
    data = intent.model_dump()
    if role_query is not None and role_query.strip():
        data["role_query"] = role_query.strip().lower()
        data["role_family"] = role_family_for(data["role_query"])
        if data["role_family"] == "product_management":
            data["title_include"], data["title_exclude"] = list(PM_TITLE_INCLUDE), list(PM_TITLE_EXCLUDE)
        else:
            data["title_include"], data["title_exclude"] = [data["role_query"]], []
    if city is not None:
        if city.strip():
            c, r, cc, al = parse_location(city)
            if c:
                data["location"].update({"city": c, "region": r, "country_code": cc, "aliases": al})
            else:
                data["location"].update(
                    {"city": city.strip().title(), "region": "", "aliases": [city.strip().lower()]}
                )
        else:
            data["location"].update({"city": "", "region": "", "aliases": []})
    if clear_experience:
        data["experience"].update({"min_years": None, "max_years": None})
    elif min_years is not None or max_years is not None:
        data["experience"].update({"min_years": min_years, "max_years": max_years})
    if clear_recency:
        data["posted_within_days"] = None
    elif posted_within_days is not None:
        data["posted_within_days"] = posted_within_days
    if accept_remote is not None:
        data["location"]["accept_remote"] = accept_remote
    open_filters = []
    if not data["location"]["city"]:
        open_filters.append("location")
    if data["experience"]["min_years"] is None and data["experience"]["max_years"] is None:
        open_filters.append("experience")
    if data["posted_within_days"] is None:
        open_filters.append("recency")
    data["open_filters"] = open_filters
    return JobSearchIntent.model_validate(data)


def job_success_criteria(intent: JobSearchIntent) -> list[str]:
    """Testable success criteria for the specification (section 10.1)."""
    crit = [
        "Every included row has job_id, company_name, and job_description copied from a tool payload",
        f"Every included row is in the {intent.role_family.replace('_', ' ')} family (no excluded titles)",
    ]
    if intent.location.city:
        crit.append(
            f"Every included row is in {intent.location.city} ({intent.location.country_code}) or a listed locality"
        )
    if intent.posted_within_days is not None:
        crit.append(
            f"Every included row has date_posted within the last {intent.posted_within_days} days"
        )
    exp = intent.experience
    if exp.min_years is not None or exp.max_years is not None:
        band = f"{exp.min_years if exp.min_years is not None else '?'}-{exp.max_years if exp.max_years is not None else '+'}"
        crit.append(
            f"Every included row overlaps {band} years of experience; rows with no stated years go to needs_review"
        )
    crit.extend(
        [
            "No apply URL or job id that was absent from the tool response",
            "An empty included set is allowed and must explain exclusions",
            "Leaves final approval to the human; nothing is applied, emailed, or scheduled",
        ]
    )
    return crit


# --------------------------------------------------------------------------- #
# Row-level matching
# --------------------------------------------------------------------------- #


def _norm_title(title: str) -> str:
    t = (title or "").lower()
    t = re.sub(r"[^a-z0-9+/&.\- ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def title_in_family(title: str, intent: JobSearchIntent) -> tuple[bool, str]:
    """Return (in_family, reason). Exclusions run first (section 6.2)."""
    t = _norm_title(title)
    if not t:
        return False, "empty title"
    has_pm_title = bool(re.search(r"\bproduct\s+manager\b", t))
    for term in intent.title_exclude:
        if term and re.search(rf"\b{re.escape(term.lower())}\b", t):
            if term.lower() in _SOFT_EXCLUDES and has_pm_title:
                continue
            return False, f"title excluded: '{term}'"
    if intent.role_family == "product_management":
        for pattern in _PM_INCLUDE_PATTERNS:
            if re.search(pattern, t):
                return True, "title in product_management family"
        for term in intent.title_include:
            if term and term.lower() in t:
                return True, "title in product_management family"
        return False, "title not in product_management family"
    needles = [x.lower() for x in intent.title_include if x] or ([intent.role_query.lower()] if intent.role_query else [])
    if not needles:
        return True, "no role filter"
    if any(n in t for n in needles):
        return True, f"title matches '{intent.role_query}'"
    return False, f"title does not match '{intent.role_query}'"


_NON_IN_TEXT = ("sindh", "pakistan", "karachi")


def location_match_for(record: JobRecord, intent: JobSearchIntent) -> tuple[str, str]:
    """Return (location_match, reason). Only the job's own location fields count."""
    loc = intent.location
    if not loc.city:
        return "unknown", "location filter not applied"
    hay = " ".join(x for x in (record.city or "", record.location_text or "") if x).lower()
    if not hay.strip():
        return "unknown", "no job location in source"
    if record.country_code and record.country_code.upper() != loc.country_code.upper():
        return "mismatch", f"country {record.country_code} is not {loc.country_code}"
    if loc.country_code.upper() == "IN" and any(m in hay for m in _NON_IN_TEXT):
        return "mismatch", "location is outside India"
    city_l = loc.city.lower()
    if re.search(rf"\b{re.escape(city_l)}\b", hay):
        return "city", f"city {loc.city}"
    for alias in [a.lower() for a in loc.aliases if a and a.lower() != city_l]:
        if re.search(rf"\b{re.escape(alias)}\b", hay):
            return "locality_alias", f"locality alias '{alias}' for {loc.city}"
    return "mismatch", f"location '{record.location_text or record.city}' is not {loc.city}"


def experience_match_for(
    exp_min: int | None, exp_max: int | None, intent: JobSearchIntent
) -> tuple[str, str]:
    """Overlap policy for the requested band (section 5.2)."""
    qmin, qmax = intent.experience.min_years, intent.experience.max_years
    if qmin is None and qmax is None:
        return "unknown", "experience filter not applied"
    if exp_min is None and exp_max is None:
        return "unknown", "experience not stated in source"
    lo_q = qmin if qmin is not None else 0
    hi_q = qmax if qmax is not None else 10_000
    lo_j = exp_min if exp_min is not None else 0
    hi_j = exp_max if exp_max is not None else 10_000
    if lo_j > hi_q or hi_j < lo_q:
        return "exclude", f"experience {_fmt_band(exp_min, exp_max)} does not overlap {_fmt_band(qmin, qmax)}"
    inside = lo_j >= lo_q and hi_j <= hi_q and exp_max is not None
    if inside:
        return "exact", f"experience {_fmt_band(exp_min, exp_max)} within {_fmt_band(qmin, qmax)} (exact)"
    return "overlap", f"experience {_fmt_band(exp_min, exp_max)} overlaps {_fmt_band(qmin, qmax)}"


def _fmt_band(lo: int | None, hi: int | None) -> str:
    if lo is None and hi is None:
        return "unstated"
    if hi is None:
        return f"{lo}+ years"
    if lo is None:
        return f"up to {hi} years"
    return f"{lo}-{hi} years"


_RELATIVE_RE = re.compile(
    r"(?:(?P<n>\d+)\+?|an?|one)\s*(?P<unit>minute|hour|day|week|month)s?\s+ago", re.I
)


def parse_posted_label(label: str | None, retrieved_at: datetime) -> datetime | None:
    """Convert 'N days ago' / 'today' / 'yesterday' to a UTC datetime using retrieved_at."""
    if not label:
        return None
    text = label.strip().lower()
    if text in {"today", "just posted", "just now", "new"}:
        return retrieved_at
    if text == "yesterday":
        return retrieved_at - timedelta(days=1)
    m = _RELATIVE_RE.search(text)
    if not m:
        return None
    n = int(m.group("n")) if m.group("n") else 1
    unit = m.group("unit").lower()
    delta = {
        "minute": timedelta(minutes=n),
        "hour": timedelta(hours=n),
        "day": timedelta(days=n),
        "week": timedelta(weeks=n),
        "month": timedelta(days=30 * n),
    }[unit]
    return retrieved_at - delta


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_retrieved(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return _parse_iso(value) or datetime.now(timezone.utc)


def _evaluate_record(
    record: JobRecord,
    intent: JobSearchIntent,
    retrieved: datetime,
    posted_after: datetime | None,
) -> tuple[JobRecord, str | None]:
    """Fill match fields. Returns (record, reason_code_if_not_included)."""
    reasons: list[str] = []
    rec = record.model_copy(deep=True)
    if not rec.retrieved_at:
        rec.retrieved_at = retrieved.isoformat()

    in_family, role_reason = title_in_family(rec.title, intent)
    rec.role_match = "in_family" if in_family else "out_of_family"

    loc_match, loc_reason = location_match_for(rec, intent)
    rec.location_match = loc_match  # type: ignore[assignment]

    # Recency: prefer ISO date; fall back to relative label.
    posted_dt = _parse_iso(rec.date_posted)
    if posted_dt is None and rec.posted_label:
        posted_dt = parse_posted_label(rec.posted_label, retrieved)
        if posted_dt is not None:
            rec.date_posted = posted_dt.isoformat()
    if intent.posted_within_days is None or posted_after is None:
        rec.recency_match = "unknown"
        recency_reason = "recency filter not applied"
    elif posted_dt is None:
        rec.recency_match = "unknown"
        recency_reason = "no posted date in source"
    elif posted_dt >= posted_after:
        rec.recency_match = "within_window"
        recency_reason = (
            f"posted {posted_dt.date().isoformat()} within {intent.posted_within_days} days "
            f"of {retrieved.date().isoformat()}"
        )
    else:
        rec.recency_match = "stale"
        recency_reason = f"posted {posted_dt.date().isoformat()} is older than {intent.posted_within_days} days"

    # Experience: structured fields first, then deterministic text parse.
    notes: list[str] = []
    exp_min, exp_max = rec.experience_min, rec.experience_max
    if exp_min is None and exp_max is None:
        source_text = " ".join(x for x in (rec.experience_text or "", rec.job_description or "") if x)
        exp_min, exp_max, notes = parse_experience_from_source(source_text)
        rec.experience_min, rec.experience_max = exp_min, exp_max
        if exp_min is not None or exp_max is not None:
            if not rec.experience_text:
                rec.experience_text = _fmt_band(exp_min, exp_max)
    exp_match, exp_reason = experience_match_for(exp_min, exp_max, intent)
    rec.experience_match = exp_match  # type: ignore[assignment]
    reasons.extend(notes)

    # Decision order: role, location, recency, company, experience.
    code: str | None = None
    if not in_family:
        code = "out_of_family"
        reasons.insert(0, role_reason)
    elif loc_match == "mismatch":
        code = "wrong_city"
        reasons.insert(0, loc_reason)
    elif loc_match == "unknown" and intent.location.city:
        code = "unknown_location"
        reasons.insert(0, loc_reason)
    elif rec.workplace == "remote" and not intent.location.accept_remote and loc_match not in {"city", "locality_alias"}:
        code = "remote_not_requested"
        reasons.insert(0, "remote posting and remote was not requested")
    elif rec.recency_match == "stale":
        code = "stale"
        reasons.insert(0, recency_reason)
    elif rec.recency_match == "unknown" and intent.posted_within_days is not None:
        code = "unknown_recency"
        reasons.insert(0, recency_reason)
    elif not (rec.company_name or "").strip():
        code = "missing_company"
        reasons.insert(0, "source did not provide a company name")
    elif exp_match == "exclude":
        code = "experience_no_overlap"
        reasons.insert(0, exp_reason)
    elif exp_match == "unknown" and (
        intent.experience.min_years is not None or intent.experience.max_years is not None
    ):
        code = "unknown_experience"
        reasons.insert(0, exp_reason)

    if code is None:
        rec.match_status = "included"
        reasons = [role_reason, loc_reason, recency_reason, exp_reason] + reasons
    elif code == "unknown_experience":
        rec.match_status = "needs_review"
        reasons = [role_reason, loc_reason, recency_reason] + reasons
    else:
        rec.match_status = "excluded"
    # Machine reason code first so the UI can group by it.
    if code:
        reasons.insert(0, code)
    rec.match_reasons = [r for r in dict.fromkeys(reasons) if r]
    return rec, code


def apply_job_filters(
    records: Iterable[JobRecord],
    intent: JobSearchIntent,
    *,
    retrieved_at: str | datetime | None = None,
    source_name: str = "",
    sources_failed: list[str] | None = None,
    illustrative: bool = False,
    extra_notes: list[str] | None = None,
) -> JobSearchEnvelope:
    """Apply role, place, recency, and experience rules in code (sections 5-9)."""
    retrieved = _parse_retrieved(retrieved_at)
    posted_after = (
        retrieved - timedelta(days=intent.posted_within_days)
        if intent.posted_within_days is not None
        else None
    )
    all_records = list(records)
    raw_ids = [r.job_id for r in all_records if r.job_id]

    seen: set[str] = set()
    included: list[JobRecord] = []
    needs_review: list[JobRecord] = []
    excluded: list[JobRecord] = []
    reason_counts: dict[str, int] = {}

    for record in all_records:
        if record.job_id in seen:
            continue
        seen.add(record.job_id)
        rec, code = _evaluate_record(record, intent, retrieved, posted_after)
        if rec.match_status == "included":
            included.append(rec)
        elif rec.match_status == "needs_review":
            needs_review.append(rec)
        else:
            excluded.append(rec)
            reason_counts[code or "excluded"] = reason_counts.get(code or "excluded", 0) + 1

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    included.sort(
        key=lambda r: (-((_parse_iso(r.date_posted) or epoch).timestamp()), r.title.lower())
    )

    truncated = 0
    if intent.limit and len(included) > intent.limit:
        overflow = included[intent.limit :]
        included = included[: intent.limit]
        truncated = len(overflow)
        for rec in overflow:
            rec.match_status = "excluded"
            rec.match_reasons = ["truncated_by_limit"] + rec.match_reasons
            excluded.append(rec)
        reason_counts["truncated_by_limit"] = truncated

    counts: dict[str, int] = {
        "retrieved": len(seen),
        "included": len(included),
        "needs_review": len(needs_review),
        "excluded": len(excluded),
    }
    for code, n in sorted(reason_counts.items()):
        counts[f"excluded_{code}"] = n
    if truncated:
        counts["truncated_by_limit"] = truncated

    notes: list[str] = list(extra_notes or [])
    exp = intent.experience
    if exp.min_years is not None or exp.max_years is not None:
        notes.append(
            "Experience was applied after retrieval because the source has no experience parameter."
        )
    if intent.posted_within_days is not None:
        notes.append(
            "Recency uses each job's own posted date (relative labels converted at retrieval time), "
            "not the date a page was indexed."
        )
    for missing in intent.open_filters:
        notes.append(f"Filter not applied (not stated in the task): {missing}.")
    if counts["retrieved"] == 0:
        notes.append("The source returned no listings; nothing was invented to fill the table.")
    if truncated:
        notes.append(f"Included table capped at {intent.limit}; {truncated} further match(es) not shown.")

    echo = JobQueryEcho(
        role_family=intent.role_family,
        role_query=intent.role_query,
        city=(
            f"{intent.location.city}, {intent.location.region}, {intent.location.country_code}"
            if intent.location.city and intent.location.region
            else intent.location.city
        ),
        country_code=intent.location.country_code,
        radius_km=intent.location.radius_km,
        experience_min=exp.min_years,
        experience_max=exp.max_years,
        range_policy=exp.range_policy,
        posted_within_days=intent.posted_within_days,
        posted_after=posted_after.isoformat() if posted_after else None,
        retrieved_at=retrieved.isoformat(),
        source_name=source_name,
        open_filters=list(intent.open_filters),
    )
    allowed_urls = sorted({r.apply_url for r in all_records if r.apply_url})
    return JobSearchEnvelope(
        query_echo=echo,
        jobs=included,
        needs_review=needs_review,
        excluded=excluded,
        counts=counts,
        coverage_notes=notes,
        sources_failed=list(sources_failed or []),
        illustrative=illustrative,
        raw_tool_job_ids=raw_ids,
        extra={"allowed_urls": allowed_urls},
    )


# --------------------------------------------------------------------------- #
# Grounding (section 10.2): drop anything the tool payload did not contain
# --------------------------------------------------------------------------- #

_ID_TOKEN_RE = re.compile(r"\b(?:serpapi|demo|adzuna|jsearch)[:\-][\w:\-]{3,}", re.I)
_URL_RE = re.compile(r"https?://[^\s)\]>\"']+", re.I)


def ground_job_envelope(envelope: JobSearchEnvelope) -> tuple[JobSearchEnvelope, list[str]]:
    """Drop rows whose job_id is not in the tool payload and URLs not returned by the tool."""
    allowed_ids = set(envelope.raw_tool_job_ids)
    allowed_urls = set((envelope.extra or {}).get("allowed_urls") or [])
    dropped: list[str] = []

    def clean(rows: list[JobRecord]) -> list[JobRecord]:
        out: list[JobRecord] = []
        for row in rows:
            if row.job_id not in allowed_ids:
                dropped.append(row.job_id)
                continue
            if row.apply_url and row.apply_url not in allowed_urls:
                row = row.model_copy(update={"apply_url": None})
            out.append(row)
        return out

    jobs, review, excluded = clean(envelope.jobs), clean(envelope.needs_review), clean(envelope.excluded)
    counts = dict(envelope.counts)
    counts.update({"included": len(jobs), "needs_review": len(review), "excluded": len(excluded)})
    notes = list(envelope.coverage_notes)
    if dropped:
        notes.append(f"Dropped {len(dropped)} row(s) whose job id was not in the tool payload.")
    grounded = envelope.model_copy(
        update={
            "jobs": jobs,
            "needs_review": review,
            "excluded": excluded,
            "counts": counts,
            "coverage_notes": notes,
        }
    )
    return grounded, dropped


def scrub_ungrounded_refs(
    lines: list[str], *, allowed_ids: Iterable[str], allowed_urls: Iterable[str]
) -> list[str]:
    """Remove text lines that cite a job id or URL the tool never returned."""
    ids, urls = {i.lower() for i in allowed_ids}, set(allowed_urls)
    kept: list[str] = []
    for line in lines:
        text = str(line)
        bad_id = any(
            not any(i == tok.lower() or i.startswith(tok.lower()) for i in ids)
            for tok in _ID_TOKEN_RE.findall(text)
        )
        bad_url = any(u.rstrip(".,") not in urls for u in _URL_RE.findall(text))
        if not (bad_id or bad_url):
            kept.append(line)
    return kept


def text_has_ungrounded_refs(text: str, *, allowed_ids: Iterable[str], allowed_urls: Iterable[str]) -> bool:
    return not scrub_ungrounded_refs([text], allowed_ids=allowed_ids, allowed_urls=allowed_urls)
