use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use tauri::{AppHandle, Manager};
use tauri_plugin_sql::{Migration, MigrationKind};

/// Return migrations for the offline-cache SQLite database.
pub fn offline_cache_migrations() -> Vec<Migration> {
    vec![Migration {
        version: 1,
        description: "create offline cache tables",
        sql: include_str!("../../migrations/002_offline_cache.sql"),
        kind: MigrationKind::Up,
    }]
}

// ── Types ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct CachedSession {
    pub session_id: String,
    pub tenant_id: String,
    pub title: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    pub last_viewed_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct CachedRun {
    pub run_id: String,
    pub session_id: String,
    pub status: String,
    pub created_at: String,
    pub completed_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct CachedEvent {
    pub event_id: String,
    pub run_id: String,
    pub seq: i64,
    pub event_type: String,
    pub payload_json: String,
    pub occurred_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct CachedArtifact {
    pub artifact_id: String,
    pub run_id: Option<String>,
    pub session_id: String,
    pub local_path: String,
    pub kind: Option<String>,
    pub name: Option<String>,
    pub downloaded_at: String,
}

// ── Commands ────────────────────────────────────────────────────────────

/// Helper: get the app data dir path for the offline cache database.
fn cache_db_path(app: &AppHandle) -> Result<std::path::PathBuf, String> {
    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("failed to get app data dir: {}", e))?;
    Ok(data_dir.join("offline-cache.db"))
}

/// Helper: open a sqlx SQLite pool for the offline cache database.
async fn open_cache_pool(app: &AppHandle) -> Result<sqlx::SqlitePool, String> {
    let db_path = cache_db_path(app)?;
    if let Some(parent) = db_path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("create app data dir: {}", e))?;
    }
    let db_url = format!(
        "sqlite:{}",
        db_path.to_string_lossy().replace('\\', "/")
    );
    let pool = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(2)
        .connect(&db_url)
        .await
        .map_err(|e| format!("open offline cache db: {}", e))?;

    // Run migrations
    let sql = include_str!("../../migrations/002_offline_cache.sql");
    sqlx::raw_sql(sql)
        .execute(&pool)
        .await
        .map_err(|e| format!("offline cache migrate: {}", e))?;

    Ok(pool)
}

#[tauri::command]
pub async fn cache_session(
    app: AppHandle,
    session_id: String,
    tenant_id: String,
    title: Option<String>,
) -> Result<(), String> {
    let pool = open_cache_pool(&app).await?;
    let now = chrono::Utc::now().to_rfc3339();
    sqlx::query(
        "INSERT INTO cached_sessions (session_id, tenant_id, title, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?)
         ON CONFLICT(session_id) DO UPDATE SET
            tenant_id = excluded.tenant_id,
            title = excluded.title,
            updated_at = excluded.updated_at",
    )
    .bind(&session_id)
    .bind(&tenant_id)
    .bind(&title)
    .bind(&now)
    .bind(&now)
    .execute(&pool)
    .await
    .map_err(|e| format!("cache_session: {}", e))?;
    Ok(())
}

#[tauri::command]
pub async fn cache_run(
    app: AppHandle,
    run_id: String,
    session_id: String,
    status: String,
) -> Result<(), String> {
    let pool = open_cache_pool(&app).await?;
    let now = chrono::Utc::now().to_rfc3339();
    sqlx::query(
        "INSERT INTO cached_runs (run_id, session_id, status, created_at)
         VALUES (?, ?, ?, ?)
         ON CONFLICT(run_id) DO UPDATE SET
            status = excluded.status",
    )
    .bind(&run_id)
    .bind(&session_id)
    .bind(&status)
    .bind(&now)
    .execute(&pool)
    .await
    .map_err(|e| format!("cache_run: {}", e))?;
    Ok(())
}

#[tauri::command]
pub async fn cache_event(
    app: AppHandle,
    event_id: String,
    run_id: String,
    seq: i64,
    event_type: String,
    payload_json: String,
    occurred_at: String,
) -> Result<(), String> {
    let pool = open_cache_pool(&app).await?;
    sqlx::query(
        "INSERT OR IGNORE INTO cached_events (event_id, run_id, seq, event_type, payload_json, occurred_at)
         VALUES (?, ?, ?, ?, ?, ?)",
    )
    .bind(&event_id)
    .bind(&run_id)
    .bind(seq)
    .bind(&event_type)
    .bind(&payload_json)
    .bind(&occurred_at)
    .execute(&pool)
    .await
    .map_err(|e| format!("cache_event: {}", e))?;
    Ok(())
}

#[tauri::command]
pub async fn cache_artifact(
    app: AppHandle,
    artifact_id: String,
    session_id: String,
    local_path: String,
    kind: Option<String>,
    name: Option<String>,
) -> Result<(), String> {
    let pool = open_cache_pool(&app).await?;
    let now = chrono::Utc::now().to_rfc3339();
    sqlx::query(
        "INSERT OR REPLACE INTO cached_artifacts (artifact_id, session_id, local_path, kind, name, downloaded_at)
         VALUES (?, ?, ?, ?, ?, ?)",
    )
    .bind(&artifact_id)
    .bind(&session_id)
    .bind(&local_path)
    .bind(&kind)
    .bind(&name)
    .bind(&now)
    .execute(&pool)
    .await
    .map_err(|e| format!("cache_artifact: {}", e))?;
    Ok(())
}

#[tauri::command]
pub async fn get_cached_sessions(app: AppHandle) -> Result<Vec<CachedSession>, String> {
    let pool = open_cache_pool(&app).await?;
    let rows = sqlx::query_as::<_, CachedSession>(
        "SELECT session_id, tenant_id, title, created_at, updated_at, last_viewed_at
         FROM cached_sessions ORDER BY updated_at DESC",
    )
    .fetch_all(&pool)
    .await
    .map_err(|e| format!("get_cached_sessions: {}", e))?;
    Ok(rows)
}

#[tauri::command]
pub async fn get_cached_runs(
    app: AppHandle,
    session_id: String,
) -> Result<Vec<CachedRun>, String> {
    let pool = open_cache_pool(&app).await?;
    let rows = sqlx::query_as::<_, CachedRun>(
        "SELECT run_id, session_id, status, created_at, completed_at
         FROM cached_runs WHERE session_id = ? ORDER BY created_at DESC",
    )
    .bind(&session_id)
    .fetch_all(&pool)
    .await
    .map_err(|e| format!("get_cached_runs: {}", e))?;
    Ok(rows)
}

#[tauri::command]
pub async fn get_cached_events(
    app: AppHandle,
    run_id: String,
) -> Result<Vec<CachedEvent>, String> {
    let pool = open_cache_pool(&app).await?;
    let rows = sqlx::query_as::<_, CachedEvent>(
        "SELECT event_id, run_id, seq, event_type, payload_json, occurred_at
         FROM cached_events WHERE run_id = ? ORDER BY seq ASC",
    )
    .bind(&run_id)
    .fetch_all(&pool)
    .await
    .map_err(|e| format!("get_cached_events: {}", e))?;
    Ok(rows)
}

#[tauri::command]
pub async fn get_cached_artifact(
    app: AppHandle,
    artifact_id: String,
) -> Result<Option<CachedArtifact>, String> {
    let pool = open_cache_pool(&app).await?;
    let row = sqlx::query_as::<_, CachedArtifact>(
        "SELECT artifact_id, run_id, session_id, local_path, kind, name, downloaded_at
         FROM cached_artifacts WHERE artifact_id = ?",
    )
    .bind(&artifact_id)
    .fetch_optional(&pool)
    .await
    .map_err(|e| format!("get_cached_artifact: {}", e))?;
    Ok(row)
}

#[tauri::command]
pub async fn get_cached_artifacts_by_session(
    app: AppHandle,
    session_id: String,
) -> Result<Vec<CachedArtifact>, String> {
    let pool = open_cache_pool(&app).await?;
    let rows = sqlx::query_as::<_, CachedArtifact>(
        "SELECT artifact_id, run_id, session_id, local_path, kind, name, downloaded_at
         FROM cached_artifacts WHERE session_id = ? ORDER BY downloaded_at DESC",
    )
    .bind(&session_id)
    .fetch_all(&pool)
    .await
    .map_err(|e| format!("get_cached_artifacts_by_session: {}", e))?;
    Ok(rows)
}
