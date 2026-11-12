"""Personal AI Workforce Studio — multipage entry / navigation host."""

from __future__ import annotations

import streamlit as st

from src.ui.components import logo_path

st.set_page_config(
    page_title="Personal AI Workforce Studio",
    page_icon=logo_path(),
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation(
    [
        st.Page("pages/0_Home_Page.py", title="Home Page", default=True),
        st.Page("pages/1_Task_Manager.py", title="Task Manager"),
        st.Page("pages/2_Workforce_Studio.py", title="Workforce Studio"),
        st.Page("pages/3_Run_History.py", title="Run History"),
        st.Page("pages/4_Agent_Lab.py", title="Agent Lab"),
        st.Page("pages/5_About_Setup.py", title="About & Setup"),
    ]
)
pg.run()
