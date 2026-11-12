"""Shared header and setup status."""

from __future__ import annotations

import streamlit as st

from src.config.settings import Settings
from src.ui.styles import APP_CSS, chip_class


def inject_styles() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)


def render_header() -> None:
    st.markdown(
        """
        <div class="main-header">
          <h1>Personal AI Workforce Studio</h1>
          <div class="tagline">From AI Assistant to Agentic AI That Gets Work Done</div>
          <div class="explainer">
            Give your task to a coordinated team of specialised AI agents. Watch them research,
            plan, create, challenge, and prepare a deliverable for <strong>your</strong> approval.
            This workshop app shows every handoff — it does not send emails, change calendars,
            or take other external actions.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sensitive_warning() -> None:
    st.markdown(
        """
        <div class="warn-box">
          <strong>Do not enter</strong> passwords, API keys, sensitive personal data, or confidential
          business information. Demo Mode keeps work local; Live LLM Mode sends prompts to your
          configured provider.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_mode_status(mode: str, settings: Settings) -> None:
    live_ready = settings.has_llm_credentials
    search_ready = settings.search_configured
    mode_chip = "chip-ok" if mode == "demo" else ("chip-ok" if live_ready else "chip-err")
    live_label = "ready" if live_ready else "missing credentials"
    search_label = "configured" if search_ready else "not configured (research unverified)"
    st.markdown(
        f"""
        <span class="status-chip {mode_chip}">Mode: {mode.upper()}</span>
        <span class="status-chip {chip_class('ok' if live_ready else 'wait')}">
          Live LLM: {settings.provider_display_name} / {settings.llm_model} — {live_label}
        </span>
        <span class="status-chip {chip_class('ok' if search_ready else 'wait')}">
          Search: {search_label}
        </span>
        """,
        unsafe_allow_html=True,
    )
    if mode == "live" and not live_ready:
        st.error(
            "Live LLM Mode needs provider credentials before a run can start. "
            "Set OPENAI_API_KEY (or the key for your model) in the environment or Streamlit secrets. "
            "The app will not silently switch to Demo Mode."
        )
    if mode == "live":
        st.info(
            "Live Mode sends your task text and context to the configured model provider. "
            "Model output is unverified unless a search adapter returns sources."
        )
