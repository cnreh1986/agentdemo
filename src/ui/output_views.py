"""Output tabs and agent inspector."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def render_output_tabs(run_state: dict[str, Any] | None) -> None:
    if not run_state:
        st.info("Outputs appear here after a run.")
        return

    if run_state.get("demo_disclaimer"):
        st.warning(run_state["demo_disclaimer"])

    tabs = st.tabs(["Research", "Plan", "Deliverable", "Review", "Run Log"])
    with tabs[0]:
        research = run_state.get("research")
        if not research:
            st.write("No research packet yet.")
        else:
            st.subheader("Research packet")
            st.write(research.get("agent_summary", ""))
            try:
                from src.services.export_service import ExportService

                docx_name, docx_bytes = ExportService().research_docx(run_state)
                st.download_button(
                    "Download Word (PRD report)",
                    data=docx_bytes,
                    file_name=docx_name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="research_tab_docx",
                )
            except Exception:
                pass
            st.markdown("**Key findings**")
            for item in research.get("key_findings", []):
                st.markdown(f"- {item}")
            st.markdown("**Limitations**")
            for item in research.get("research_limitations", []):
                st.markdown(f"- {item}")
            evidence = research.get("evidence_items") or []
            if evidence:
                st.markdown("**Evidence**")
                for item in evidence:
                    etype = item.get("evidence_type", "")
                    url = item.get("source_url")
                    claim = item.get("claim", "")
                    title = item.get("source_title") or item.get("source_domain") or "Source"
                    if url and etype in {"primary", "secondary"}:
                        st.markdown(f"- {claim} — [{title}]({url})")
                    else:
                        st.markdown(f"- {claim} — {title} _(no live link)_")
            else:
                st.caption("No source-backed evidence items (expected when search is unavailable).")
            with st.expander("Raw JSON"):
                st.code(_json(research), language="json")

    with tabs[1]:
        plan = run_state.get("plan")
        if not plan:
            st.write("No plan yet.")
        else:
            st.subheader(plan.get("objective", "Action plan"))
            st.write(plan.get("strategic_rationale", ""))
            for action in plan.get("actions", []):
                st.markdown(
                    f"**{action.get('action_id')} — {action.get('title')}** "
                    f"({action.get('priority')})  \n{action.get('description')}  \n"
                    f"_Effort: {action.get('estimated_effort')} · Timing: {action.get('suggested_timing')}_"
                )
            with st.expander("Raw JSON"):
                st.code(_json(plan), language="json")

    with tabs[2]:
        deliverable = run_state.get("deliverable")
        if not deliverable:
            st.write("No deliverable yet.")
        elif run_state.get("job_envelope") or run_state.get("comparison_envelope"):
            from src.ui.task_class_views import render_comparison_envelope, render_job_envelope

            if deliverable.get("executive_summary"):
                st.markdown(deliverable["executive_summary"])
            if run_state.get("job_envelope"):
                render_job_envelope(run_state["job_envelope"])
            else:
                render_comparison_envelope(run_state["comparison_envelope"])
            with st.expander("Markdown view"):
                st.markdown(deliverable.get("markdown_content") or "")
            with st.expander("Structured metadata"):
                st.code(_json({k: v for k, v in deliverable.items() if k != "markdown_content"}), language="json")
        else:
            st.markdown(deliverable.get("markdown_content") or deliverable.get("executive_summary", ""))
            with st.expander("Structured metadata"):
                st.code(_json({k: v for k, v in deliverable.items() if k != "markdown_content"}), language="json")

    with tabs[3]:
        review = run_state.get("review")
        if not review:
            st.write("No review yet.")
        else:
            st.subheader("Independent review")
            st.caption("Any score is a model assessment, not an objective truth.")
            st.metric("Quality score (assessment)", review.get("quality_score"))
            st.write(f"**Status:** {review.get('status')}")
            st.write(review.get("reviewer_summary", ""))
            if review.get("issues"):
                st.markdown("**Issues**")
                for issue in review["issues"]:
                    st.markdown(f"- {issue}")
            with st.expander("Raw JSON"):
                st.code(_json(review), language="json")

    with tabs[4]:
        events = run_state.get("events") or []
        st.write(f"{len(events)} events · revision_count={run_state.get('revision_count', 0)}")
        st.code(_json(events), language="json")


def render_agent_inspector(run_state: dict[str, Any] | None) -> None:
    executions = (run_state or {}).get("agent_executions") or {}
    if not executions:
        st.info("Inspect completed agents here after they finish.")
        return
    names = list(executions.keys())
    choice = st.selectbox("Agent execution", names)
    packet = executions[choice]
    st.write(f"**Status:** {packet.get('status')} · **Duration:** {packet.get('duration_ms')} ms")
    st.write(packet.get("summary", ""))
    if packet.get("handoff_to"):
        st.caption(f"Handoff destination: {packet['handoff_to']}")
    c1, c2 = st.columns(2)
    with c1:
        with st.expander("Input packet", expanded=True):
            st.code(_json(packet.get("input")), language="json")
    with c2:
        with st.expander("Output packet", expanded=True):
            st.code(_json(packet.get("output")), language="json")


def render_approval_panel(run_state: dict[str, Any] | None) -> dict[str, Any] | None:
    """Render approval controls. Returns action dict when a button is pressed."""
    if not run_state or run_state.get("status") != "AWAITING_HUMAN_APPROVAL":
        if run_state and run_state.get("approval_status"):
            st.success(
                f"Human decision: **{run_state['approval_status']}** "
                f"at {run_state.get('approval_at', '')}"
            )
            if run_state.get("approval_note"):
                st.write(run_state["approval_note"])
        return None

    st.subheader("Human approval required")
    st.write("The AI reviewer cannot approve this run for you. Choose a decision:")
    note = st.text_area("Optional note / revision instruction", key="approval_note_input")
    c1, c2, c3 = st.columns(3)
    action = None
    with c1:
        if st.button("Approve", type="primary", use_container_width=True):
            action = {"decision": "approve", "note": note}
    with c2:
        if st.button("Request Revision", use_container_width=True):
            action = {"decision": "revise", "note": note}
    with c3:
        if st.button("Reject", use_container_width=True):
            action = {"decision": "reject", "note": note}
    return action
