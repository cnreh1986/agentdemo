"""Workshop landing page content for app.py."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.ui.components import EDITION_LINE, logo_path

_ROOT = Path(__file__).resolve().parents[2]
_LANDING_ASSETS = _ROOT / "assets" / "landing"

_FEATURES = [
    ("Two execution modes", "Demo (deterministic fixtures, no network) and Live LLM (your configured provider via LiteLLM)."),
    ("Task workspace", "Type an objective, load a sample, or load a saved template from Task Manager."),
    ("Run Workforce", "Starts the pipeline: Orchestrator → Research → Planning → Execution → Reviewer → Human Approval."),
    ("Opt-in auto-approve", "Session checkbox (off by default) to approve a clean finished run without an extra click; still recorded as a human-origin decision in the feed."),
    ("Pause / Start", "Pause after the current stage; Start resumes the same run when status is paused."),
    ("Agent Activity overlay", "Focused view of which agent is running, what it does, and handoff summaries."),
    ("Pipeline, activity feed, and agent inspector", "Status text, events, and input/output packets per agent."),
    ("Output tabs", "Research, Plan, Deliverable, Review, Run Log (plus raw JSON expanders for technical attendees)."),
    ("Mandatory human gate", "Approve, Request Revision, or Reject. The Reviewer never marks a run human-approved."),
    ("Downloads", "Markdown briefing, JSON bundle, ZIP, and Research as Word (.docx)."),
    ("Task Manager", "Create, update, and delete reusable task templates."),
    ("Run History", "Reopen past runs from local SQLite (when persistence is enabled)."),
    ("Agent Lab", "Inspect and session-override agent system prompts."),
    ("About & Setup", "Provider readiness, safety notes, workshop metrics."),
]

_PAGES = [
    ("Workforce Studio", "Primary workshop screen: mode, task form, run, overlay, outputs, approval, downloads"),
    ("Task Manager", "Browse system samples; create / edit / delete your saved templates"),
    ("Run History", "List and reopen persisted runs; clear local DB if needed"),
    ("Agent Lab", "Read default prompts; apply session-only overrides for experiments"),
    ("About & Setup", "Product summary, provider status, safety, local metrics"),
]

_WALKTHROUGH = [
    "Open the app (local URL from `streamlit run app.py`).",
    "Choose **Demo Mode** (default) or configure credentials and select **Live LLM Mode**.",
    "Load a sample or saved task, or type your own objective. Optionally expand context, constraints, time horizon, and output format.",
    "Click **Run Workforce**. Watch the Agent Activity overlay and pipeline update as each stage completes.",
    "Inspect Research / Plan / Deliverable / Review tabs and the agent inspector.",
    "At **Human approval required**, choose **Approve**, **Request Revision** (needs a short instruction), or **Reject**.",
    "Download the outputs you need.",
    "Use **New Task** to clear the form, **Task Manager** to save templates, and **Run History** to reopen earlier runs.",
]

_SCREENSHOTS = [
    (
        "01_workforce_studio.png",
        "Workforce Studio — task workspace",
        "Mode selector, task / objective field, sample or saved-task picker, and Run Workforce / New Task / Reset.",
    ),
    (
        "02_agent_activity.png",
        "Agent Activity / pipeline",
        "While or after a run: Agent Activity overlay or Workforce overview with pipeline chips, activity feed, and current stage.",
    ),
    (
        "03_human_approval.png",
        "Human approval",
        "When status is awaiting human approval: Approve, Request Revision, and Reject — reviewer approval is not enough on its own.",
    ),
    (
        "04_outputs_downloads.png",
        "Outputs and downloads",
        "Research / Plan / Deliverable / Review tabs and download buttons for Markdown, JSON, ZIP, and Research Word.",
    ),
]

_FAQS = [
    (
        "What is the difference between Demo Mode and Live Mode?",
        "**Demo Mode** uses built-in illustrative fixtures. No API key and no live model or search calls. "
        "**Live LLM Mode** sends your task context to the configured model (default `openai/gpt-4o-mini` via LiteLLM). "
        "Live Mode requires provider credentials.",
    ),
    (
        "Do I need an API key to try the workshop?",
        "No. Start in Demo Mode. Add `OPENAI_API_KEY` (or the matching provider key) only when you want Live Mode.",
    ),
    (
        "Does the Reviewer approve the work for me?",
        "No. The Reviewer scores quality and may request a bounded revision. **You** must Approve, Request Revision, or Reject. "
        "Reviewer “approved” never sets the run to human-approved.",
    ),
    (
        "Can this app send email, update my calendar, or buy something?",
        "No. The MVP has no external side effects. Outputs are drafts for your review and download.",
    ),
    (
        "Where are runs and tasks saved?",
        "When persistence is enabled, runs go to local SQLite under `data/` (e.g. `data/workforce.db`). "
        "Saved task templates are JSON files under `data/tasks/`. On Streamlit Community Cloud, `data/` can reset on redeploy — "
        "fine for workshops, not durable storage.",
    ),
    (
        "What is Task Manager vs Workforce Studio?",
        "**Task Manager** stores reusable templates. **Workforce Studio** is where you run the workforce. "
        "Load a saved or sample task into the Studio form, then click Run Workforce.",
    ),
    (
        "How do I clear a run or start over?",
        "Use **New Task** to clear the form and current run state, or **Reset** (with confirm if a run is active / awaiting approval). "
        "Run History can clear the local database if needed.",
    ),
    (
        "What is the revision limit?",
        "By default the app allows one automatic reviewer-driven revision (`WORKFORCE_MAX_REVISIONS`). "
        "After that, the run pauses for your human decision even if the reviewer still wants changes.",
    ),
    (
        "Is live web search required?",
        "No. Optional Firecrawl search uses `FIRECRAWL_API_KEY`. Without it, Live research is labelled as model knowledge / "
        "not live-verified and must not invent fake URLs. Demo Mode never implies live web research.",
    ),
    (
        "Can I change agent prompts?",
        "Yes, on **Agent Lab** — edits apply to the current Streamlit session only and are not written as secrets or permanent config.",
    ),
    (
        "The page feels frozen while agents run. Is that expected?",
        "Streamlit still processes the run in the page script. Use the Agent Activity overlay to follow progress. "
        "**Pause** stops after the current stage; **Start** resumes. Schedule-for-later is covered as a design note in "
        "`enhancement.md`, not as a guaranteed UI control.",
    ),
]


def render_landing_page() -> None:
    """Render the workshop landing / home experience."""
    st.markdown('<div class="landing-page">', unsafe_allow_html=True)

    # Hero — single self-contained card (no split open/close div around widgets)
    if Path(logo_path()).is_file():
        st.image(logo_path(), width=140)
    st.markdown(
        f"""
        <div class="landing-hero">
          <div class="edition-line">{EDITION_LINE}</div>
          <div class="landing-brand">Personal AI Workforce Studio</div>
          <div class="landing-tagline">From AI Assistant to Agentic AI That Gets Work Done</div>
          <p class="landing-lede">
            A Streamlit workshop app that shows how a coordinated team of specialised AI agents can
            research, plan, create, and challenge work — then pause for <strong>your</strong> approval.
            You submit a plain-language task; the Orchestrator and four specialists run in a visible
            pipeline; nothing consequential happens outside the app until you decide.
          </p>
          <p class="landing-lede">
            <strong>Demo Mode</strong> works offline with no API keys.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3, _ = st.columns([1.4, 1.2, 1.2, 2])
    with c1:
        if st.button("Open Workforce Studio", type="primary", use_container_width=True):
            st.switch_page("pages/2_Workforce_Studio.py")
    with c2:
        if st.button("Task Manager", use_container_width=True):
            st.switch_page("pages/1_Task_Manager.py")
    with c3:
        if st.button("About & Setup", use_container_width=True):
            st.switch_page("pages/5_About_Setup.py")

    # What you get
    st.markdown("## What you get")
    for title, body in _FEATURES:
        st.markdown(f"- **{title}** — {body}")
    st.markdown(
        '<div class="landing-safety">'
        "<strong>Safety boundary:</strong> the app does not send emails, change calendars, "
        "make purchases, or take other external side effects. It produces drafts and "
        "recommendations for human review."
        "</div>",
        unsafe_allow_html=True,
    )

    # Pages
    st.markdown("## Pages at a glance")
    st.dataframe(
        [{"Page": name, "What it is for": desc} for name, desc in _PAGES],
        hide_index=True,
        use_container_width=True,
    )

    # Walkthrough
    st.markdown("## Workshop walkthrough")
    for i, step in enumerate(_WALKTHROUGH, start=1):
        st.markdown(f"{i}. {step}")

    # Flowchart
    st.markdown("## User flowchart")
    st.markdown(
        """
```mermaid
flowchart TD
  openApp[Open app]
  pickMode[Choose Demo or Live]
  enterTask[Enter or load task]
  runWF[Run Workforce]
  agents[Orchestrator Research Planning Execution Reviewer]
  awaitHuman[Await human approval]
  decide{Approve Revise or Reject}
  done[Download outputs]
  openApp --> pickMode --> enterTask --> runWF --> agents --> awaitHuman --> decide
  decide -->|Approve or Reject| done
  decide -->|Request Revision| agents
```
        """
    )
    st.caption(
        "Reviewer may request one bounded automatic revision before the human gate. "
        "Live Mode is blocked with a clear error if credentials are missing — never a silent Demo fallback."
    )

    # Product screenshots
    st.markdown("## Product Screenshots")
    for filename, title, caption in _SCREENSHOTS:
        path = _LANDING_ASSETS / filename
        st.markdown(f"### {title}")
        if path.is_file():
            st.markdown('<div class="landing-shot">', unsafe_allow_html=True)
            st.image(str(path), width=520)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info(f"Screenshot not found: `{filename}` — {caption}")
        st.caption(caption)

    # FAQ
    st.markdown("## FAQ")
    for question, answer in _FAQS:
        with st.expander(question):
            st.markdown(answer)

    # Quick start
    st.markdown("## Quick start")
    st.code(
        "\n".join(
            [
                "/opt/homebrew/bin/python3.12 -m venv .venv",
                "source .venv/bin/activate          # Windows: .venv\\Scripts\\activate",
                "pip install -r requirements.txt",
                "cp .env.example .env",
                "streamlit run app.py",
            ]
        ),
        language="bash",
    )
    st.markdown(
        "Open the URL Streamlit prints (typically http://localhost:8501). "
        "Deploy on [Streamlit Community Cloud](https://share.streamlit.io) with main file `app.py` — "
        "see [README.md](README.md) for secrets and limits."
    )

    # More reading
    st.markdown("## More reading")
    st.markdown(
        """
| Document | Contents |
| --- | --- |
| [README.md](README.md) | Setup, modes, workshop flow, troubleshooting |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical layout |
| [Personal_AI_Workforce_Studio_PRD.md](Personal_AI_Workforce_Studio_PRD.md) | Full product requirements |
| [enhancement.md](enhancement.md) | Planned UX enhancements (design notes) |
| [landingPage.md](landingPage.md) | Landing guide source |
        """
    )

    st.markdown("</div>", unsafe_allow_html=True)
