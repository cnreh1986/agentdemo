"""Competitive-analysis intent parsing and comparison matrix builders.

Implements newehancement.md sections 17-26: the user's context is evidence, every cell
carries a basis, unknown cells stay empty, and a thin request yields ``needs_context``
plus a labelled domain frame instead of an invented analysis.
"""

from __future__ import annotations

import re
from typing import Any

from src.models.competitive_analysis import (
    CompetitiveAnalysisIntent,
    ComparisonCell,
    ComparisonDecision,
    ComparisonEnvelope,
    ComparisonEvidenceItem,
    ComparisonOption,
    ComparisonSubject,
    UserContextSlots,
)

DOMAIN_FRAME_BANNER = (
    "Domain frame, not an analysis of your company: every cell below is the usual "
    "Product Manager versus Product Marketer split (domain default). Provide your decision "
    "and situation to get a contextual comparison."
)

# --------------------------------------------------------------------------- #
# Role catalog (section 20)
# --------------------------------------------------------------------------- #

ROLE_CATALOG: list[dict[str, str]] = [
    {
        "id": "problem_ownership",
        "label": "Problem ownership",
        "question": "Who frames the customer problem and the outcome?",
        "pm": "Owns the problem, the bet, and the success criteria.",
        "pmm": "Owns the segment and the narrative around that problem.",
    },
    {
        "id": "roadmap",
        "label": "Roadmap",
        "question": "Who decides what is built, and in what order?",
        "pm": "Owns the product roadmap and the trade-offs.",
        "pmm": "Owns the go-to-market roadmap, timed off the product roadmap.",
    },
    {
        "id": "positioning",
        "label": "Positioning",
        "question": "Who states the value, for whom, against what alternative?",
        "pm": "Contributes product truth and proof.",
        "pmm": "Owns positioning and messaging.",
    },
    {
        "id": "launch",
        "label": "Launch",
        "question": "Who runs a release from readiness to market?",
        "pm": "Confirms the product is ready and watches adoption and guardrails.",
        "pmm": "Leads launch tiering, channels, and internal readiness.",
    },
    {
        "id": "pricing",
        "label": "Pricing",
        "question": "Who sets price and packaging?",
        "pm": "Owns the value metric as a product choice.",
        "pmm": "Owns packaging input, buyer journey, and how price is explained.",
    },
    {
        "id": "enablement",
        "label": "Enablement",
        "question": "Who prepares the people who sell and support?",
        "pm": "Supplies product truth.",
        "pmm": "Owns pitch, demo story, objection handling, and battlecards.",
    },
    {
        "id": "discovery",
        "label": "Discovery",
        "question": "Who talks to customers, and what comes back?",
        "pm": "Interviews become roadmap bets.",
        "pmm": "Interviews become personas, message tests, and win/loss notes.",
    },
    {
        "id": "metrics",
        "label": "Metrics",
        "question": "What numbers is the role accountable for?",
        "pm": "Activation, adoption, retention, reliability.",
        "pmm": "Conversion, pipeline influence, win rate, enablement usage.",
    },
    {
        "id": "artifacts",
        "label": "Artifacts",
        "question": "What documents does the role leave behind?",
        "pm": "Problem brief, specification, roadmap, experiment note.",
        "pmm": "Positioning doc, messaging, launch plan, enablement kit.",
    },
    {
        "id": "horizon",
        "label": "Horizon",
        "question": "What clock does the role run on?",
        "pm": "Multi-quarter roadmap.",
        "pmm": "Launch cycle and the lifecycle after launch.",
    },
]
CATALOG_BY_ID = {row["id"]: row for row in ROLE_CATALOG}

# Rows that change a hiring decision with one headcount (the rest go to criteria_not_used).
HIRING_CRITERIA = ["launch", "positioning", "enablement", "roadmap", "metrics", "pricing"]
OWNERSHIP_CRITERION = ("current_ownership", "Current ownership at this company")

SHARED_WORK = ["discovery", "launch", "pricing", "competitive notes"]

THIN_CONTEXT_QUESTIONS = [
    "What decision should this comparison answer?",
    "What do you sell, and to whom?",
    "Who already owns roadmap, messaging, release notes, and sales calls?",
    "What constraint binds the choice (headcount, timing, market)?",
]

_SUBJECT_ALIASES: list[tuple[str, str, re.Pattern[str]]] = [
    ("pm", "Product Manager", re.compile(r"^(?:product\s+manager|product\s+mgr|pm|product\s+management)$", re.I)),
    (
        "pmm",
        "Product Marketer",
        re.compile(r"^(?:product\s+marketer|product\s+marketing(?:\s+manager)?|pmm)$", re.I),
    ),
]
_CONFIRM_SUBJECT = re.compile(r"^(?:project|program)\s+manager$", re.I)
_ROLE_WORDS = {
    "manager", "marketer", "engineer", "designer", "analyst", "developer", "lead", "owner",
    "director", "officer", "scientist", "architect", "recruiter", "consultant", "writer",
}
_NOTE_PATTERNS = {
    "pm": re.compile(r"\b(?:product\s+manager|pm|product\s+mgr)\b", re.I),
    "pmm": re.compile(r"\b(?:product\s+marketer|product\s+marketing(?:\s+manager)?|pmm)\b", re.I),
}


# --------------------------------------------------------------------------- #
# Subjects
# --------------------------------------------------------------------------- #


def split_comparison_subjects(task: str) -> list[str]:
    """Pull the named subjects from 'Compare A and B ...' / 'A vs B' (section 19.1).

    Searches the whole task (not only the first sentence) so market-research phrasing like
    \"Conduct market research… Compare HubSpot, Mailchimp, and Brevo on pricing…\" still works.
    """
    text = (task or "").strip()
    if not text:
        return []
    m = re.search(
        r"\b(?:compare|comparison\s+of|difference\s+between)\s+(?:a\s+|an\s+|the\s+)?(.+)",
        text,
        re.I,
    )
    if m:
        # Keep only the remainder of the compare sentence (not following sentences).
        body = re.split(r"[.!?\n]", m.group(1), maxsplit=1)[0]
    else:
        # Fall back to first sentence for bare "A vs B" without the word compare.
        first = re.split(r"(?<=[.!?])\s+|\n", text, maxsplit=1)[0].strip().rstrip(".!?")
        if re.search(r"\b(?:vs\.?|versus)\b", first, re.I):
            body = first
        else:
            return []
    # Drop trailing decision/criteria clauses: "… on pricing", "… for our stack".
    body = re.split(
        r"\s+(?:on|for|in|at|as|given|when|because|so|considering|based\s+on|"
        r"where|that|which|if|with\s+my|with\s+our)\s+",
        body,
        maxsplit=1,
        flags=re.I,
    )[0]
    parts = re.split(r"\s*,\s*|\s+and\s+|\s+vs\.?\s+|\s+versus\s+|\s+to\s+|\s+against\s+", body, flags=re.I)
    out: list[str] = []
    for part in parts:
        label = re.sub(r"^(?:a|an|the|my|our|and|or)\s+", "", part.strip(), flags=re.I).strip(" ,.;:?")
        if label and len(label.split()) <= 6 and label.lower() not in {x.lower() for x in out}:
            out.append(label)
    return out[:5]


def canonical_subject(label: str) -> tuple[ComparisonSubject, bool]:
    """Return (subject, needs_confirmation). PM and PMM map to stable ids."""
    clean = label.strip()
    for sid, canon, pattern in _SUBJECT_ALIASES:
        if pattern.match(clean):
            return ComparisonSubject(subject_id=sid, label=canon, kind="role"), False
    needs_confirm = bool(_CONFIRM_SUBJECT.match(clean))
    slug = re.sub(r"[^a-z0-9]+", "_", clean.lower()).strip("_") or "subject"
    words = clean.lower().split()
    kind = "role" if words and words[-1] in _ROLE_WORDS else "product"
    shown = clean if any(c.isupper() for c in clean[1:]) else clean.title()
    return ComparisonSubject(subject_id=slug, label=shown, kind=kind), needs_confirm


# --------------------------------------------------------------------------- #
# Context parsing
# --------------------------------------------------------------------------- #


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s and s.strip()]


_ACTION_VERB = re.compile(
    r"^(?:also\s+)?(?:writes?|joins?|owns?|runs?|handles?|does|leads?|manages?|sets?|drafts?|attends?|takes?|covers?)\s+(?:the\s+|our\s+|all\s+)?",
    re.I,
)


def _parse_user_context(background: str) -> tuple[UserContextSlots, set[int]]:
    sentences = _sentences(background)
    used: set[int] = set()
    slots = UserContextSlots()
    team_parts: list[str] = []
    ownership: list[str] = []

    from src.services.job_intent import parse_location

    for idx, sent in enumerate(sentences):
        m = re.search(r"(\d[\d,]*)\s*[- ]?\s*(?:person|people|employees?)\b", sent, re.I)
        if m and not slots.company_stage:
            slots.company_stage = f"about {m.group(1)} people"
            used.add(idx)
        elif not slots.company_stage:
            m2 = re.search(r"\b(pre-seed|seed|series\s+[a-f]|early[- ]stage|growth[- ]stage|startup)\b", sent, re.I)
            if m2:
                slots.company_stage = m2.group(1).lower()
                used.add(idx)
        if not slots.business_model:
            for term in ("B2B SaaS", "B2C", "B2B", "SaaS", "marketplace", "D2C"):
                if re.search(rf"\b{re.escape(term)}\b", sent, re.I):
                    slots.business_model = term
                    used.add(idx)
                    break
        if not slots.location:
            city, _, cc, _ = parse_location(sent)
            if city:
                slots.location = f"{city}, India" if cc == "IN" else city
                used.add(idx)
        m = re.search(r"\bwe\s+(?:sell|build|make|offer|provide)\s+(.+?)\s+(?:to|for)\s+(.+?)$", sent.rstrip(".;"), re.I)
        if m and not slots.product:
            slots.product, slots.customer = m.group(1).strip(), m.group(2).strip()
            used.add(idx)
        elif not slots.product:
            m = re.search(r"\bwe\s+(?:sell|build|make|offer|provide)\s+(.+?)$", sent.rstrip(".;"), re.I)
            if m:
                slots.product = m.group(1).strip()
                used.add(idx)
        if not slots.go_to_market:
            m = re.search(
                r"\b(founder[- ]led(?:\s+sales)?|self[- ]serve|product[- ]led\s+growth|plg|inside\s+sales|channel\s+partners?|enterprise\s+sales)\b",
                sent,
                re.I,
            )
            if m:
                val = re.sub(r"founder[- ]led", "founder-led", m.group(1).lower())
                slots.go_to_market = val if "sales" in val or "growth" in val or "serve" in val or "partner" in val else f"{val} sales"
                used.add(idx)
        m = re.search(r"\bwe\s+have\s+(.+?)$", sent.rstrip(".;"), re.I)
        if m:
            team_parts.append(m.group(1).strip())
            used.add(idx)
        m = re.search(r"\b(?:our|the|existing|current)\s+([a-z][\w\- ]*?)\s+already\s+(.+?)$", sent.rstrip(".;"), re.I)
        if m:
            role = m.group(1).strip().lower()
            for action in re.split(r"\s+and\s+|,\s*", m.group(2)):
                obj = _ACTION_VERB.sub("", action.strip()).strip()
                if obj:
                    ownership.append(f"{obj}: existing {role}")
            used.add(idx)
    slots.current_team = ", ".join(team_parts)
    slots.current_ownership = ownership
    return slots, used


def _parse_decision(
    task: str, background: str, constraints: str, time_horizon: str
) -> ComparisonDecision:
    combined = " ".join(p for p in (task, background, constraints) if p)
    question = ""
    m = re.search(r"\bdecision\s*(?:is|:)\s*(.+?)(?:[.;\n]|$)", combined, re.I)
    if m:
        question = m.group(1).strip().rstrip("?").strip()
        question = question[:1].upper() + question[1:] + ("?" if not question.endswith("?") else "")
    elif re.search(r"\b(?:next\s+hire|hire|hiring|headcount)\b", combined, re.I):
        single = bool(re.search(r"\b(?:one|1|single)\s+(?:headcount|hire|role)|\bsingle\b", combined, re.I))
        horizon = (time_horizon or "").strip().lower()
        if not horizon and re.search(r"next\s+quarter", combined, re.I):
            horizon = "next quarter"
        when = f" {horizon}" if horizon else " next"
        question = (
            f"Which {'single ' if single else ''}role should we hire{when}, "
            "and what does the current team keep owning?"
        )
    else:
        m = re.search(r"\bwhich\s+(?:one\s+)?(?:should|do)\s+we\s+(.+?)(?:\?|[.;]|$)", combined, re.I)
        if m:
            question = f"Which one should we {m.group(1).strip()}?"
    audience = ""
    m = re.search(r"\baudience\s*(?:is|:)\s*(?:the\s+|my\s+)?([A-Za-z][\w\- ]{1,30}?)(?:[.;,\n]|$)", combined, re.I)
    if m:
        audience = m.group(1).strip().lower()
    clauses: list[str] = []
    for clause in re.split(r"[.;\n]+", constraints or ""):
        clause = clause.strip()
        if clause and not re.match(r"^audience\b", clause, re.I):
            clauses.append(clause)
    return ComparisonDecision(
        question=question,
        audience=audience,
        time_horizon=(time_horizon or "").strip(),
        constraints=clauses,
    )


def _parse_user_criteria(text: str) -> list[str]:
    m = re.search(
        r"(?:criteria[^:.]*|care\s+about|compare\s+(?:them\s+)?on)\s*:\s*(.+?)(?:[.]\s|[.]$|$)",
        text or "",
        re.I | re.S,
    )
    if not m:
        return []
    parts = re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+", m.group(1))
    return [p.strip(" .") for p in parts if p.strip(" .")][:8]


def _user_listed(intent: CompetitiveAnalysisIntent) -> list[str]:
    policy = intent.criteria_policy or ""
    if policy.startswith("user_listed:"):
        return [c.strip() for c in policy[len("user_listed:") :].split(";") if c.strip()]
    return []


def _subject_notes(subject: ComparisonSubject, sentences: list[str]) -> str:
    pattern = _NOTE_PATTERNS.get(subject.subject_id)
    if pattern is None:
        label = re.escape(subject.label.lower())
        pattern = re.compile(rf"\b{label}\b", re.I)
    return " ".join(s for s in sentences if pattern.search(s))


def parse_competitive_analysis_intent(
    task: str,
    background: str = "",
    constraints: str = "",
    time_horizon: str = "",
) -> CompetitiveAnalysisIntent:
    """Parse the task once into a typed intent; set ``needs_context`` when too thin."""
    task = (task or "").strip()
    labels = split_comparison_subjects(task)
    subjects: list[ComparisonSubject] = []
    confirm: list[str] = []
    for label in labels:
        subject, needs_confirm = canonical_subject(label)
        if subject.subject_id in {s.subject_id for s in subjects}:
            continue
        subjects.append(subject)
        if needs_confirm:
            confirm.append(
                f"You typed '{label}'. Project and program managers are not the same as a "
                "Product Manager; confirm this is the subject you want compared."
            )
    sentences = _sentences(background)
    for subject in subjects:
        subject.user_notes = _subject_notes(subject, sentences)

    slots, used = _parse_user_context(background)
    remainder = " ".join(s for i, s in enumerate(sentences) if i not in used)
    decision = _parse_decision(task, background, constraints, time_horizon)
    kind = "role" if subjects and all(s.kind == "role" for s in subjects) else "product"
    user_criteria = _parse_user_criteria(" ".join([task, background, constraints]))

    intent = CompetitiveAnalysisIntent(
        comparison_kind=kind,  # type: ignore[arg-type]
        subjects=subjects,
        decision=decision,
        user_context=slots,
        unparsed_remainder=remainder,
        original_task=task,
    )
    if user_criteria:
        intent.criteria_policy = "user_listed: " + "; ".join(user_criteria)
    background_present = bool((background or "").strip())
    constraints_present = bool((constraints or "").strip())
    return _finalise_status(intent, background_present, constraints_present, extra_questions=confirm)


def _slots_present(slots: UserContextSlots) -> bool:
    return any(
        [
            slots.company_stage, slots.business_model, slots.location, slots.product,
            slots.customer, slots.go_to_market, slots.current_team, slots.current_ownership,
        ]
    )


def _finalise_status(
    intent: CompetitiveAnalysisIntent,
    background_present: bool,
    constraints_present: bool,
    *,
    extra_questions: list[str] | None = None,
) -> CompetitiveAnalysisIntent:
    questions: list[str] = []
    if len(intent.subjects) < 2:
        questions.append("Which two or more subjects should be compared? Name them explicitly.")
    if not intent.decision.question:
        questions.append(THIN_CONTEXT_QUESTIONS[0])
    context_present = _slots_present(intent.user_context) or constraints_present or background_present
    if not context_present:
        questions.extend(THIN_CONTEXT_QUESTIONS[1:])
    if (
        intent.comparison_kind == "product" or not _is_catalog_pair(intent)
    ) and len(intent.subjects) >= 2 and not _user_listed(intent):
        questions.append("Which criteria should every subject be compared on?")
    questions.extend(extra_questions or [])
    blocking = [q for q in questions if q not in (extra_questions or [])]
    intent.status = "needs_context" if blocking else "ready"
    intent.unblock_questions = list(dict.fromkeys(questions))
    return intent


def rebuild_comparison_intent(
    base: CompetitiveAnalysisIntent | dict[str, Any],
    *,
    subject_labels: list[str] | None = None,
    decision_question: str | None = None,
    audience: str | None = None,
) -> CompetitiveAnalysisIntent:
    """Apply user corrections from the confirm panel, then recompute status."""
    intent = (
        base
        if isinstance(base, CompetitiveAnalysisIntent)
        else CompetitiveAnalysisIntent.model_validate(base)
    ).model_copy(deep=True)
    confirm: list[str] = []
    if subject_labels is not None:
        old = {s.subject_id: s for s in intent.subjects}
        subjects: list[ComparisonSubject] = []
        for label in subject_labels:
            if not label.strip():
                continue
            subject, needs_confirm = canonical_subject(label)
            if subject.subject_id in old:
                subject.user_notes = old[subject.subject_id].user_notes
            if subject.subject_id not in {s.subject_id for s in subjects}:
                subjects.append(subject)
            if needs_confirm:
                confirm.append(f"Confirm that '{label}' is the subject you want compared.")
        intent.subjects = subjects
        intent.comparison_kind = (
            "role" if subjects and all(s.kind == "role" for s in subjects) else "product"
        )
    if decision_question is not None:
        intent.decision.question = decision_question.strip()
    if audience is not None:
        intent.decision.audience = audience.strip()
    background_present = bool(intent.user_context.current_team or intent.unparsed_remainder)
    return _finalise_status(
        intent,
        background_present,
        bool(intent.decision.constraints),
        extra_questions=confirm,
    )


def comparison_needs_context(intent: CompetitiveAnalysisIntent | dict[str, Any]) -> bool:
    obj = (
        intent
        if isinstance(intent, CompetitiveAnalysisIntent)
        else CompetitiveAnalysisIntent.model_validate(intent)
    )
    return obj.status == "needs_context"


def format_context_echo(intent: CompetitiveAnalysisIntent) -> list[str]:
    ctx = intent.user_context
    lines: list[str] = []
    head = ", ".join(x for x in (ctx.company_stage, ctx.business_model, ctx.location) if x)
    if head:
        lines.append(head[:1].upper() + head[1:])
    if ctx.product or ctx.customer:
        lines.append(
            "Sells " + ctx.product + (f" to {ctx.customer}" if ctx.customer else "")
            if ctx.product
            else f"Customer: {ctx.customer}"
        )
    if ctx.go_to_market:
        lines.append(ctx.go_to_market[:1].upper() + ctx.go_to_market[1:])
    if ctx.current_team:
        lines.append(f"Team today: {ctx.current_team}")
    for item in ctx.current_ownership:
        lines.append(f"Ownership: {item}")
    return lines


def comparison_success_criteria(intent: CompetitiveAnalysisIntent) -> list[str]:
    names = " and ".join(s.label for s in intent.subjects) or "the named subjects"
    crit = [
        f"Both named subjects appear as columns: {names}",
        "Every selected criterion has a cell for every subject",
        "Every non-empty cell has a basis (user_supplied, public_source, domain_default, inference)",
        "User statements about current ownership appear as user_supplied and are not contradicted by a domain default",
        "Blank cells are listed as unknowns; nothing is filled in to complete the table",
        "Options address the decision and respect the stated constraints (no candidate names, no job advertisement)",
        "Leaves final approval to the human; nothing is hired, posted, or published",
    ]
    if intent.status == "needs_context":
        crit.insert(
            1,
            "Context is thin: return a labelled domain frame and the questions that unblock a real run",
        )
    return crit


# --------------------------------------------------------------------------- #
# Matrix builders
# --------------------------------------------------------------------------- #


def _is_catalog_pair(intent: CompetitiveAnalysisIntent) -> bool:
    ids = {s.subject_id for s in intent.subjects}
    return intent.comparison_kind == "role" and ids == {"pm", "pmm"}


def cell_id(cell: ComparisonCell) -> str:
    return f"{cell.subject_id}:{cell.criterion_id}"


def _evidence_user(claim: str) -> ComparisonEvidenceItem:
    return ComparisonEvidenceItem(claim=claim, source_title="User context", basis="user_supplied")


def _evidence_default(row: dict[str, str], text: str) -> ComparisonEvidenceItem:
    return ComparisonEvidenceItem(
        claim=f"Usual split ({row['label']}): {text}",
        source_title="Role catalog (domain default)",
        basis="domain_default",
    )


def build_domain_frame(intent: CompetitiveAnalysisIntent) -> list[ComparisonCell]:
    """Catalog rows only; every cell is a labelled domain default (section 19.3)."""
    if not _is_catalog_pair(intent):
        return []
    cells: list[ComparisonCell] = []
    for row in ROLE_CATALOG:
        for subject in intent.subjects:
            text = row[subject.subject_id]
            cells.append(
                ComparisonCell(
                    criterion_id=row["id"],
                    criterion_label=row["label"],
                    subject_id=subject.subject_id,
                    subject_label=subject.label,
                    value=text,
                    basis="domain_default",
                    evidence=[_evidence_default(row, text)],
                )
            )
    return cells


def _ownership_cell(subject: ComparisonSubject, intent: CompetitiveAnalysisIntent) -> ComparisonCell:
    crit_id, crit_label = OWNERSHIP_CRITERION
    ctx = intent.user_context
    alias = _NOTE_PATTERNS.get(subject.subject_id) or re.compile(rf"\b{re.escape(subject.label.lower())}\b", re.I)
    owned: list[tuple[str, str]] = []
    for item in ctx.current_ownership:
        obj, _, who = item.partition(": existing ")
        if alias.search(who or item):
            owned.append((obj.strip(), item))
    if owned:
        value = f"Existing {subject.label} covers: " + "; ".join(o for o, _ in owned) + " (user-stated)."
        evidence = [_evidence_user(src) for _, src in owned]
        return ComparisonCell(
            criterion_id=crit_id, criterion_label=crit_label, subject_id=subject.subject_id,
            subject_label=subject.label, value=value, basis="user_supplied", evidence=evidence,
        )
    for part in [p.strip() for p in ctx.current_team.split(",") if p.strip()]:
        if alias.search(part):
            value = (
                f"No {subject.label} on the team today (user-stated)."
                if re.match(r"^no\b", part, re.I)
                else f"Team today: {part} (user-stated)."
            )
            return ComparisonCell(
                criterion_id=crit_id, criterion_label=crit_label, subject_id=subject.subject_id,
                subject_label=subject.label, value=value, basis="user_supplied",
                evidence=[_evidence_user(part)],
            )
    return ComparisonCell(
        criterion_id=crit_id, criterion_label=crit_label, subject_id=subject.subject_id,
        subject_label=subject.label, value="", basis="unknown", evidence=[],
    )


def build_comparison_matrix(
    intent: CompetitiveAnalysisIntent,
    *,
    public_evidence: dict[str, list[ComparisonEvidenceItem]] | None = None,
    product_fills: dict[str, ComparisonEvidenceItem] | None = None,
) -> tuple[list[ComparisonCell], list[str]]:
    """Return (matrix, criteria_not_used). Unknown cells stay empty (section 21).

    ``product_fills`` maps ``subject_id:criterion_id`` → public_source evidence for
    product comparisons (Phase C). Role comparisons still use ``public_evidence`` by
    criterion id.
    """
    public_evidence = public_evidence or {}
    product_fills = product_fills or {}
    cells: list[ComparisonCell] = []
    if _is_catalog_pair(intent):
        for subject in intent.subjects:
            cells.append(_ownership_cell(subject, intent))
        for crit_id in HIRING_CRITERIA:
            row = CATALOG_BY_ID[crit_id]
            for subject in intent.subjects:
                if crit_id == "pricing":
                    # Pricing owner at this company was never stated: keep it blank.
                    cells.append(
                        ComparisonCell(
                            criterion_id=crit_id, criterion_label="Pricing owner at this company",
                            subject_id=subject.subject_id, subject_label=subject.label,
                            value="", basis="unknown", evidence=[],
                        )
                    )
                    continue
                text = row[subject.subject_id]
                cells.append(
                    ComparisonCell(
                        criterion_id=crit_id, criterion_label=row["label"],
                        subject_id=subject.subject_id, subject_label=subject.label,
                        value=text, basis="domain_default",
                        evidence=[_evidence_default(row, text)] + list(public_evidence.get(crit_id, [])),
                    )
                )
        not_used = [r["label"] for r in ROLE_CATALOG if r["id"] not in HIRING_CRITERIA]
        # Order rows by criterion then subject for readable tables.
        order = [OWNERSHIP_CRITERION[0]] + HIRING_CRITERIA
        cells.sort(key=lambda c: (order.index(c.criterion_id), [s.subject_id for s in intent.subjects].index(c.subject_id)))
        return cells, not_used

    for crit in _user_listed(intent):
        crit_id = re.sub(r"[^a-z0-9]+", "_", crit.lower()).strip("_") or "criterion"
        for subject in intent.subjects:
            fill = product_fills.get(f"{subject.subject_id}:{crit_id}")
            if fill and fill.source_url and fill.claim.strip():
                cells.append(
                    ComparisonCell(
                        criterion_id=crit_id,
                        criterion_label=crit,
                        subject_id=subject.subject_id,
                        subject_label=subject.label,
                        value=fill.claim.strip(),
                        basis="public_source",
                        evidence=[fill],
                    )
                )
            else:
                cells.append(
                    ComparisonCell(
                        criterion_id=crit_id, criterion_label=crit, subject_id=subject.subject_id,
                        subject_label=subject.label, value="", basis="unknown", evidence=[],
                    )
                )
    return cells, []


def build_demo_matrix(intent: CompetitiveAnalysisIntent) -> tuple[list[ComparisonCell], list[str]]:
    """Alias used by Demo Mode and tests; no network, no model."""
    return build_comparison_matrix(intent)


def _option_set(
    intent: CompetitiveAnalysisIntent, matrix: list[ComparisonCell]
) -> tuple[list[ComparisonOption], dict[str, list[str]], dict[str, str]]:
    deps: dict[str, list[str]] = {}
    blocked: dict[str, str] = {}
    ids = {cell_id(c) for c in matrix}
    if _is_catalog_pair(intent):
        owner_pm = any(c.subject_id == "pm" and c.criterion_id == "current_ownership" and c.basis == "user_supplied" for c in matrix)
        options = [
            ComparisonOption(
                option_id="hire_pmm",
                label="Hire the Product Marketer seat",
                implication="First owner for positioning, launch coordination, and enablement.",
                tradeoffs=[
                    "Roadmap depth stays with the existing product capacity."
                    + (" Release notes need an explicit handoff." if owner_pm else ""),
                ],
            ),
            ComparisonOption(
                option_id="hire_pm",
                label="Hire the Product Manager seat",
                implication="More product capacity on roadmap and discovery.",
                tradeoffs=[
                    "Messaging, enablement, and launch coordination stay where they sit today.",
                ],
            ),
            ComparisonOption(
                option_id="defer",
                label="Defer the hire",
                implication="Neither gap is staffed; the current ownership map stays as described.",
                tradeoffs=["Both the roadmap gap and the go-to-market gap remain open."],
            ),
        ]
        wanted = {
            "hire_pmm": ["pmm:current_ownership", "pmm:positioning", "pmm:launch", "pmm:enablement", "pmm:metrics"],
            "hire_pm": ["pm:current_ownership", "pm:roadmap", "pm:launch", "pm:metrics"],
            "defer": ["pm:current_ownership", "pmm:current_ownership"],
        }
        for oid, cids in wanted.items():
            deps[oid] = [c for c in cids if c in ids]
        for oid in ("hire_pmm", "hire_pm"):
            unknown = [cell_id(c) for c in matrix if cell_id(c) in deps[oid] and c.basis == "unknown"]
            if unknown:
                blocked[oid] = "Who feels the pain today, roadmap or win rate?"
        return options, deps, blocked

    options = []
    for subject in intent.subjects:
        oid = f"prioritise_{subject.subject_id}"
        options.append(
            ComparisonOption(
                option_id=oid,
                label=f"Prioritise {subject.label}",
                implication="Supported only by cells with a user_supplied or public_source basis.",
                tradeoffs=["Unknown cells must be researched before this option is defensible."],
            )
        )
        deps[oid] = [cell_id(c) for c in matrix if c.subject_id == subject.subject_id]
        if not any(c.basis != "unknown" for c in matrix if c.subject_id == subject.subject_id):
            blocked[oid] = "No filled cells yet; add facts or enable public search."
    options.append(
        ComparisonOption(
            option_id="defer",
            label="Defer the decision",
            implication="Gather the missing facts first.",
            tradeoffs=["No progress on the decision this cycle."],
        )
    )
    deps["defer"] = []
    return options, deps, blocked


def build_comparison_envelope(
    intent: CompetitiveAnalysisIntent | dict[str, Any],
    *,
    illustrative: bool = False,
    public_evidence: dict[str, list[ComparisonEvidenceItem]] | None = None,
    product_fills: dict[str, ComparisonEvidenceItem] | None = None,
    search_note: str | None = None,
    allowed_urls: list[str] | set[str] | None = None,
    suggested_subjects: list[str] | None = None,
    suggested_criteria: list[str] | None = None,
) -> ComparisonEnvelope:
    """Assemble the section 21 envelope in code from the typed intent."""
    intent = (
        intent
        if isinstance(intent, CompetitiveAnalysisIntent)
        else CompetitiveAnalysisIntent.model_validate(intent)
    )
    echo = format_context_echo(intent)
    if intent.status == "needs_context":
        frame = build_domain_frame(intent)
        return ComparisonEnvelope(
            comparison_kind=intent.comparison_kind,
            status="needs_context",
            intent_echo=intent,
            domain_frame_banner=DOMAIN_FRAME_BANNER if frame else (
                "No role catalog applies to these subjects. Provide the decision, the situation, "
                "and the criteria to compare."
            ),
            matrix=[],
            criteria_not_used=[],
            options=[],
            open_questions=list(intent.unblock_questions),
            illustrative=illustrative,
            extra={
                "domain_frame": [c.model_dump(mode="json") for c in frame],
                "context_echo": echo,
                "unknowns": list(intent.unblock_questions),
                "limitations": [
                    "Thin context: the contextual matrix is intentionally empty. "
                    "No company, headcount, or recommendation was invented."
                ],
                "suggested_subjects": list(suggested_subjects or []),
                "suggested_criteria": list(suggested_criteria or []),
            },
        )

    matrix, not_used = build_comparison_matrix(
        intent, public_evidence=public_evidence, product_fills=product_fills
    )
    options, deps, blocked = _option_set(intent, matrix)
    unknowns = sorted({f"{c.subject_label}: {c.criterion_label}" for c in matrix if c.basis == "unknown"})
    if _is_catalog_pair(intent):
        limitations = ["Domain-default cells describe the usual pattern, not your company."]
    else:
        limitations = [
            "Product cells are filled only from retrieved public pages or user-supplied facts; "
            "missing pages stay unknown."
        ]
    if search_note:
        limitations.append(search_note)
    url_list = sorted({*(allowed_urls or []), *(
        e.source_url
        for c in matrix
        for e in c.evidence
        if e.source_url
    )})
    extra: dict[str, Any] = {
        "context_echo": echo,
        "unknowns": unknowns,
        "option_cell_dependencies": deps,
        "blocked_options": blocked,
        "limitations": limitations,
        "shared_work": SHARED_WORK if _is_catalog_pair(intent) else [],
        "scores": "none (describe first; no numeric scores)",
        "allowed_urls": url_list,
        "suggested_subjects": list(suggested_subjects or []),
        "suggested_criteria": list(suggested_criteria or []),
    }
    if _is_catalog_pair(intent):
        extra["domain_notes"] = [
            {
                "criterion_id": "pricing",
                "subject_id": s.subject_id,
                "note": f"Usual pattern (not a fact about this company): {CATALOG_BY_ID['pricing'][s.subject_id]}",
            }
            for s in intent.subjects
        ]
        extra["conflicts"] = [
            "Messaging owner: hiring a marketer moves future messaging; it does not rewrite who writes release notes today.",
            "Roadmap versus launch: a second product manager deepens what gets built; a first marketer deepens how it is explained and sold.",
            "Metrics: the two roles report different numbers and are not averaged into one impact score.",
        ]
    return ComparisonEnvelope(
        comparison_kind=intent.comparison_kind,
        status="ready",
        intent_echo=intent,
        domain_frame_banner=None,
        matrix=matrix,
        criteria_not_used=not_used,
        options=options,
        open_questions=list(dict.fromkeys(blocked.values())),
        illustrative=illustrative,
        extra=extra,
    )
