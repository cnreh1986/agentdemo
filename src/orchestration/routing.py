"""Conditional routing for the workforce graph."""

from __future__ import annotations

from typing import Literal

from src.orchestration.state import WorkforceState


def after_validation(state: WorkforceState) -> Literal["specify", "end_failed"]:
    if state.get("status") == "FAILED":
        return "end_failed"
    return "specify"


def after_agent(state: WorkforceState) -> Literal["continue", "end_failed"]:
    if state.get("status") == "FAILED" or state.get("error"):
        return "end_failed"
    return "continue"


def after_review(state: WorkforceState) -> Literal["revise", "human"]:
    if state.get("status") == "FAILED":
        return "human"
    review = state.get("review") or {}
    needs = review.get("status") == "revision_required" or state.get("status") == "REVISION_REQUIRED"
    count = int(state.get("revision_count") or 0)
    max_rev = int(state.get("max_revisions") or 1)
    if needs and count < max_rev:
        return "revise"
    return "human"
