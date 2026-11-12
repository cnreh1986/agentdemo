from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkflowEvent(BaseModel):
    event_id: str
    run_id: str
    timestamp: datetime | str
    stage: str
    event_type: str
    status: str
    message: str
    duration_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
