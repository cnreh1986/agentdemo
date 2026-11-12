"""Shared header and setup status."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st

from src.config.settings import Settings
from src.ui.styles import APP_CSS, chip_class

_ROOT = Path(__file__).resolve().parents[2]
LOGO_PATH = _ROOT / "assets" / "the_product_room_logo.jpg"
EDITION_LINE = "Product Room, 28/11/2026 Second Edition"
FOOTER_LINE = (
    "Thank you from Product Room Team — Nadia, Rachana, Atul, Venkat, Harmeet, Salman, Nadeem."
)


def logo_path() -> str:
    """Absolute path to The Product Room logo (for page_icon / st.logo / st.image)."""
    return str(LOGO_PATH)


def render_page_brand(*, show_home_link: bool = True, show_page_brand: bool = True) -> None:
    """Logo + edition line in the main content area (all pages)."""
    if show_home_link:
        st.page_link("pages/0_Home_Page.py", label="Home Page", icon=":material/home:")
    if not show_page_brand:
        return
    if LOGO_PATH.is_file():
        st.image(logo_path(), width=96)
    st.markdown(
        f'<div class="page-brand"><div class="edition-line">{EDITION_LINE}</div></div>',
        unsafe_allow_html=True,
    )


def render_page_footer() -> None:
    """Fixed thank-you footer on every page."""
    st.markdown(f'<div class="app-footer">{FOOTER_LINE}</div>', unsafe_allow_html=True)


def inject_styles(*, show_home_link: bool = True, show_page_brand: bool = True) -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)
    if LOGO_PATH.is_file():
        st.logo(logo_path(), size="large")
    render_page_brand(show_home_link=show_home_link, show_page_brand=show_page_brand)
    render_page_footer()


def queue_run_notice(
    message: str,
    *,
    level: str = "info",
    run_id: str | None = None,
) -> None:
    """Store one in-session completion notice (toast + dismissible banner)."""
    safe_level = level if level in {"info", "success", "warning", "error"} else "info"
    st.session_state.run_notice = {
        "message": message,
        "level": safe_level,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dismissed": False,
        "toast_shown": False,
    }


def render_run_notice() -> None:
    notice: dict[str, Any] | None = st.session_state.get("run_notice")
    if not notice or notice.get("dismissed"):
        return
    message = str(notice.get("message") or "")
    level = str(notice.get("level") or "info")
    if not notice.get("toast_shown"):
        st.toast(message)
        notice["toast_shown"] = True
        st.session_state.run_notice = notice
    st.markdown(
        f'<div class="run-notice {level}">{message}</div>',
        unsafe_allow_html=True,
    )
    if st.button("Dismiss notice", key="dismiss_run_notice"):
        notice["dismissed"] = True
        st.session_state.run_notice = notice
        st.rerun()


def render_header() -> None:
    # Logo + edition line already rendered by inject_styles / render_page_brand.
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
