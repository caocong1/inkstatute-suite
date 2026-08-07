-- Offline cache for session/run/event metadata (read-only when offline)
CREATE TABLE IF NOT EXISTS cached_sessions (
    session_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_viewed_at TEXT
);

CREATE TABLE IF NOT EXISTS cached_runs (
    run_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (session_id) REFERENCES cached_sessions(session_id)
);

CREATE TABLE IF NOT EXISTS cached_events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES cached_runs(run_id)
);

CREATE TABLE IF NOT EXISTS cached_artifacts (
    artifact_id TEXT PRIMARY KEY,
    run_id TEXT,
    session_id TEXT NOT NULL,
    local_path TEXT NOT NULL,
    kind TEXT,
    name TEXT,
    downloaded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cached_events_run_id ON cached_events(run_id, seq);
CREATE INDEX IF NOT EXISTS idx_cached_runs_session_id ON cached_runs(session_id);
CREATE INDEX IF NOT EXISTS idx_cached_artifacts_session_id ON cached_artifacts(session_id);
