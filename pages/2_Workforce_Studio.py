"""Primary workshop page: task input, live run, outputs, approval."""

from __future__ import annotations

import copy

import streamlit as st

from src.config.samples import OUTPUT_FORMATS, SAMPLE_TASK_LABELS, SAMPLE_TASKS
from src.config.settings import get_settings
from src.config.validation import validate_task_input
from src.services.export_service import ExportService
from src.services.run_service import AUTO_APPROVE_NOTE, RunService
from src.ui.agent_activity_overlay import render_agent_activity_overlay
from src.ui.agent_cards import render_agent_cards
from src.ui.components import (
    inject_styles,
    logo_path,
    queue_run_notice,
    render_header,
    render_mode_status,
    render_run_notice,
    render_sensitive_warning,
)
from src.ui.output_views import render_agent_inspector, render_approval_panel, render_output_tabs
from src.ui.workflow_view import render_event_feed, render_pipeline

st.set_page_config(
    page_title="Workforce Studio",
    page_icon=logo_path(),
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_styles()
settings = get_settings()

for key, default in {
    "run_state": None,
    "run_in_progress": False,
    "run_continue": False,
    "ready_for_next_stage": False,
    "pause_requested": False,
    "auto_approve_enabled": False,
    "run_notice": None,
    "show_agent_overlay": False,
    "agent_overlay_minimized": False,
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

_ACTIVE_STATUSES = {
    "AWAITING_HUMAN_APPROVAL",
    "PAUSED",
    "TASK_RECEIVED",
    "TASK_VALIDATED",
    "SPECIFICATION_CREATED",
    "RESEARCH_RUNNING",
    "PLANNING_RUNNING",
    "EXECUTION_RUNNING",
    "REVIEW_RUNNING",
    "REVISION_RUNNING",
}


def _clear_overlay_flags() -> None:
    st.session_state.show_agent_overlay = False
    st.session_state.agent_overlay_minimized = False


def _start_new_task() -> None:
    """Clear form + run so the user can type a custom task. Must run via on_click."""
    st.session_state.task_text = ""
    st.session_state.background_text = ""
    st.session_state.constraints_text = ""
    st.session_state.time_horizon_text = ""
    st.session_state.output_format = "Briefing"
    st.session_state.sample_task_selector = "(choose a sample)"
    st.session_state._loaded_sample = None
    st.session_state.run_state = None
    st.session_state.run_in_progress = False
    st.session_state.run_continue = False
    st.session_state.ready_for_next_stage = False
    st.session_state.pause_requested = False
    st.session_state.confirm_reset = False
    _clear_overlay_flags()


def _request_reset() -> None:
    active = st.session_state.run_state and st.session_state.run_state.get("status") in _ACTIVE_STATUSES
    if active:
        st.session_state.confirm_reset = True
    else:
        st.session_state.run_state = None
        st.session_state.run_in_progress = False
        st.session_state.run_continue = False
        st.session_state.ready_for_next_stage = False
        st.session_state.pause_requested = False
        _clear_overlay_flags()


def _confirm_reset() -> None:
    st.session_state.run_state = None
    st.session_state.run_in_progress = False
    st.session_state.run_continue = False
    st.session_state.ready_for_next_stage = False
    st.session_state.pause_requested = False
    st.session_state.confirm_reset = False
    _clear_overlay_flags()


def _cancel_reset() -> None:
    st.session_state.confirm_reset = False


def _load_saved_tasks() -> list[dict]:
    if not settings.persistence_enabled:
        return []
    try:
        from src.persistence.task_repository import TaskRepository

        return TaskRepository().list_tasks()
    except Exception:
        return []


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


def _queue_terminal_notice(state: dict, *, auto_approved: bool = False) -> None:
    status = state.get("status") or ""
    run_id = state.get("run_id")
    if auto_approved or status == "HUMAN_APPROVED" and (state.get("approval_note") == AUTO_APPROVE_NOTE):
        queue_run_notice(
            "Workforce finished and was auto-approved.",
            level="success",
            run_id=run_id,
        )
        return
    if status == "AWAITING_HUMAN_APPROVAL":
        queue_run_notice(
            "Workforce finished. Your approval is waiting.",
            level="info",
            run_id=run_id,
        )
        return
    if status == "FAILED":
        stage = state.get("current_stage") or "unknown"
        err = state.get("error") or "Unknown error"
        queue_run_notice(
            f"Workforce failed at {stage}: {err}",
            level="error",
            run_id=run_id,
        )
        return
    if status == "PAUSED":
        stage = state.get("paused_after_stage") or state.get("current_stage") or "stage"
        queue_run_notice(
            f"Paused after {stage}. Resume when ready.",
            level="warning",
            run_id=run_id,
        )


def _maybe_auto_approve(service: RunService, state: dict) -> tuple[dict, bool]:
    if not st.session_state.auto_approve_enabled:
        return state, False
    if not RunService.can_auto_approve(state):
        return state, False
    updated = service.apply_human_decision(
        state,
        decision="approve",
        note=AUTO_APPROVE_NOTE,
    )
    return updated, True


def _finalize_stage_result(service: RunService, result: dict, *, more_stages: bool) -> None:
    """Persist stage result; pause, continue, or finish with notices / auto-approve."""
    if (result.get("status") or "") == "FAILED" or not more_stages:
        if (result.get("status") or "") != "FAILED":
            result, auto = _maybe_auto_approve(service, result)
        else:
            auto = False
        st.session_state.run_state = result
        _persist(result)
        _queue_terminal_notice(result, auto_approved=auto)
        st.session_state.run_in_progress = False
        st.session_state.run_continue = False
        st.session_state.ready_for_next_stage = False
        st.session_state.pause_requested = False
        if auto:
            _clear_overlay_flags()
        return

    if st.session_state.pause_requested:
        paused = service.pause_run(result)
        st.session_state.run_state = paused
        _persist(paused)
        _queue_terminal_notice(paused)
        st.session_state.run_in_progress = False
        st.session_state.run_continue = False
        st.session_state.ready_for_next_stage = False
        st.session_state.pause_requested = False
        return

    # Leave a short interactive gap so Pause can be clicked before the next stage.
    st.session_state.run_state = result
    _persist(result)
    st.session_state.run_in_progress = False
    st.session_state.run_continue = False
    st.session_state.ready_for_next_stage = True


def _run_overlay_callback(slot):
    def on_update(state: dict) -> None:
        st.session_state.run_state = copy.deepcopy(state)
        if not st.session_state.agent_overlay_minimized:
            with slot.container():
                render_agent_activity_overlay(
                    state,
                    running=True,
                    revision=int(state.get("revision_count") or 0) > 0,
                    show_actions=False,
                )

    return on_update


render_header()
render_sensitive_warning()
render_run_notice()

mode = st.radio(
    "Execution mode",
    options=["demo", "live"],
    format_func=lambda m: "Demo Mode (default — no API key)" if m == "demo" else "Live LLM Mode",
    horizontal=True,
    key="execution_mode",
)
render_mode_status(mode, settings)

st.subheader("Task workspace")

saved_tasks = _load_saved_tasks()
saved_by_label = {f"Saved: {t['title']}": t for t in saved_tasks}
selector_options = ["(choose a sample)"] + SAMPLE_TASK_LABELS + list(saved_by_label.keys())
# Drop stale selection if a saved task was deleted
if st.session_state.sample_task_selector not in selector_options:
    st.session_state.sample_task_selector = "(choose a sample)"
    st.session_state._loaded_sample = None

sample = st.selectbox(
    "Sample or saved task (optional)",
    options=selector_options,
    key="sample_task_selector",
)
# Fill form fields BEFORE task widgets are instantiated on this run.
if sample != "(choose a sample)" and st.session_state.get("_loaded_sample") != sample:
    if sample in SAMPLE_TASKS:
        packet = SAMPLE_TASKS[sample]
    elif sample in saved_by_label:
        saved = saved_by_label[sample]
        packet = {
            "task": saved["task"],
            "background": saved.get("background", ""),
            "constraints": saved.get("constraints", ""),
            "time_horizon": saved.get("time_horizon", ""),
            "output_format": saved.get("output_format", "Briefing"),
        }
    else:
        packet = None
    if packet:
        st.session_state.task_text = packet["task"]
        st.session_state.background_text = packet["background"]
        st.session_state.constraints_text = packet["constraints"]
        st.session_state.time_horizon_text = packet["time_horizon"]
        st.session_state.output_format = packet["output_format"]
        st.session_state._loaded_sample = sample

st.text_area(
    "Task / objective (required)",
    key="task_text",
    height=100,
    placeholder="Describe the work you want the workforce to complete…",
)
st.caption(
    "Type your own task, load a sample/saved template, then click Run Workforce. "
    "Manage saved templates on the **Task Manager** page. **New Task** clears the form."
)

st.checkbox(
    "Auto-approve when ready (skips the Approve button for this session)",
    key="auto_approve_enabled",
)
st.caption(
    "Off by default. When enabled, a clean finished run is approved for you and recorded "
    "in the activity feed as coming from this setting."
)

run_state_preview = st.session_state.run_state
paused_now = bool(run_state_preview and run_state_preview.get("status") == "PAUSED")
busy = (
    st.session_state.run_in_progress
    or st.session_state.run_continue
    or st.session_state.ready_for_next_stage
)
between_stages = bool(st.session_state.ready_for_next_stage)

c_run, c_pause, c_start, c_new, c_reset = st.columns([1.2, 1, 1, 1, 1])
run_clicked = c_run.button(
    "Run Workforce",
    type="primary",
    disabled=busy or paused_now,
    use_container_width=True,
)
pause_clicked = c_pause.button(
    "Pause",
    disabled=(
        paused_now
        or (run_state_preview or {}).get("status")
        in {"AWAITING_HUMAN_APPROVAL", "HUMAN_APPROVED", "HUMAN_REJECTED", "FAILED"}
        or not (between_stages or st.session_state.run_in_progress or st.session_state.run_continue)
    ),
    use_container_width=True,
)
start_clicked = c_start.button(
    "Start",
    disabled=not paused_now or st.session_state.run_in_progress,
    use_container_width=True,
    help="Resume a paused run with the same run id",
)
c_new.button("New Task", use_container_width=True, on_click=_start_new_task)
c_reset.button("Reset", use_container_width=True, on_click=_request_reset)

if pause_clicked:
    st.session_state.pause_requested = True
    if between_stages and st.session_state.run_state:
        service = RunService(prompt_overrides=st.session_state.prompt_overrides)
        paused = service.pause_run(st.session_state.run_state)
        st.session_state.run_state = paused
        _persist(paused)
        _queue_terminal_notice(paused)
        st.session_state.ready_for_next_stage = False
        st.session_state.run_continue = False
        st.session_state.pause_requested = False
        st.rerun()
    st.info("Pause requested — will stop after the current agent stage finishes.")

if start_clicked and paused_now:
    st.session_state.pause_requested = False
    st.session_state.ready_for_next_stage = False
    st.session_state.run_continue = True
    st.session_state.show_agent_overlay = True
    st.session_state.agent_overlay_minimized = False
    st.rerun()

if between_stages and not paused_now:
    st.info(
        "Agent stage finished. Click **Pause** to stop, or wait a moment for the next agent to start."
    )

    @st.fragment(run_every=1.2)
    def _auto_advance_fragment() -> None:
        if not st.session_state.get("ready_for_next_stage"):
            return
        if st.session_state.get("pause_requested"):
            return
        st.session_state.ready_for_next_stage = False
        st.session_state.run_continue = True
        st.rerun()

    _auto_advance_fragment()

with st.expander("Optional context, constraints, and preferences"):
    st.text_area("Background / context", key="background_text", height=80)
    st.text_area(
        "Constraints (budget, time, audience, geography, format)",
        key="constraints_text",
        height=80,
    )
    st.text_input("Time horizon", key="time_horizon_text")
    st.selectbox("Output format", options=OUTPUT_FORMATS, key="output_format")

if st.session_state.confirm_reset:
    st.warning("A run is active or awaiting approval. Confirm reset?")
    st.button("Confirm reset", on_click=_confirm_reset)
    st.button("Cancel reset", on_click=_cancel_reset)

# --- Stage continuation (one agent stage per script run) ---
if st.session_state.run_continue and st.session_state.run_state and not st.session_state.run_in_progress:
    st.session_state.run_continue = False
    service = RunService(prompt_overrides=st.session_state.prompt_overrides)
    current = st.session_state.run_state

    if st.session_state.pause_requested and (current.get("status") or "") != "PAUSED":
        paused = service.pause_run(current)
        st.session_state.run_state = paused
        _persist(paused)
        _queue_terminal_notice(paused)
        st.session_state.pause_requested = False
        st.rerun()

    if (current.get("status") or "") == "PAUSED" and not st.session_state.pause_requested:
        # Resuming: keep checkpoint; clear PAUSED label for UI until next snapshot
        current = dict(current)
        current["status"] = "REVISION_RUNNING" if int(current.get("revision_count") or 0) else "TASK_RECEIVED"
        st.session_state.run_state = current

    st.session_state.run_in_progress = True
    st.session_state.show_agent_overlay = True
    overlay_slot = st.empty()
    try:
        result = service.advance_run(
            st.session_state.run_state,
            on_update=_run_overlay_callback(overlay_slot),
        )
        more = service.run_has_more_stages(result) and (result.get("status") or "") != "FAILED"
        _finalize_stage_result(service, result, more_stages=more)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Run failed: {exc}")
        failed = dict(st.session_state.run_state or {})
        failed["status"] = "FAILED"
        failed["error"] = str(exc)
        st.session_state.run_state = failed
        _persist(failed)
        _queue_terminal_notice(failed)
        st.session_state.run_in_progress = False
        st.session_state.run_continue = False
        st.session_state.ready_for_next_stage = False
    st.rerun()

if run_clicked and not st.session_state.run_in_progress and not paused_now:
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
        st.session_state.pause_requested = False
        st.session_state.run_continue = False
        st.session_state.run_in_progress = True
        st.session_state.show_agent_overlay = True
        st.session_state.agent_overlay_minimized = False
        overlay_slot = st.empty()
        try:
            service = RunService(prompt_overrides=st.session_state.prompt_overrides)
            if settings.persistence_enabled:
                try:
                    from src.persistence.repositories import RunRepository

                    RunRepository().increment_metric("runs_started")
                except Exception:
                    pass
            result = service.begin_run(
                task=validation.task,
                background=validation.background,
                constraints=validation.constraints,
                time_horizon=validation.time_horizon,
                output_format=validation.output_format,
                mode=mode,
                on_update=_run_overlay_callback(overlay_slot),
            )
            more = service.run_has_more_stages(result) and (result.get("status") or "") != "FAILED"
            _finalize_stage_result(service, result, more_stages=more)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Run failed: {exc}")
            if st.session_state.run_state is None:
                st.session_state.run_state = {
                    "status": "FAILED",
                    "error": str(exc),
                    "events": [],
                    "node_states": {},
                }
            else:
                failed = dict(st.session_state.run_state)
                failed["status"] = "FAILED"
                failed["error"] = str(exc)
                st.session_state.run_state = failed
                _persist(failed)
            _queue_terminal_notice(st.session_state.run_state)
            st.session_state.run_in_progress = False
            st.session_state.run_continue = False
            st.session_state.ready_for_next_stage = False
        st.rerun()

run_state = st.session_state.run_state

if st.session_state.show_agent_overlay and st.session_state.agent_overlay_minimized and run_state:
    st.markdown(
        '<div class="overlay-expand-chip">Agent Activity minimized — expand to follow the run</div>',
        unsafe_allow_html=True,
    )
    if st.button("Expand Agent Activity", key="overlay_expand"):
        st.session_state.agent_overlay_minimized = False
        st.rerun()

if (
    st.session_state.show_agent_overlay
    and not st.session_state.agent_overlay_minimized
    and run_state
    and not st.session_state.run_in_progress
):
    render_agent_activity_overlay(
        run_state,
        running=False,
        revision=int(run_state.get("revision_count") or 0) > 0,
        show_actions=True,
    )

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
        if run_state.get("paused_after_stage"):
            st.caption(f"Paused after: `{run_state.get('paused_after_stage')}`")
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
        if action["decision"] == "revise":
            st.session_state.run_in_progress = True
            st.session_state.show_agent_overlay = True
            st.session_state.agent_overlay_minimized = False
            revision_slot = st.empty()

            def on_revision_update(state: dict) -> None:
                st.session_state.run_state = copy.deepcopy(state)
                if not st.session_state.agent_overlay_minimized:
                    with revision_slot.container():
                        render_agent_activity_overlay(
                            state,
                            running=True,
                            revision=True,
                            show_actions=False,
                        )

            try:
                updated = service.apply_human_decision(
                    run_state,
                    decision=action["decision"],
                    note=action.get("note") or "",
                    on_update=on_revision_update,
                )
                updated, auto = _maybe_auto_approve(service, updated)
                st.session_state.run_state = updated
                _persist(updated)
                _queue_terminal_notice(updated, auto_approved=auto)
                if auto:
                    _clear_overlay_flags()
            finally:
                st.session_state.run_in_progress = False
            st.rerun()
        else:
            updated = service.apply_human_decision(
                run_state,
                decision=action["decision"],
                note=action.get("note") or "",
            )
            st.session_state.run_state = updated
            _persist(updated)
            if action["decision"] in {"approve", "reject"}:
                _clear_overlay_flags()
            st.rerun()
    except ValueError as exc:
        st.session_state.run_in_progress = False
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
