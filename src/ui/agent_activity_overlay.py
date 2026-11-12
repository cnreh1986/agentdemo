"""Focused Agent Activity takeover panel for workshop runs."""

from __future__ import annotations

from typing import Any

import streamlit as st

from src.orchestration.events import sanitize_value
from src.ui.agent_cards import AGENTS
from src.ui.styles import chip_class
from src.ui.workflow_view import PIPELINE_LABELS

AGENT_ACTIVITY_COPY: dict[str, dict[str, Any]] = {
    "orchestrator": {
        "title": "Orchestrator",
        "what": (
            "Validates your request and turns it into a clear task specification "
            "and success criteria."
        ),
        "steps": [
            "Validate input",
            "Create TaskSpec",
            "Emit events",
            "Hand off to Research",
        ],
    },
    "research": {
        "title": "Research",
        "what": (
            "Finds themes, assumptions, gaps, and (if configured) live search evidence. "
            "Never invents fake URLs."
        ),
        "steps": [
            "Optional Firecrawl search",
            "Build research prompt",
            "Call LLM for JSON",
            "Validate ResearchPacket",
            "Strip bad citations",
            "Hand off to Planning",
        ],
    },
    "planning": {
        "title": "Planning",
        "what": (
            "Turns research into prioritised actions, timing estimates, risks, "
            "and dependencies."
        ),
        "steps": [
            "Load research + task",
            "Call LLM for JSON",
            "Validate Plan",
            "Hand off to Execution",
        ],
    },
    "execution": {
        "title": "Execution",
        "what": (
            "Writes the briefing / action plan deliverable in Markdown plus "
            "structured metadata."
        ),
        "steps": [
            "Load research + plan",
            "Call LLM for JSON",
            "Validate Deliverable",
            "Hand off to Reviewer",
        ],
    },
    "reviewer": {
        "title": "Reviewer",
        "what": (
            "Independently checks quality; may request one bounded revision. "
            "Does not human-approve."
        ),
        "steps": [
            "Load deliverable + criteria",
            "Call LLM for JSON",
            "Validate ReviewReport",
            "Route revise or pause for human",
        ],
    },
    "human_approval": {
        "title": "Human Approval",
        "what": (
            "You decide: Approve, Request Revision, or Reject. "
            "No emails or external actions."
        ),
        "steps": [
            "Wait for explicit button",
            "Record decision + timestamp",
        ],
    },
}

_AGENT_BY_KEY = {a["key"]: a for a in AGENTS}
_PIPELINE_KEYS = [key for key, _ in PIPELINE_LABELS]


def progress_fraction(run_state: dict[str, Any] | None) -> float:
    node_states = (run_state or {}).get("node_states") or {}
    if not _PIPELINE_KEYS:
        return 0.0
    completed = sum(1 for key in _PIPELINE_KEYS if node_states.get(key) == "Completed")
    status = (run_state or {}).get("status") or ""
    if status in {"AWAITING_HUMAN_APPROVAL", "HUMAN_APPROVED"}:
        return 1.0
    if status == "PAUSED":
        return min(0.9, (completed + 0.2) / len(_PIPELINE_KEYS))
    if status == "FAILED":
        return min(0.95, completed / len(_PIPELINE_KEYS))
    return min(0.95, (completed + (0.35 if any(node_states.get(k) == "Running" for k in _PIPELINE_KEYS) else 0)) / len(_PIPELINE_KEYS))


def active_stage_key(run_state: dict[str, Any] | None) -> str:
    state = run_state or {}
    node_states = state.get("node_states") or {}
    for key in _PIPELINE_KEYS:
        if node_states.get(key) == "Running":
            return key
    current = str(state.get("current_stage") or "")
    if current in AGENT_ACTIVITY_COPY:
        return current
    if current == "human":
        return "human_approval"
    for key in reversed(_PIPELINE_KEYS):
        if node_states.get(key) in {"Completed", "Needs revision", "Failed", "Queued", "Paused"}:
            return key
    return "orchestrator"


def summarise_packet(kind: str, packet: Any) -> list[str]:
    if not isinstance(packet, dict):
        return ["(none yet)"]
    lines: list[str] = []
    if kind == "research":
        findings = packet.get("key_findings") or []
        lines.append(f"Key findings: {len(findings)}")
        evidence = packet.get("evidence_items") or []
        lines.append(f"Evidence items: {len(evidence)}")
        limits = packet.get("research_limitations") or []
        if limits:
            lines.append(f"Limitation: {str(limits[0])[:120]}")
    elif kind == "plan":
        actions = packet.get("actions") or []
        lines.append(f"Actions: {len(actions)}")
        for action in actions[:3]:
            if isinstance(action, dict):
                title = action.get("title") or action.get("action_id") or "action"
                lines.append(f"• {title}")
    elif kind == "deliverable":
        title = packet.get("title") or "untitled"
        lines.append(f"Title: {title}")
        summary = str(packet.get("executive_summary") or "").strip()
        if summary:
            lines.append(summary[:160] + ("…" if len(summary) > 160 else ""))
    elif kind == "review":
        lines.append(f"Status: {packet.get('status', '—')}")
        if packet.get("quality_score") is not None:
            lines.append(f"Quality score (model assessment): {packet.get('quality_score')}")
        summary = str(packet.get("reviewer_summary") or "").strip()
        if summary:
            lines.append(summary[:160])
    elif kind == "task":
        lines.append(f"Objective: {packet.get('objective') or packet.get('original_task') or '—'}")
        constraints = str(packet.get("constraints") or "").strip()
        if constraints:
            lines.append(f"Constraints: {constraints[:120]}")
    else:
        lines.append(f"Keys: {', '.join(list(packet.keys())[:6])}")
    return lines or ["(empty)"]


def _current_execution(run_state: dict[str, Any], stage: str) -> dict[str, Any]:
    executions = run_state.get("agent_executions") or {}
    if stage in executions:
        return executions[stage]
    if stage == "execution" and "execution_revision" in executions:
        return executions["execution_revision"]
    return {}


def _handoff_summaries(run_state: dict[str, Any], stage: str) -> tuple[list[str], list[str], Any, Any]:
    execution = _current_execution(run_state, stage)
    raw_in = execution.get("input")
    raw_out = execution.get("output")
    if raw_in is None and stage == "research":
        raw_in = run_state.get("task_specification")
    if raw_out is None:
        packet_map = {
            "orchestrator": "task_specification",
            "research": "research",
            "planning": "plan",
            "execution": "deliverable",
            "reviewer": "review",
        }
        key = packet_map.get(stage)
        if key:
            raw_out = run_state.get(key)

    kind_in = "task" if stage in {"orchestrator", "research"} else stage
    if stage == "planning":
        in_lines = summarise_packet("research", run_state.get("research") or raw_in)
        out_lines = summarise_packet("plan", raw_out if isinstance(raw_out, dict) else run_state.get("plan"))
    elif stage == "execution":
        in_lines = summarise_packet("plan", run_state.get("plan") or raw_in)
        out_lines = summarise_packet("deliverable", raw_out if isinstance(raw_out, dict) else run_state.get("deliverable"))
    elif stage == "reviewer":
        in_lines = summarise_packet("deliverable", run_state.get("deliverable") or raw_in)
        out_lines = summarise_packet("review", raw_out if isinstance(raw_out, dict) else run_state.get("review"))
    elif stage == "orchestrator":
        in_lines = summarise_packet("task", run_state.get("task_input") or raw_in or {})
        out_lines = summarise_packet("task", raw_out if isinstance(raw_out, dict) else run_state.get("task_specification"))
    else:
        in_lines = summarise_packet(kind_in, raw_in if isinstance(raw_in, dict) else run_state.get("task_specification"))
        out_lines = summarise_packet("research" if stage == "research" else kind_in, raw_out if isinstance(raw_out, dict) else {})

    return in_lines, out_lines, sanitize_value(raw_in), sanitize_value(raw_out)


def render_agent_activity_overlay(
    run_state: dict[str, Any] | None,
    *,
    running: bool,
    revision: bool = False,
    show_actions: bool = True,
) -> None:
    state = run_state or {}
    mode = str(state.get("mode") or "demo").lower()
    run_id = str(state.get("run_id") or "")
    short_id = run_id[:8] if run_id else "—"
    stage = active_stage_key(state)
    copy = AGENT_ACTIVITY_COPY.get(stage, AGENT_ACTIVITY_COPY["orchestrator"])
    agent_meta = _AGENT_BY_KEY.get(stage, {})
    icon = agent_meta.get("icon", "🤖")
    node_states = state.get("node_states") or {}
    events = state.get("events") or []
    last_event = events[-1] if events else {}
    execution = _current_execution(state, stage)
    duration = execution.get("duration_ms")
    duration_txt = f"{duration} ms" if duration is not None else "—"
    frac = progress_fraction(state)
    status = state.get("status") or ("RUNNING" if running else "—")
    revision_count = int(state.get("revision_count") or 0)
    max_revisions = int(state.get("max_revisions") or 1)

    st.markdown('<div class="agent-activity-overlay">', unsafe_allow_html=True)
    head_l, head_r = st.columns([2.4, 1])
    with head_l:
        title = "Agent Activity"
        if revision or revision_count:
            title += f" · Revision {revision_count} of {max_revisions}"
        st.markdown(f"### {title}")
        st.caption(f"Run `{short_id}` · Stage **{copy['title']}** · Status `{status}`")
    with head_r:
        badge = "Demo" if mode == "demo" else "Live"
        st.markdown(
            f'<div style="text-align:right;margin-top:0.4rem;">'
            f'<span class="status-chip {"chip-wait" if mode == "demo" else "chip-run"}">{badge}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )

    st.progress(frac, text=f"{copy['title']} · {status} · agent duration {duration_txt}")

    if mode == "demo":
        st.info("Illustrative fixtures — no live LLM or web search in this run.")
    else:
        st.warning(
            "Task text is sent to the configured model provider. "
            "Search runs only if Firecrawl is configured."
        )

    if status == "FAILED":
        err = state.get("error") or last_event.get("message") or "Stage failed."
        st.error(f"Failed at **{copy['title']}**: {sanitize_value(err)}")

    left, center, right = st.columns([1.05, 1.45, 1.2])
    with left:
        st.markdown("#### Pipeline")
        parts = [
            '<div class="pipeline overlay-pipeline">'
            '<span class="pipe-node Completed">User Task<br/>'
            '<span style="font-weight:500;font-size:0.85rem;">Completed</span></span>'
            "<span>→</span>"
        ]
        for key, label in PIPELINE_LABELS:
            node_status = node_states.get(key, "Waiting")
            safe = node_status.replace(" ", "-")
            active = " active-node" if key == stage else ""
            parts.append(
                f'<span class="pipe-node {safe}{active}" title="{node_status}">'
                f"{label}<br/><span style=\"font-weight:500;font-size:0.85rem;\">{node_status}</span>"
                f"</span><span>→</span>"
            )
        parts.append(
            '<span class="pipe-node">Final Output<br/>'
            '<span style="font-weight:500;font-size:0.85rem;">Waiting</span></span></div>'
        )
        st.markdown("".join(parts), unsafe_allow_html=True)

    with center:
        st.markdown(f"#### {icon} {copy['title']}")
        st.markdown(f"**What this agent does**  \n{copy['what']}")
        st.markdown("**What the code is doing now**")
        for step in copy["steps"]:
            st.markdown(f"- {step}")
        msg = last_event.get("message") or "Waiting for the next event…"
        st.markdown(
            f"**Last event**  \n"
            f'<span class="status-chip {chip_class(str(last_event.get("status") or status))}">'
            f'{last_event.get("status") or status}</span> {sanitize_value(msg)}',
            unsafe_allow_html=True,
        )
        st.caption(f"Elapsed for this agent: {duration_txt}")

    with right:
        st.markdown("#### Handoff packets")
        in_lines, out_lines, raw_in, raw_out = _handoff_summaries(state, stage)
        st.markdown("**Input (summary)**")
        for line in in_lines:
            st.markdown(f"- {sanitize_value(line)}")
        st.markdown("**Output (summary)**")
        for line in out_lines:
            st.markdown(f"- {sanitize_value(line)}")
        with st.expander("Show raw JSON (technical)", expanded=False):
            st.json({"input": raw_in, "output": raw_out})

    st.markdown("#### Activity feed")
    if not events:
        st.caption("Events will appear as each agent starts and finishes.")
    else:
        for event in reversed(events[-12:]):
            ts = event.get("timestamp", "")[-12:-1] if event.get("timestamp") else ""
            st.markdown(
                f"**{ts}** · `{event.get('stage', '')}` · {event.get('status', '')}  \n"
                f"{sanitize_value(event.get('message', ''))}"
            )

    if show_actions:
        a1, a2, a3 = st.columns(3)
        with a1:
            if st.button("Minimize", key="overlay_minimize", use_container_width=True):
                st.session_state.agent_overlay_minimized = True
                st.rerun()
        with a2:
            if not running and status == "AWAITING_HUMAN_APPROVAL":
                if st.button(
                    "Continue to review & approve",
                    type="primary",
                    key="overlay_continue",
                    use_container_width=True,
                ):
                    st.session_state.show_agent_overlay = False
                    st.session_state.agent_overlay_minimized = False
                    st.rerun()
            elif not running and status == "PAUSED":
                if st.button(
                    "Start (resume)",
                    type="primary",
                    key="overlay_resume",
                    use_container_width=True,
                ):
                    st.session_state.pause_requested = False
                    st.session_state.run_continue = True
                    st.rerun()
            elif not running and status in {"FAILED", "CANCELLED", "HUMAN_APPROVED", "HUMAN_REJECTED"}:
                if st.button("Close", key="overlay_close", use_container_width=True):
                    st.session_state.show_agent_overlay = False
                    st.session_state.agent_overlay_minimized = False
                    st.rerun()
        with a3:
            if not running and status == "FAILED":
                if st.button("Inspect run", key="overlay_inspect", use_container_width=True):
                    st.session_state.show_agent_overlay = False
                    st.session_state.agent_overlay_minimized = False
                    st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
