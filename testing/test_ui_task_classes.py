"""Streamlit AppTest checks for the interpreted-task panel and Deliverable tables.

``st.page_link`` is stubbed because AppTest cannot resolve ``pages/`` links (the same reason
tests/test_ui_smoke.py fails on a clean checkout); everything else is the real page.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest

from src.config.samples import SAMPLE_COMPARE_THIN_LABEL, SAMPLE_JOBS_LABEL

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = f"""
import streamlit as st
st.page_link = lambda *a, **k: None
exec(compile(open(r"{ROOT / 'pages' / '2_Workforce_Studio.py'}").read(), "studio", "exec"))
"""


def _app() -> AppTest:
    at = AppTest.from_string(SCRIPT, default_timeout=60)
    at.run()
    assert not at.exception
    return at


def test_job_sample_shows_interpreted_filters_and_runs_in_demo():
    at = _app()
    at.selectbox[0].select(SAMPLE_JOBS_LABEL).run()
    assert not at.exception
    assert any("Interpreted as: job search" in m.value for m in at.markdown)
    labels = {n.label for n in at.number_input}
    assert {"Min years", "Max years"} <= labels
    next(b for b in at.button if b.label == "Run Workforce").click().run(timeout=120)
    assert not at.exception
    state = at.session_state["run_state"]
    assert state["status"] == "AWAITING_HUMAN_APPROVAL"
    assert state["job_envelope"]["jobs"]


def test_thin_comparison_shows_needs_context_warning():
    at = _app()
    at.selectbox[0].select(SAMPLE_COMPARE_THIN_LABEL).run()
    assert not at.exception
    assert any("Context is thin" in w.value for w in at.warning)
    next(b for b in at.button if b.label == "Run Workforce").click().run(timeout=120)
    assert at.session_state["run_state"]["comparison_envelope"]["status"] == "needs_context"


def test_briefing_task_has_no_interpreted_panel():
    at = _app()
    at.selectbox[0].select("Plan my next productive week.").run()
    assert not any("Interpreted as" in m.value for m in at.markdown)
