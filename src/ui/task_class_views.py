"""Deliverable-tab views for job_search and competitive_analysis envelopes."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from src.models.competitive_analysis import ComparisonEnvelope
from src.models.job_search import JobSearchEnvelope
from src.services.task_class_render import (
    ILLUSTRATIVE_COMPARISON_BANNER,
    ILLUSTRATIVE_JOBS_BANNER,
    comparison_rows,
    excluded_reason_groups,
    job_summary_line,
    job_table_rows,
)


def render_job_envelope(raw: dict[str, Any]) -> None:
    env = JobSearchEnvelope.model_validate(raw)
    if env.illustrative:
        st.warning(ILLUSTRATIVE_JOBS_BANNER)
    e = env.query_echo
    st.markdown("#### Query echo")
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**Role family**  \n{e.role_family} (`{e.role_query}`)")
    c2.markdown(f"**Location**  \n{e.city or 'not applied'}" + (f" · {e.radius_km} km" if e.city else ""))
    exp = (
        f"{e.experience_min if e.experience_min is not None else '?'}–"
        f"{e.experience_max if e.experience_max is not None else '+'} years ({e.range_policy})"
        if e.experience_min is not None or e.experience_max is not None
        else "not applied"
    )
    c3.markdown(f"**Experience**  \n{exp}")
    c4, c5, c6 = st.columns(3)
    c4.markdown(
        "**Posted after**  \n"
        + (f"{e.posted_after[:10]} (last {e.posted_within_days} days)" if e.posted_after else "not applied")
    )
    c5.markdown(f"**Source**  \n{e.source_name or 'n/a'}")
    c6.markdown(f"**Retrieved**  \n{e.retrieved_at[:19].replace('T', ' ')} UTC")
    st.caption(job_summary_line(env))
    for failed in env.sources_failed:
        st.error(f"Source failed: {failed}")

    st.markdown("#### Included jobs")
    if env.jobs:
        rows = job_table_rows(env.jobs)
        st.dataframe(
            [{k: v for k, v in r.items() if k not in {"Reason"}} for r in rows],
            use_container_width=True,
            hide_index=True,
        )
        for job in env.jobs:
            with st.expander(f"{job.title} — {job.company_name} · {job.job_id}"):
                if job.description_completeness == "truncated":
                    st.caption("Description truncated at the source; not completed by the model.")
                st.write(job.job_description)
                st.caption("Why it matched: " + "; ".join(job.match_reasons))
                if job.apply_url:
                    st.markdown(f"[Source link]({job.apply_url})" if not env.illustrative else f"Link (illustrative): `{job.apply_url}`")
    else:
        st.info("No jobs met every filter. Exclusion counts above explain why; nothing was invented.")

    st.markdown("#### Needs review (experience not stated)")
    if env.needs_review:
        st.dataframe(
            [{k: r[k] for k in ("Job id", "Title", "Company", "Location", "Posted", "Experience")} for r in job_table_rows(env.needs_review)],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("None.")

    st.markdown("#### Excluded")
    groups = excluded_reason_groups(env)
    if groups:
        for code, jobs in sorted(groups.items()):
            with st.expander(f"{code.replace('_', ' ')} ({len(jobs)})"):
                for job in jobs:
                    st.markdown(
                        f"- `{job.job_id}` {job.title} — {job.company_name or 'unknown company'} "
                        f"· _{'; '.join(job.match_reasons[1:2])}_"
                    )
    else:
        st.caption("None.")
    if env.coverage_notes:
        with st.expander("Coverage notes"):
            for note in env.coverage_notes:
                st.markdown(f"- {note}")
    with st.expander("Raw JSON (job envelope)"):
        st.code(json.dumps(raw, indent=2, default=str), language="json")


def render_comparison_envelope(raw: dict[str, Any]) -> None:
    env = ComparisonEnvelope.model_validate(raw)
    extra = env.extra or {}
    if env.illustrative:
        st.warning(ILLUSTRATIVE_COMPARISON_BANNER)
    intent = env.intent_echo
    st.markdown("#### Context echo")
    if intent:
        st.markdown(f"**Subjects:** {', '.join(s.label for s in intent.subjects) or 'not parsed'}")
        st.markdown(f"**Decision:** {intent.decision.question or 'not stated'}")
        if intent.decision.audience:
            st.markdown(f"**Audience:** {intent.decision.audience}")
        if intent.decision.constraints:
            st.markdown("**Constraints:** " + "; ".join(intent.decision.constraints))
    for line in extra.get("context_echo") or []:
        st.markdown(f"- {line}")

    if env.status == "needs_context":
        st.warning("Status: **needs context**. The contextual matrix is intentionally empty.")
        if env.domain_frame_banner:
            st.info(env.domain_frame_banner)
        frame = extra.get("domain_frame") or []
        if frame:
            subjects: list[str] = []
            for cell in frame:
                if cell["subject_label"] not in subjects:
                    subjects.append(cell["subject_label"])
            by_crit: dict[str, dict[str, str]] = {}
            for cell in frame:
                by_crit.setdefault(cell["criterion_label"], {})[cell["subject_label"]] = cell["value"]
            st.dataframe(
                [{"Criterion": c, **{f"{s} (domain default)": v.get(s, "") for s in subjects}} for c, v in by_crit.items()],
                use_container_width=True,
                hide_index=True,
            )
        st.markdown("**Questions that unblock a real run**")
        for q in env.open_questions:
            st.markdown(f"- {q}")
    else:
        st.markdown("#### Comparison matrix")
        headers, rows = comparison_rows(env)
        if rows:
            st.dataframe(
                [dict(zip(headers, r)) for r in rows], use_container_width=True, hide_index=True
            )
            st.caption("Basis is shown in brackets: user_supplied, public_source, domain_default, inference. Blank = unknown.")
        if env.criteria_not_used:
            st.caption("Criteria not used: " + ", ".join(env.criteria_not_used))
        if extra.get("conflicts"):
            st.markdown("**Tensions to weigh**")
            for c in extra["conflicts"]:
                st.markdown(f"- {c}")
        st.markdown("#### Options for the decision")
        deps, blocked = extra.get("option_cell_dependencies") or {}, extra.get("blocked_options") or {}
        for opt in env.options:
            with st.expander(opt.label, expanded=True):
                st.write(opt.implication)
                for t in opt.tradeoffs:
                    st.markdown(f"- Stays uncovered: {t}")
                if deps.get(opt.option_id):
                    st.caption("Depends on cells: " + ", ".join(deps[opt.option_id]))
                if opt.option_id in blocked:
                    st.warning(f"blocked_by_unknown: {blocked[opt.option_id]}")
        if extra.get("unknowns"):
            st.markdown("**Unknowns (left blank on purpose)**")
            for u in extra["unknowns"]:
                st.markdown(f"- {u}")
    for lim in extra.get("limitations") or []:
        st.caption(lim)
    with st.expander("Raw JSON (comparison envelope)"):
        st.code(json.dumps(raw, indent=2, default=str), language="json")
