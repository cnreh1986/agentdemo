"""Task input validation."""

from __future__ import annotations

from dataclasses import dataclass

from .settings import get_settings


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]
    task: str = ""
    background: str = ""
    constraints: str = ""
    time_horizon: str = ""
    output_format: str = "Briefing"


def validate_task_input(
    task: str,
    background: str = "",
    constraints: str = "",
    time_horizon: str = "",
    output_format: str = "Briefing",
    max_length: int | None = None,
) -> ValidationResult:
    settings = get_settings()
    limit = max_length if max_length is not None else settings.max_task_length
    errors: list[str] = []

    cleaned_task = (task or "").strip()
    cleaned_background = (background or "").strip()
    cleaned_constraints = (constraints or "").strip()
    cleaned_horizon = (time_horizon or "").strip()
    cleaned_format = (output_format or "Briefing").strip() or "Briefing"

    if not cleaned_task:
        errors.append("Task / objective is required.")
    if len(cleaned_task) > limit:
        errors.append(f"Task exceeds maximum length of {limit} characters.")
    for label, value in (
        ("Background", cleaned_background),
        ("Constraints", cleaned_constraints),
        ("Time horizon", cleaned_horizon),
    ):
        if len(value) > limit:
            errors.append(f"{label} exceeds maximum length of {limit} characters.")

    return ValidationResult(
        ok=len(errors) == 0,
        errors=errors,
        task=cleaned_task,
        background=cleaned_background,
        constraints=cleaned_constraints,
        time_horizon=cleaned_horizon,
        output_format=cleaned_format,
    )
