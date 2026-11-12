"""Run history — local SQLite persistence."""

from __future__ import annotations

import streamlit as st

from src.config.settings import get_settings
from src.ui.components import inject_styles, logo_path
from src.ui.output_views import render_agent_inspector, render_output_tabs
from src.ui.workflow_view import render_event_feed, render_pipeline

st.set_page_config(page_title="Run History", page_icon=logo_path(), layout="wide")
inject_styles()
settings = get_settings()
st.title("Run History")

if not settings.persistence_enabled:
    st.warning("Persistence is disabled (`WORKFORCE_PERSISTENCE_ENABLED=false`).")
    st.stop()

try:
    from src.persistence.repositories import RunRepository

    repo = RunRepository()
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not open local history database: {exc}")
    st.info("The studio still works in ephemeral session mode.")
    st.stop()

runs = repo.list_runs()
if not runs:
    st.info("No persisted runs yet. Complete a workforce run in Workforce Studio.")
else:
    labels = {
        r["id"]: f"{r['created_at'][:19]} · {r['mode']} · {r['status']} · {r['task'][:60]}"
        for r in runs
    }
    choice = st.selectbox("Previous runs", options=list(labels.keys()), format_func=lambda i: labels[i])
    state = repo.get_run(choice)
    if state:
        st.caption("Read-only inspection mode")
        render_pipeline(state)
        render_event_feed(state)
        render_output_tabs(state)
        render_agent_inspector(state)

st.divider()
if st.checkbox("I understand this permanently deletes local history"):
    if st.button("Clear local history", type="primary"):
        repo.clear_all()
        st.success("Local history cleared.")
        st.rerun()
