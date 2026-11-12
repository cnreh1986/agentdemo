"""Streamlit AppTest smoke checks."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
STUDIO_PAGE = ROOT / "pages" / "1_Workforce_Studio.py"


def test_workforce_studio_loads_demo_mode():
    at = AppTest.from_file(str(STUDIO_PAGE), default_timeout=30)
    at.run()
    assert not at.exception
    assert at.radio[0].value == "demo"
    assert any("Personal AI Workforce Studio" in str(el.value) for el in at.markdown)


def test_sample_task_selector_present():
    at = AppTest.from_file(str(STUDIO_PAGE), default_timeout=30)
    at.run()
    assert not at.exception
    assert len(at.selectbox) >= 1
    labels = at.selectbox[0].options
    assert any("Plan my next productive week" in str(opt) for opt in labels)
