"""Personal AI Workforce Studio — entry point / home redirect."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Personal AI Workforce Studio",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.switch_page("pages/2_Workforce_Studio.py")
