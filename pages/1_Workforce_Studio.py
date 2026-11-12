"""Primary workshop page: task input, live run, outputs, approval."""

from __future__ import annotations

import copy

import streamlit as st

from src.config.samples import OUTPUT_FORMATS, SAMPLE_TASK_LABELS, SAMPLE_TASKS
from src.config.settings import get_settings
from src.config.validation import validate_task_input
from src.services.export_service import ExportService
from src.services.run_service import RunService
from src.ui.agent_cards import render_agent_cards
from src.ui.components import (
    inject_styles,
    render_header,
    render_mode_status,
    render_sensitive_warning,
)
from src.ui.output_views import render_agent_inspector, render_approval_panel, render_output_tabs
from src.ui.workflow_view import render_event_feed, render_pipeline

st.set_page_config(
    page_title="Workforce Studio",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_styles()
settings = get_settings()

for key, default in {
    "run_state": None,
    "run_in_progress": False,
    "task_text": "",
    "background_text": "",
    "constraints_text": "",
    "time_horizon_text": "",
    "output_format": "Briefing",
    "execution_mode": "demo",
    "prompt_overrides": {},
    "confirm_reset": False,
    "sample_task_selector": "(choose a sample)",
    "_loaded_sample": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def _start_new_task() -> None:
    """Clear form + run so the user can type a custom task."""
    st.session_state.task_text = ""
    st.session_state.background_text = ""
    st.session_state.constraints_text = ""
    st.session_state.time_horizon_text = ""
    st.session_state.output_format = "Briefing"
    st.session_state.sample_task_selector = "(choose a sample)"
    st.session_state._loaded_sample = None
    st.session_state.run_state = None
    st.session_state.run_in_progress = False
    st.session_state.confirm_reset = False



def _persist(state: dict) -> None:
    if not settings.persistence_enabled:
        return
    try:
        from src.persistence.repositories import RunRepository

        repo = RunRepository()
        repo.save_run(state)
        if state.get("status") in {"HUMAN_APPROVED", "HUMAN_REJECTED", "FAILED"}:
            repo.increment_metric("runs_completed")
    except Exception:
        # Persistence must not break the workshop demo
        pass


def _bump_export() -> None:
    if not settings.persistence_enabled:
        return
    try:
        from src.persistence.repositories import RunRepository

        RunRepository().increment_metric("exports_downloaded")
    except Exception:
        pass


render_header()
render_sensitive_warning()

mode = st.radio(
    "Execution mode",
    options=["demo", "live"],
    format_func=lambda m: "Demo Mode (default — no API key)" if m == "demo" else "Live LLM Mode",
    horizontal=True,
    key="execution_mode",
)
render_mode_status(mode, settings)

st.subheader("Task workspace")
sample = st.selectbox(
    "Sample task (optional)",
    options=["(choose a sample)"] + SAMPLE_TASK_LABELS,
    key="sample_task_selector",
)
if sample != "(choose a sample)" and st.session_state.get("_loaded_sample") != sample:
    packet = SAMPLE_TASKS[sample]
    st.session_state.task_text = packet["task"]
    st.session_state.background_text = packet["background"]
    st.session_state.constraints_text = packet["constraints"]
    st.session_state.time_horizon_text = packet["time_horizon"]
    st.session_state.output_format = packet["output_format"]
    st.session_state._loaded_sample = sample
    st.rerun()

st.text_area(
    "Task / objective (required)",
    key="task_text",
    height=100,
    placeholder="Describe the work you want the workforce to complete…",
)
st.caption("Type your own task above, or load a sample. Then click Run Workforce.")

c_run, c_new, c_reset, _ = st.columns([1.2, 1, 1, 2])
run_clicked = c_run.button(
    "Run Workforce",
    type="primary",
    disabled=st.session_state.run_in_progress,
    use_container_width=True,
)
new_task_clicked = c_new.button("New Task", use_container_width=True)
reset_clicked = c_reset.button("Reset", use_container_width=True)

if new_task_clicked:
    _start_new_task()
    st.rerun()

with st.expander("Optional context, constraints, and preferences"):
    st.text_area("Background / context", key="background_text", height=80)
    st.text_area(
        "Constraints (budget, time, audience, geography, format)",
        key="constraints_text",
        height=80,
    )
    st.text_input("Time horizon", key="time_horizon_text")
    st.selectbox("Output format", options=OUTPUT_FORMATS, key="output_format")

if reset_clicked:
    active = st.session_state.run_state and st.session_state.run_state.get("status") in {
        "AWAITING_HUMAN_APPROVAL",
        "TASK_RECEIVED",
        "RESEARCH_RUNNING",
        "PLANNING_RUNNING",
        "EXECUTION_RUNNING",
        "REVIEW_RUNNING",
        "REVISION_RUNNING",
    }
    if active:
        st.session_state.confirm_reset = True
    else:
        st.session_state.run_state = None
        st.session_state.run_in_progress = False
        st.rerun()

if st.session_state.confirm_reset:
    st.warning("A run is active or awaiting approval. Confirm reset?")
    if st.button("Confirm reset"):
        st.session_state.run_state = None
        st.session_state.run_in_progress = False
        st.session_state.confirm_reset = False
        st.rerun()
    if st.button("Cancel reset"):
        st.session_state.confirm_reset = False
        st.rerun()

if run_clicked and not st.session_state.run_in_progress:
    validation = validate_task_input(
        st.session_state.task_text,
        st.session_state.background_text,
        st.session_state.constraints_text,
        st.session_state.time_horizon_text,
        st.session_state.output_format,
    )
    if not validation.ok:
        for err in validation.errors:
            st.error(err)
    elif mode == "live" and not settings.has_llm_credentials:
        st.error(
            "Live LLM Mode is blocked until credentials are configured. "
            "Add OPENAI_API_KEY (or matching provider key) and restart. "
            "The app will not silently switch to Demo Mode."
        )
    else:
        st.session_state.run_in_progress = True
        progress = st.empty()
        status_box = st.status("Running workforce…", expanded=True)

        def on_update(state: dict) -> None:
            st.session_state.run_state = copy.deepcopy(state)
            stage = state.get("current_stage", "")
            completed = list(state.get("node_states", {}).values()).count("Completed")
            progress.progress(
                min(0.95, 0.12 * (1 + completed)),
                text=f"Stage: {stage} · status: {state.get('status')}",
            )
            if state.get("events"):
                status_box.write(state["events"][-1]["message"])

        try:
            service = RunService(prompt_overrides=st.session_state.prompt_overrides)
            if settings.persistence_enabled:
                try:
                    from src.persistence.repositories import RunRepository

                    RunRepository().increment_metric("runs_started")
                except Exception:
                    pass
            result = service.start_run(
                task=validation.task,
                background=validation.background,
                constraints=validation.constraints,
                time_horizon=validation.time_horizon,
                output_format=validation.output_format,
                mode=mode,
                on_update=on_update,
            )
            st.session_state.run_state = result
            _persist(result)
            status_box.update(label="Run ready for human approval", state="complete")
        except Exception as exc:  # noqa: BLE001
            status_box.update(label="Run failed", state="error")
            st.error(f"Run failed: {exc}")
            if st.session_state.run_state is None:
                st.session_state.run_state = {
                    "status": "FAILED",
                    "error": str(exc),
                    "events": [],
                    "node_states": {},
                }
            else:
                _persist(st.session_state.run_state)
        finally:
            st.session_state.run_in_progress = False
            progress.empty()

run_state = st.session_state.run_state

st.subheader("Workforce overview")
render_agent_cards(run_state)

left, right = st.columns([1.1, 1])
with left:
    st.subheader("Workflow")
    render_pipeline(run_state)
    st.subheader("Activity feed")
    render_event_feed(run_state)
with right:
    st.subheader("Current stage & inspector")
    if run_state:
        st.write(
            f"**Status:** `{run_state.get('status')}` · "
            f"**Stage:** `{run_state.get('current_stage')}` · "
            f"**Revisions:** {run_state.get('revision_count', 0)}/{run_state.get('max_revisions', 1)}"
        )
        if run_state.get("task_specification"):
            with st.expander("Task specification", expanded=False):
                st.json(run_state["task_specification"])
        if run_state.get("unresolved_issues"):
            st.warning("Unresolved issues:\n- " + "\n- ".join(run_state["unresolved_issues"]))
    render_agent_inspector(run_state)

st.subheader("Outputs")
render_output_tabs(run_state)

action = render_approval_panel(run_state)
if action and run_state:
    service = RunService(prompt_overrides=st.session_state.prompt_overrides)
    try:
        updated = service.apply_human_decision(
            run_state,
            decision=action["decision"],
            note=action.get("note") or "",
        )
        st.session_state.run_state = updated
        _persist(updated)
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))

if run_state and (run_state.get("deliverable") or run_state.get("research")):
    exporter = ExportService()
    st.subheader("Downloads")
    cols = st.columns(4)
    if run_state.get("deliverable"):
        md_name, md = exporter.markdown_briefing(run_state)
        json_name, js = exporter.json_bundle(run_state)
        zip_name, zbytes = exporter.zip_bundle(run_state)
        with cols[0]:
            if st.download_button(
                "Download Markdown",
                data=md,
                file_name=md_name,
                mime="text/markdown",
            ):
                _bump_export()
        with cols[1]:
            if st.download_button(
                "Download JSON bundle",
                data=js,
                file_name=json_name,
                mime="application/json",
            ):
                _bump_export()
        with cols[2]:
            if st.download_button(
                "Download ZIP",
                data=zbytes,
                file_name=zip_name,
                mime="application/zip",
            ):
                _bump_export()
    if run_state.get("research"):
        try:
            docx_name, docx_bytes = exporter.research_docx(run_state)
            with cols[3]:
                if st.download_button(
                    "Download Research (Word)",
                    data=docx_bytes,
                    file_name=docx_name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ):
                    _bump_export()
        except ValueError:
            pass
