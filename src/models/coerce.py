"""Shared soft-coercion helpers for LLM JSON that almost matches our schemas."""

from __future__ import annotations

from typing import Any


def as_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, dict):
        for key in ("text", "finding", "item", "value", "summary", "claim", "items", "title"):
            if key in value:
                return as_str_list(value[key])
        return as_str_list(list(value.values()))
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, str):
                text = item.strip()
                if text:
                    out.append(text)
            elif isinstance(item, dict):
                for key in ("text", "finding", "item", "value", "summary", "claim", "title"):
                    if key in item and str(item[key]).strip():
                        out.append(str(item[key]).strip())
                        break
                else:
                    nested = str(item).strip()
                    if nested:
                        out.append(nested)
            else:
                out.append(str(item))
        return out
    return [str(value)]


def as_dict_list(value: Any) -> list[dict[str, Any]]:
    """Coerce timeline-like fields: list[dict], single dict, map, or string."""
    if value is None:
        return []
    if isinstance(value, dict):
        entry_keys = {"day", "focus", "phase", "when", "period", "summary", "step", "milestone"}
        if entry_keys.intersection(value.keys()):
            return [dict(value)]
        # Map form: {"Day 1": "Frame", "Day 2": "Draft"}
        return [{"day": str(k), "focus": str(v)} for k, v in value.items()]
    if isinstance(value, str):
        text = value.strip()
        return [{"summary": text}] if text else []
    if isinstance(value, list):
        out: list[dict[str, Any]] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, dict):
                out.append(dict(item))
            elif isinstance(item, str) and item.strip():
                out.append({"summary": item.strip()})
            else:
                out.append({"summary": str(item)})
        return out
    return [{"summary": str(value)}]


def as_action_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        if isinstance(value, str) and value.strip():
            return [
                {
                    "action_id": "a1",
                    "title": value.strip()[:80],
                    "description": value.strip(),
                }
            ]
        return []
    cleaned: list[dict[str, Any]] = []
    for i, item in enumerate(value):
        if item is None:
            continue
        if isinstance(item, str):
            text = item.strip()
            if not text:
                continue
            cleaned.append(
                {
                    "action_id": f"a{i + 1}",
                    "title": text[:80],
                    "description": text,
                }
            )
            continue
        if isinstance(item, dict):
            d = dict(item)
            if not str(d.get("action_id") or "").strip():
                d["action_id"] = f"a{i + 1}"
            if not str(d.get("title") or "").strip():
                d["title"] = str(d.get("name") or d.get("action") or f"Action {i + 1}")
            if not str(d.get("description") or "").strip():
                d["description"] = str(d.get("details") or d.get("title") or "")
            cleaned.append(d)
    return cleaned


def soften_priority(value: object) -> str:
    if value is None or value == "":
        return "medium"
    text = str(value).strip().lower()
    if text in {"high", "medium", "low"}:
        return text
    aliases = {
        "1": "high",
        "h": "high",
        "urgent": "high",
        "critical": "high",
        "2": "medium",
        "m": "medium",
        "normal": "medium",
        "3": "low",
        "l": "low",
        "minor": "low",
    }
    return aliases.get(text, "medium")


def soften_quality_score(value: object, default: int = 50) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, str):
        value = value.strip().rstrip("%")
    try:
        num = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if 0.0 <= num <= 1.0:
        num *= 100.0
    return max(0, min(100, int(round(num))))
