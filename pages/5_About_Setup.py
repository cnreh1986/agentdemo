"""About, setup status, safety notes, workshop metrics."""

from __future__ import annotations

import streamlit as st

from src.config.settings import get_settings
from src.ui.components import inject_styles, logo_path, render_mode_status

st.set_page_config(page_title="About & Setup", page_icon=logo_path(), layout="wide")
inject_styles()
settings = get_settings()

st.title("About & Setup")
st.markdown(
    """
### Personal AI Workforce Studio
Workshop learning application that demonstrates a transparent multi-agent workforce.

**Safety**
- No emails, calendar changes, purchases, or other external side effects in the MVP.
- Demo Mode never calls a model provider.
- Live Mode sends task context to your configured provider — configure keys via environment or Streamlit secrets.
- Do not submit confidential or sensitive information.
- Human approval is separate from LLM reviewer approval.
- Job search uses SerpAPI Google Jobs only (no Naukri/LinkedIn scraping), never applies to a job, and never invents listings. Demo Mode uses labelled fixtures.
"""
)

st.subheader("Provider status")
render_mode_status("demo", settings)
st.code(
    f"""model={settings.llm_model}
provider={settings.provider_display_name}
llm_credentials={'configured' if settings.has_llm_credentials else 'missing'}
search={'configured' if settings.search_configured else 'not configured'}
jobs_search={'SerpAPI configured' if settings.jobs_search_configured else 'SerpAPI not configured (Live job_search blocked; Demo Mode unaffected)'}
max_revisions={settings.max_revisions}
persistence={settings.persistence_enabled}
""",
    language="text",
)

st.subheader("Local workshop metrics")
st.caption("Counts only — no attendee personal information is stored.")
try:
    from src.persistence.repositories import RunRepository

    metrics = RunRepository().metrics()
    c1, c2, c3 = st.columns(3)
    c1.metric("Runs started", metrics.get("runs_started", 0))
    c2.metric("Runs completed/failed", metrics.get("runs_completed", 0))
    c3.metric("Exports downloaded", metrics.get("exports_downloaded", 0))
except Exception as exc:  # noqa: BLE001
    st.info(f"Metrics unavailable: {exc}")

st.subheader("Architecture")
st.write("See `ARCHITECTURE.md` and `IMPLEMENTATION_PLAN.md` in the repository root.")
