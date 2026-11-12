"""SQLite helpers using the standard library."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    task_input TEXT NOT NULL,
    task_specification_json TEXT,
    mode TEXT NOT NULL,
    provider_name TEXT,
    model_name TEXT,
    status TEXT NOT NULL,
    current_stage TEXT,
    revision_count INTEGER DEFAULT 0,
    max_revisions INTEGER DEFAULT 1,
    approval_status TEXT,
    approval_note TEXT,
    completed_at TEXT,
    state_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_executions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    status TEXT,
    input_json TEXT,
    output_json TEXT,
    started_at TEXT,
    completed_at TEXT,
    duration_ms INTEGER,
    error_code TEXT,
    safe_error_message TEXT,
    attempt_number INTEGER DEFAULT 1,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS workflow_events (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    stage TEXT,
    event_type TEXT,
    status TEXT,
    message TEXT,
    metadata_json TEXT,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    title TEXT,
    content_markdown TEXT,
    content_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS workshop_metrics (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    runs_started INTEGER DEFAULT 0,
    runs_completed INTEGER DEFAULT 0,
    exports_downloaded INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS saved_tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    task TEXT NOT NULL,
    background TEXT DEFAULT '',
    constraints TEXT DEFAULT '',
    time_horizon TEXT DEFAULT '',
    output_format TEXT DEFAULT 'Briefing',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path | None = None):
        root = Path(__file__).resolve().parents[2]
        self.path = Path(path) if path else root / "data" / "workforce.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO workshop_metrics (id, runs_started, runs_completed, exports_downloaded) VALUES (1, 0, 0, 0)"
            )
            conn.commit()
