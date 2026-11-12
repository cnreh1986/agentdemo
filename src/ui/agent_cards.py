"""Agent roster cards."""

from __future__ import annotations

from typing import Any

import streamlit as st

from src.ui.styles import chip_class

AGENTS = [
    {
        "key": "orchestrator",
        "icon": "🧭",
        "name": "Orchestrator",
        "role": "Validates the task, creates the specification, and routes work.",
    },
    {
        "key": "research",
        "icon": "🔎",
        "name": "Research",
        "role": "Discovers themes, evidence gaps, and limitations.",
    },
    {
        "key": "planning",
        "icon": "🗺️",
        "name": "Planning",
        "role": "Turns findings into prioritised, timed actions.",
    },
    {
        "key": "execution",
        "icon": "📝",
        "name": "Execution",
        "role": "Creates the briefing or action-plan deliverable.",
    },
    {
        "key": "reviewer",
        "icon": "✅",
        "name": "Reviewer",
        "role": "Independently checks quality and may request revision.",
    },
]


def render_agent_cards(run_state: dict[str, Any] | None) -> None:
    node_states = (run_state or {}).get("node_states") or {}
    executions = (run_state or {}).get("agent_executions") or {}
    cols = st.columns(5)
    for col, agent in zip(cols, AGENTS):
        status = node_states.get(agent["key"], "Waiting")
        duration = None
        exec_key = agent["key"]
        if exec_key in executions:
            duration = executions[exec_key].get("duration_ms")
        elif agent["key"] == "execution" and "execution_revision" in executions:
            duration = executions["execution_revision"].get("duration_ms")
        css = "agent-card"
        if status == "Running":
            css += " active"
        elif status == "Completed":
            css += " done"
        elif status == "Failed":
            css += " fail"
        elif status == "Needs revision":
            css += " warn"
        duration_txt = f"{duration} ms" if duration is not None else "—"
        with col:
            st.markdown(
                f"""
                <div class="{css}">
                  <div>{agent['icon']} <strong>{agent['name']}</strong></div>
                  <div style="font-size:0.82rem;color:#475569;margin:0.35rem 0;">{agent['role']}</div>
                  <span class="status-chip {chip_class(status)}">{status}</span>
                  <span style="font-size:0.78rem;color:#64748B;">Duration: {duration_txt}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
