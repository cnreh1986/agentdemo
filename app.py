"""Personal AI Workforce Studio — entry point / home redirect."""

from __future__ import annotations

import streamlit as st

from src.ui.components import inject_styles, logo_path

st.set_page_config(
    page_title="Personal AI Workforce Studio",
    page_icon=logo_path(),
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_styles()
st.switch_page("pages/2_Workforce_Studio.py")
