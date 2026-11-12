"""Pipeline visualisation and activity feed."""

from __future__ import annotations

from typing import Any

import streamlit as st

PIPELINE_LABELS = [
    ("orchestrator", "Orchestrator"),
    ("research", "Research"),
    ("planning", "Planning"),
    ("execution", "Execution"),
    ("reviewer", "Reviewer"),
    ("human_approval", "Human Approval"),
]


def render_pipeline(run_state: dict[str, Any] | None) -> None:
    node_states = (run_state or {}).get("node_states") or {}
    parts = ['<div class="pipeline"><span class="pipe-node">User Task</span><span>→</span>']
    for key, label in PIPELINE_LABELS:
        status = node_states.get(key, "Waiting")
        safe_status = status.replace(" ", "-")
        parts.append(
            f'<span class="pipe-node {safe_status}" title="{status}">{label}<br/>'
            f'<span style="font-weight:500;font-size:0.75rem;">{status}</span></span><span>→</span>'
        )
    parts.append('<span class="pipe-node">Final Output</span></div>')
    st.markdown("".join(parts), unsafe_allow_html=True)
    st.caption("Sequential MVP — one active stage at a time. Status uses text labels, not colour alone.")


def render_event_feed(run_state: dict[str, Any] | None, limit: int = 40) -> None:
    events = (run_state or {}).get("events") or []
    if not events:
        st.info("Activity feed will appear when you run the workforce.")
        return
    for event in reversed(events[-limit:]):
        ts = event.get("timestamp", "")[-12:-1] if event.get("timestamp") else ""
        stage = event.get("stage", "")
        message = event.get("message", "")
        status = event.get("status", "")
        duration = event.get("duration_ms")
        dur = f" · {duration} ms" if duration is not None else ""
        st.markdown(f"**{ts}** · `{stage}` · {status}{dur}  \n{message}")
