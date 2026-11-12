"""Sample workshop tasks."""

from __future__ import annotations

from typing import Any

SAMPLE_TASKS: dict[str, dict[str, str]] = {
    "Plan my next productive week.": {
        "task": "Plan my next productive week.",
        "background": "I am a product manager balancing deep work, meetings, and learning.",
        "constraints": "Max 8 focused hours per weekday; protect two evenings; audience is myself.",
        "time_horizon": "5 working days",
        "output_format": "Action Plan",
    },
    "Research a product opportunity and prepare a brief.": {
        "task": "Research a product opportunity and prepare a brief.",
        "background": "Exploring AI-assisted personal productivity tools for professionals.",
        "constraints": "Focus on B2B SaaS; no budget above $50k MVP; English-speaking markets.",
        "time_horizon": "Next quarter",
        "output_format": "Briefing",
    },
    "Create a learning roadmap for a new skill.": {
        "task": "Create a learning roadmap for a new skill.",
        "background": "I want to learn practical Agentic AI workflows for product work.",
        "constraints": "5–7 hours per week; beginner-to-intermediate; prefer free or low-cost resources.",
        "time_horizon": "8 weeks",
        "output_format": "Markdown bundle",
    },
}

SAMPLE_TASK_LABELS = list(SAMPLE_TASKS.keys())

# Stable ids for system/demo tasks shown in Task Manager (not stored as files).
_SYSTEM_TASK_IDS: dict[str, str] = {
    "Plan my next productive week.": "system-plan-week",
    "Research a product opportunity and prepare a brief.": "system-product-brief",
    "Create a learning roadmap for a new skill.": "system-learning-roadmap",
}

OUTPUT_FORMATS = [
    "Briefing",
    "Action Plan",
    "Research Summary",
    "Markdown bundle",
]


def list_system_tasks() -> list[dict[str, Any]]:
    """Return built-in demo/system tasks as uniform packets for Task Manager."""
    packets: list[dict[str, Any]] = []
    for label, fields in SAMPLE_TASKS.items():
        packets.append(
            {
                "id": _SYSTEM_TASK_IDS.get(label, f"system-{abs(hash(label))}"),
                "title": label,
                "task": fields.get("task", ""),
                "background": fields.get("background", ""),
                "constraints": fields.get("constraints", ""),
                "time_horizon": fields.get("time_horizon", ""),
                "output_format": fields.get("output_format", "Briefing"),
                "source": "system",
            }
        )
    return packets
