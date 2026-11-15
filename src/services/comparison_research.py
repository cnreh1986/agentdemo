"""Public-source collection and grounding for competitive analysis (Phase B/C).

Mirrors the job-search pattern: tool URLs are the only allow-list; unknown cells
stay empty when a page is missing; Demo Mode never calls the network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.models.competitive_analysis import (
    CompetitiveAnalysisIntent,
    ComparisonCell,
    ComparisonEnvelope,
    ComparisonEvidenceItem,
)
from src.providers.search_base import SearchProvider
from src.services.comparison_intent import (
    CATALOG_BY_ID,
    HIRING_CRITERIA,
    _is_catalog_pair,
    _user_listed,
    cell_id,
)

_WHO_ELSE = re.compile(r"\b(?:who\s+else|other\s+competitors?|alternatives?\s+to\s+consider)\b", re.I)
_WHAT_ELSE = re.compile(r"\b(?:what\s+else|other\s+criteria|additional\s+criteria)\b", re.I)
_URL_RE = re.compile(r"https?://[^\s)\]\">']+")


@dataclass
class PublicEvidenceBundle:
    """Result of optional Firecrawl collection for a comparison run."""

    role_evidence: dict[str, list[ComparisonEvidenceItem]] = field(default_factory=dict)
    product_fills: dict[str, ComparisonEvidenceItem] = field(default_factory=dict)
    public_items: list[dict[str, Any]] = field(default_factory=list)
    allowed_urls: set[str] = field(default_factory=set)
    note: str | None = None
    suggested_subjects: list[str] = field(default_factory=list)
    suggested_criteria: list[str] = field(default_factory=list)


def product_fill_key(subject_id: str, criterion_id: str) -> str:
    return f"{subject_id}:{criterion_id}"


def detect_suggestion_asks(text: str) -> tuple[bool, bool]:
    """Return (ask_subjects, ask_criteria) when the user requested suggestions."""
    blob = text or ""
    return bool(_WHO_ELSE.search(blob)), bool(_WHAT_ELSE.search(blob))


def _clip_claim(snippet: str, title: str = "") -> str:
    claim = (snippet or title or "").strip()
    return claim[:240]


def _to_public_item(result: Any, claim: str) -> dict[str, Any]:
    return {
        "claim": claim,
        "source_title": getattr(result, "title", None),
        "source_url": getattr(result, "url", None),
        "source_domain": getattr(result, "domain", None),
        "retrieved_at": getattr(result, "retrieved_at", None),
        "supporting_excerpt_or_summary": claim,
        "evidence_type": "secondary",
        "confidence": "medium",
    }


def _search_safe(
    provider: SearchProvider, query: str, *, max_results: int = 2
) -> tuple[list[Any], str | None]:
    try:
        return list(provider.search(query, max_results=max_results) or [])[:max_results], None
    except Exception as exc:  # noqa: BLE001
        return [], f"Public search failed for part of the matrix ({str(exc)[:80]}); defaults are unverified."


def collect_public_evidence(
    search_provider: SearchProvider | None,
    intent: CompetitiveAnalysisIntent | dict[str, Any],
) -> PublicEvidenceBundle:
    """Run short per-criterion (and per-product) queries when search is configured.

    Role (PM/PMM): every non-pricing hiring criterion, ≤2 results each.
    Product: each user criterion × each named subject; fill only when a URL exists.
    """
    intent = (
        intent
        if isinstance(intent, CompetitiveAnalysisIntent)
        else CompetitiveAnalysisIntent.model_validate(intent)
    )
    bundle = PublicEvidenceBundle()
    ask_subjects, ask_criteria = detect_suggestion_asks(
        " ".join(
            [
                intent.original_task,
                intent.decision.question,
                intent.unparsed_remainder,
                intent.criteria_policy,
            ]
        )
    )
    if ask_subjects:
        bundle.suggested_subjects = [
            "Named subjects only appear as columns; add competitors yourself if needed."
        ]
    if ask_criteria:
        bundle.suggested_criteria = [
            "Stick to the criteria you listed; add more rows only after you name them."
        ]

    if intent.status != "ready":
        return bundle

    if not search_provider or not search_provider.is_configured():
        if _is_catalog_pair(intent):
            bundle.note = (
                "Public pages were not retrieved (no search tool configured); domain-default cells "
                "are model knowledge, and user-supplied cells still stand."
            )
        else:
            bundle.note = (
                "Public pages were not retrieved (no search tool configured); product cells stay "
                "unknown rather than inventing features or pricing."
            )
        return bundle

    notes: list[str] = []
    if _is_catalog_pair(intent):
        labels = " versus ".join(s.label.lower() for s in intent.subjects)
        for crit in [c for c in HIRING_CRITERIA if c != "pricing"]:
            row = CATALOG_BY_ID[crit]
            query = f"{labels} {row['label'].lower()} responsibilities"
            results, err = _search_safe(search_provider, query, max_results=2)
            if err:
                notes.append(err)
                continue
            for r in results:
                claim = _clip_claim(r.snippet, r.title)
                if not r.url or not claim:
                    continue
                bundle.allowed_urls.add(r.url)
                item = ComparisonEvidenceItem(
                    claim=claim, source_url=r.url, source_title=r.title, basis="public_source"
                )
                bundle.role_evidence.setdefault(crit, []).append(item)
                bundle.public_items.append(_to_public_item(r, claim))
    else:
        criteria = _user_listed(intent)
        for crit in criteria:
            crit_id = re.sub(r"[^a-z0-9]+", "_", crit.lower()).strip("_") or "criterion"
            for subject in intent.subjects:
                query = f"{subject.label} {crit}"
                results, err = _search_safe(search_provider, query, max_results=2)
                if err:
                    notes.append(err)
                    continue
                filled = False
                for r in results:
                    claim = _clip_claim(r.snippet, r.title)
                    if not r.url or not claim:
                        continue
                    bundle.allowed_urls.add(r.url)
                    key = product_fill_key(subject.subject_id, crit_id)
                    if key not in bundle.product_fills:
                        bundle.product_fills[key] = ComparisonEvidenceItem(
                            claim=claim,
                            source_url=r.url,
                            source_title=r.title,
                            basis="public_source",
                        )
                        filled = True
                    bundle.public_items.append(_to_public_item(r, claim))
                if not filled:
                    # Explicit unknown — no inventing.
                    pass

    if notes:
        bundle.note = notes[0]
    return bundle


def ground_comparison_envelope(
    envelope: ComparisonEnvelope | dict[str, Any],
    allowed_urls: set[str] | None = None,
) -> tuple[ComparisonEnvelope, list[str]]:
    """Drop public_source evidence/cells whose URL is not in the tool allow-list."""
    envelope = (
        envelope
        if isinstance(envelope, ComparisonEnvelope)
        else ComparisonEnvelope.model_validate(envelope)
    )
    extra = dict(envelope.extra or {})
    urls = set(allowed_urls or extra.get("allowed_urls") or [])
    dropped: list[str] = []
    cleaned: list[ComparisonCell] = []

    for cell in envelope.matrix:
        kept_ev: list[ComparisonEvidenceItem] = []
        for ev in cell.evidence:
            if ev.basis == "public_source":
                if not ev.source_url or ev.source_url not in urls:
                    dropped.append(cell_id(cell))
                    continue
            kept_ev.append(ev)

        if cell.basis == "public_source":
            public = [e for e in kept_ev if e.basis == "public_source" and e.source_url]
            if not public:
                dropped.append(cell_id(cell))
                cleaned.append(
                    cell.model_copy(
                        update={"value": "", "basis": "unknown", "evidence": [], "score": None}
                    )
                )
                continue
            cleaned.append(
                cell.model_copy(
                    update={
                        "value": public[0].claim or cell.value,
                        "evidence": kept_ev,
                    }
                )
            )
            continue

        # domain_default / user_supplied: strip bad public_source attachments only
        cleaned.append(cell.model_copy(update={"evidence": kept_ev}))

    notes = list(extra.get("limitations") or [])
    if dropped:
        note = (
            f"Dropped {len(set(dropped))} public_source attachment(s) whose URL was not "
            "returned by the search tool."
        )
        if note not in notes:
            notes.append(note)
        extra["limitations"] = notes

    extra["allowed_urls"] = sorted(urls)
    grounded = envelope.model_copy(update={"matrix": cleaned, "extra": extra})
    return grounded, sorted(set(dropped))


def scrub_comparison_markdown(text: str, *, allowed_urls: set[str]) -> str:
    """Remove markdown lines that cite a URL the tool never returned."""
    if not text:
        return text
    kept: list[str] = []
    for line in text.splitlines():
        found = _URL_RE.findall(line)
        if found and any(u.rstrip(".,)") not in allowed_urls for u in found):
            continue
        kept.append(line)
    return "\n".join(kept)
