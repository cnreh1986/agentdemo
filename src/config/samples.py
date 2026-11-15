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

SAMPLE_JOBS_LABEL = "Find product manager jobs in Hyderabad (5–10 years, last 7 days)"
SAMPLE_MARKET_RESEARCH_LABEL = (
    "Market research on marketing tools (HubSpot vs Mailchimp vs Brevo)"
)
SAMPLE_COMPARE_RICH_LABEL = "Compare product manager and product marketer (example company context)"
SAMPLE_COMPARE_THIN_LABEL = "Compare product manager and product marketer (needs context)"

SAMPLE_TASKS[SAMPLE_JOBS_LABEL] = {
    "task": (
        "Find product manager jobs in Hyderabad, 5–10 years of experience, "
        "posted in the last 7 days."
    ),
    "background": "",
    "constraints": "Hyderabad, India only; do not apply or contact anyone.",
    "time_horizon": "This week",
    "output_format": "Job search results",
}

SAMPLE_TASKS[SAMPLE_MARKET_RESEARCH_LABEL] = {
    "task": (
        "Conduct market research on marketing tools for a lightweight B2B team. "
        "Compare HubSpot, Mailchimp, and Brevo on pricing, core features, AI capabilities, "
        "and fit for email + CRM."
    ),
    "background": (
        "We are a small SaaS company choosing one marketing stack this quarter. "
        "We need email campaigns and a simple CRM; budget is limited. "
        "Decision: which tool to standardise on for the next 12 months. "
        "(Workshop example — treat public pricing as approximate.)"
    ),
    "constraints": (
        "Criteria to compare: pricing, core features, AI capabilities, fit for email + CRM. "
        "Do not invent pricing or features that sources do not show. Do not purchase or sign up."
    ),
    "time_horizon": "This quarter",
    "output_format": "Comparison matrix",
}

SAMPLE_TASKS[SAMPLE_COMPARE_RICH_LABEL] = {
    "task": "Compare product manager and product marketer for our next hire.",
    "background": (
        "We are an 80-person B2B SaaS company in Hyderabad. We sell accounts-payable software "
        "to mid-market finance teams in India. We have one technical product manager. "
        "We have no product marketer. Sales is founder-led. Our product manager already writes "
        "the release notes and joins the first sales call. "
        "(Fictional example company for the workshop.)"
    ),
    "constraints": (
        "One headcount next quarter. Audience is the founder. Do not name a candidate. "
        "Do not turn this into a job advertisement."
    ),
    "time_horizon": "Next quarter",
    "output_format": "Comparison matrix",
}

SAMPLE_TASKS[SAMPLE_COMPARE_THIN_LABEL] = {
    "task": "Compare product manager and product marketer. I will provide the context.",
    "background": "",
    "constraints": "",
    "time_horizon": "",
    "output_format": "Comparison matrix",
}

SAMPLE_TASK_LABELS = list(SAMPLE_TASKS.keys())

# Stable ids for system/demo tasks shown in Task Manager (not stored as files).
_SYSTEM_TASK_IDS: dict[str, str] = {
    "Plan my next productive week.": "system-plan-week",
    "Research a product opportunity and prepare a brief.": "system-product-brief",
    "Create a learning roadmap for a new skill.": "system-learning-roadmap",
    SAMPLE_JOBS_LABEL: "system-job-search-hyderabad-pm",
    SAMPLE_MARKET_RESEARCH_LABEL: "system-market-research-marketing-tools",
    SAMPLE_COMPARE_RICH_LABEL: "system-compare-pm-pmm-context",
    SAMPLE_COMPARE_THIN_LABEL: "system-compare-pm-pmm-thin",
}

OUTPUT_FORMATS = [
    "Briefing",
    "Action Plan",
    "Research Summary",
    "Markdown bundle",
    "Job search results",
    "Comparison matrix",
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
