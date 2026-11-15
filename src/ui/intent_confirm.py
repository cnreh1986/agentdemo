"""Interpreted-task confirmation panel (shown before Run Workforce)."""

from __future__ import annotations

import hashlib
from typing import Any

import streamlit as st

from src.config.settings import Settings
from src.services.comparison_intent import (
    format_context_echo,
    parse_competitive_analysis_intent,
    rebuild_comparison_intent,
)
from src.services.job_intent import classify_task_class, intent_from_fields, parse_job_search_intent


def render_intent_confirm(
    task: str,
    background: str,
    constraints: str,
    time_horizon: str,
    *,
    mode: str,
    settings: Settings,
) -> dict[str, Any]:
    """Show interpreted filters / context and return the (possibly corrected) intent.

    Returns ``{"task_class", "job_intent", "comparison_intent", "blocked"}``. Intents are
    JSON-ready dicts; ``blocked`` is a message when the run must not start.
    """
    task_class = classify_task_class(task, background, constraints)
    out: dict[str, Any] = {
        "task_class": task_class,
        "job_intent": None,
        "comparison_intent": None,
        "blocked": None,
    }
    if task_class == "briefing":
        return out
    key = hashlib.md5("|".join([task, background, constraints, time_horizon]).encode()).hexdigest()[:8]

    with st.container(border=True):
        if task_class == "job_search":
            _render_job_panel(task, background, constraints, key, mode, settings, out)
        else:
            _render_comparison_panel(
                task, background, constraints, time_horizon, key, mode, settings, out
            )
    return out


def _render_job_panel(
    task: str, background: str, constraints: str, key: str, mode: str, settings: Settings, out: dict[str, Any]
) -> None:
    base = parse_job_search_intent(task, background, constraints)
    st.markdown("**Interpreted as: job search.** Confirm or correct the filters before you run.")
    c1, c2 = st.columns(2)
    role = c1.text_input("Role", value=base.role_query, key=f"ji_role_{key}")
    city = c2.text_input("City", value=base.location.city, key=f"ji_city_{key}")
    c3, c4, c5, c6 = st.columns(4)
    apply_exp = c3.checkbox(
        "Apply experience filter",
        value=base.experience.min_years is not None or base.experience.max_years is not None,
        key=f"ji_expon_{key}",
    )
    min_y = c4.number_input("Min years", 0, 40, int(base.experience.min_years or 0), key=f"ji_min_{key}")
    max_y = c5.number_input("Max years", 0, 50, int(base.experience.max_years or 10), key=f"ji_max_{key}")
    days = c6.number_input(
        "Posted within (days, 0 = off)", 0, 90, int(base.posted_within_days or 0), key=f"ji_days_{key}"
    )
    remote = st.checkbox("Accept remote / hybrid", value=base.location.accept_remote, key=f"ji_remote_{key}")
    intent = intent_from_fields(
        base,
        role_query=role,
        city=city,
        min_years=int(min_y) if apply_exp else None,
        max_years=int(max_y) if apply_exp else None,
        clear_experience=not apply_exp,
        posted_within_days=int(days) if days else None,
        clear_recency=not days,
        accept_remote=remote,
    )
    st.caption(
        f"Role family: `{intent.role_family}` · Location: {intent.location.city or 'not applied'}"
        f"{', ' + intent.location.country_code if intent.location.city else ''} "
        f"(radius {intent.location.radius_km} km) · Experience: "
        + (
            f"{intent.experience.min_years}-{intent.experience.max_years} years (overlap)"
            if intent.experience.min_years is not None or intent.experience.max_years is not None
            else "not applied"
        )
        + " · Recency: "
        + (f"last {intent.posted_within_days} days" if intent.posted_within_days else "not applied")
    )
    if intent.open_filters:
        st.warning("Not applied (not stated or turned off): " + ", ".join(intent.open_filters))
    if intent.unparsed_remainder:
        st.caption(f"Extra keywords noticed: {intent.unparsed_remainder}")
    if mode == "demo":
        st.info("Demo Mode: illustrative fixtures with fake ids run through these filters. No search is made.")
    elif not settings.jobs_search_configured:
        message = (
            "Live job search needs SERPAPI_API_KEY (SerpAPI Google Jobs). "
            "Add it and restart, or switch to Demo Mode. The app will not invent listings."
        )
        st.error(message)
        out["blocked"] = message
    else:
        st.info("Live Mode: SerpAPI Google Jobs will be queried with these filters; rows are filtered in code.")
    out["job_intent"] = intent.model_dump(mode="json")


def _render_comparison_panel(
    task: str,
    background: str,
    constraints: str,
    time_horizon: str,
    key: str,
    mode: str,
    settings: Settings,
    out: dict[str, Any],
) -> None:
    base = parse_competitive_analysis_intent(task, background, constraints, time_horizon)
    st.markdown("**Interpreted as: competitive analysis.** Check the subjects, decision, and context echo.")
    subjects = st.text_input(
        "Subjects (comma separated)",
        value=", ".join(s.label for s in base.subjects),
        key=f"ci_subjects_{key}",
    )
    decision = st.text_area("Decision this answers", value=base.decision.question, height=70, key=f"ci_decision_{key}")
    audience = st.text_input("Audience", value=base.decision.audience, key=f"ci_audience_{key}")
    intent = rebuild_comparison_intent(
        base,
        subject_labels=[s.strip() for s in subjects.split(",") if s.strip()],
        decision_question=decision,
        audience=audience,
    )
    lines = format_context_echo(intent)
    if lines:
        st.markdown("**Context echo**")
        for line in lines:
            st.markdown(f"- {line}")
    if intent.decision.constraints:
        st.markdown("**Constraints:** " + "; ".join(intent.decision.constraints))
    if intent.status == "needs_context":
        st.warning(
            "Context is thin, so the run will return a labelled domain frame and these questions "
            "instead of a company analysis:\n- " + "\n- ".join(intent.unblock_questions)
        )
    else:
        st.success("Context looks sufficient for a contextual comparison.")
    if mode == "live":
        st.info("Live Mode sends this context to your configured model provider. Avoid confidential details.")
        if not settings.search_configured:
            if intent.comparison_kind == "product":
                st.warning(
                    "Firecrawl is not configured. Product comparison cells will stay **unknown** "
                    "(no invented features or pricing). Set FIRECRAWL_API_KEY for public-source fill, "
                    "or use Demo Mode for an illustrative matrix."
                )
            else:
                st.warning(
                    "Firecrawl is not configured. Role domain-default cells will be labelled as model "
                    "knowledge; user-supplied ownership still stands. Set FIRECRAWL_API_KEY to attach "
                    "public pages, or use Demo Mode."
                )
        else:
            st.caption(
                "Live public sources use Firecrawl: short per-criterion queries; missing pages stay unknown."
            )
    else:
        st.info(
            "Demo Mode: no model or network calls; domain-default / illustrative public_source cells "
            "are labelled as such."
        )
    out["comparison_intent"] = intent.model_dump(mode="json")
