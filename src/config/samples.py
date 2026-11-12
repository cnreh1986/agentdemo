"""Sample workshop tasks."""

from __future__ import annotations

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

OUTPUT_FORMATS = [
    "Briefing",
    "Action Plan",
    "Research Summary",
    "Markdown bundle",
]
