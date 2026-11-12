"""Workflow event helpers with secret sanitisation."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*\S+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
]


def sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: sanitize_value(v) for k, v in value.items() if not _looks_secret_key(k)}
    if isinstance(value, list):
        return [sanitize_value(v) for v in value]
    if isinstance(value, str):
        cleaned = value
        for pattern in SECRET_PATTERNS:
            cleaned = pattern.sub("[REDACTED]", cleaned)
        return cleaned
    return value


def _looks_secret_key(key: str) -> bool:
    lower = key.lower()
    return any(part in lower for part in ("api_key", "apikey", "secret", "password", "token"))


def make_event(
    *,
    run_id: str,
    stage: str,
    event_type: str,
    status: str,
    message: str,
    duration_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "event_type": event_type,
        "status": status,
        "message": sanitize_value(message),
        "duration_ms": duration_ms,
        "metadata": sanitize_value(metadata or {}),
    }
