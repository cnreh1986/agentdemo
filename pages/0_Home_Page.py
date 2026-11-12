"""Workshop landing / home page."""

from __future__ import annotations

import streamlit as st

from src.ui.components import inject_styles, logo_path
from src.ui.landing import render_landing_page

st.set_page_config(
    page_title="Personal AI Workforce Studio",
    page_icon=logo_path(),
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_styles(show_home_link=False, show_page_brand=False)
render_landing_page()
