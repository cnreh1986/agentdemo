"""Inspect and session-override agent prompts."""

from __future__ import annotations

import streamlit as st

from src.config.prompts import PROMPTS
from src.ui.agent_cards import AGENTS
from src.ui.components import inject_styles

st.set_page_config(page_title="Agent Lab", page_icon="🧪", layout="wide")
inject_styles()
st.title("Agent Lab")
st.write(
    "Inspect system instructions for each agent. Edits apply to the current Streamlit session only."
)

if "prompt_overrides" not in st.session_state:
    st.session_state.prompt_overrides = {}

for agent in AGENTS:
    key = agent["key"]
    default = PROMPTS.get(key, "")
    with st.expander(f"{agent['icon']} {agent['name']}", expanded=False):
        st.write(agent["role"])
        edited = st.text_area(
            f"System prompt — {agent['name']}",
            value=st.session_state.prompt_overrides.get(key, default),
            height=180,
            key=f"prompt_{key}",
        )
        c1, c2 = st.columns(2)
        if c1.button(f"Apply session override — {agent['name']}"):
            st.session_state.prompt_overrides[key] = edited
            st.success("Session override saved. New runs will use this prompt.")
        if c2.button(f"Reset — {agent['name']}"):
            st.session_state.prompt_overrides.pop(key, None)
            st.rerun()

st.caption("Secrets must never be placed in prompts. Overrides are not persisted across restarts.")
