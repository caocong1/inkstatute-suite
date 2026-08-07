/**
 * offlineCache — TypeScript wrapper for the offline cache Tauri commands.
 *
 * All functions use invoke() to call the Tauri commands defined in
 * src-tauri/src/commands/offline_cache.rs. These are desktop-specific
 * commands for the local SQLite offline cache.
 */

export interface CachedSession {
  session_id: string;
  tenant_id: string;
  title?: string | null;
  created_at: string;
  updated_at: string;
  last_viewed_at?: string | null;
}

export interface CachedRun {
  run_id: string;
  session_id: string;
  status: string;
  created_at: string;
  completed_at?: string | null;
}

export interface CachedEvent {
  event_id: string;
  run_id: string;
  seq: number;
  event_type: string;
  payload_json: string;
  occurred_at: string;
}

export interface CachedArtifact {
  artifact_id: string;
  run_id?: string | null;
  session_id: string;
  local_path: string;
  kind?: string | null;
  name?: string | null;
  downloaded_at: string;
}

/**
 * Cache a session's metadata (upsert).
 */
export async function cacheSession(session: {
  session_id: string;
  tenant_id: string;
  title?: string;
}): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("cache_session", {
    sessionId: session.session_id,
    tenantId: session.tenant_id,
    title: session.title ?? null,
  });
}

/**
 * Cache a run's metadata (upsert).
 */
export async function cacheRun(run: {
  run_id: string;
  session_id: string;
  status: string;
}): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("cache_run", {
    runId: run.run_id,
    sessionId: run.session_id,
    status: run.status,
  });
}

/**
 * Cache an event (insert if not exists).
 */
export async function cacheEvent(event: {
  event_id: string;
  run_id: string;
  seq: number;
  event_type: string;
  payload_json: string;
  occurred_at: string;
}): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("cache_event", {
    eventId: event.event_id,
    runId: event.run_id,
    seq: event.seq,
    eventType: event.event_type,
    payloadJson: event.payload_json,
    occurredAt: event.occurred_at,
  });
}

/**
 * Cache an artifact's metadata (insert or replace).
 */
export async function cacheArtifact(artifact: {
  artifact_id: string;
  session_id: string;
  local_path: string;
  kind?: string;
  name?: string;
}): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("cache_artifact", {
    artifactId: artifact.artifact_id,
    sessionId: artifact.session_id,
    localPath: artifact.local_path,
    kind: artifact.kind ?? null,
    name: artifact.name ?? null,
  });
}

/**
 * Get all cached sessions.
 */
export async function getCachedSessions(): Promise<CachedSession[]> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<CachedSession[]>("get_cached_sessions");
}

/**
 * Get cached runs for a session.
 */
export async function getCachedRuns(sessionId: string): Promise<CachedRun[]> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<CachedRun[]>("get_cached_runs", { sessionId });
}

/**
 * Get cached events for a run (ordered by seq).
 */
export async function getCachedEvents(runId: string): Promise<CachedEvent[]> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<CachedEvent[]>("get_cached_events", { runId });
}

/**
 * Get a cached artifact by id.
 */
export async function getCachedArtifact(artifactId: string): Promise<CachedArtifact | null> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<CachedArtifact | null>("get_cached_artifact", { artifactId });
}

/**
 * Get all cached artifacts for a session.
 */
export async function getCachedArtifactsBySession(sessionId: string): Promise<CachedArtifact[]> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<CachedArtifact[]>("get_cached_artifacts_by_session", { sessionId });
}

/**
 * Bulk sync a session and its runs/events to the local cache.
 * Called when viewing a session online (write-on-view).
 */
export async function syncSessionToCache(
  session: { session_id: string; tenant_id: string; title?: string },
  runs: Array<{ run_id: string; session_id: string; status: string }>,
  events: Array<{
    event_id: string;
    run_id: string;
    seq: number;
    event_type: string;
    payload_json: string;
    occurred_at: string;
  }>,
): Promise<void> {
  await cacheSession(session);
  for (const run of runs) {
    await cacheRun(run);
  }
  for (const event of events) {
    await cacheEvent(event);
  }
}
