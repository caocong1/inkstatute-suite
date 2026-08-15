//! Tauri commands for the read-only history plane.
//!
//! Thin wrappers over [`engine::history::HistoryStore`] that:
//! - Default `limit=50`, `offset=0`.
//! - Return empty arrays when the database doesn't exist yet.
//! - Surface user-readable Chinese (`"读取会话历史失败"`) on error; details
//!   go only to local logs (stderr), never to the UI.

use crate::engine::history::{HistoryStore, SearchHit, SessionSummary};
use crate::engine::paths;

const DEFAULT_LIMIT: i64 = 50;
const DEFAULT_OFFSET: i64 = 0;
const USER_FACING_ERROR: &str = "读取会话历史失败";

#[tauri::command]
pub async fn list_conversations(
    limit: Option<i64>,
    offset: Option<i64>,
) -> Result<Vec<SessionSummary>, String> {
    let limit = limit.unwrap_or(DEFAULT_LIMIT).max(0);
    let offset = offset.unwrap_or(DEFAULT_OFFSET).max(0);
    match open_store().await {
        Ok(Some(store)) => store
            .list_sessions(limit, offset)
            .await
            .map_err(|e| {
                eprintln!("[history] list_conversations: {e}");
                USER_FACING_ERROR.to_string()
            }),
        Ok(None) => Ok(Vec::new()),
        Err(e) => {
            eprintln!("[history] list_conversations open: {e}");
            Err(USER_FACING_ERROR.to_string())
        }
    }
}

#[tauri::command]
pub async fn search_conversations(
    query: String,
    limit: Option<i64>,
) -> Result<Vec<SearchHit>, String> {
    let limit = limit.unwrap_or(DEFAULT_LIMIT).max(0);
    match open_store().await {
        Ok(Some(store)) => store
            .search(&query, limit)
            .await
            .map_err(|e| {
                eprintln!("[history] search_conversations: {e}");
                USER_FACING_ERROR.to_string()
            }),
        Ok(None) => Ok(Vec::new()),
        Err(e) => {
            eprintln!("[history] search_conversations open: {e}");
            Err(USER_FACING_ERROR.to_string())
        }
    }
}

#[tauri::command]
pub async fn get_conversation_docs(
    session_id: String,
) -> Result<Vec<SearchHit>, String> {
    match open_store().await {
        Ok(Some(store)) => store
            .session_docs(&session_id)
            .await
            .map_err(|e| {
                eprintln!("[history] get_conversation_docs: {e}");
                USER_FACING_ERROR.to_string()
            }),
        Ok(None) => Ok(Vec::new()),
        Err(e) => {
            eprintln!("[history] get_conversation_docs open: {e}");
            Err(USER_FACING_ERROR.to_string())
        }
    }
}

/// Open the history store from the app's sessions root. Returns `Ok(None)` when
/// the database file doesn't exist yet (first run).
async fn open_store() -> Result<Option<HistoryStore>, String> {
    let sessions_root = paths::sessions_root().map_err(|e| {
        eprintln!("[history] sessions_root: {e}");
        USER_FACING_ERROR.to_string()
    })?;
    HistoryStore::open(&sessions_root).await.map_err(|e| {
        eprintln!("[history] open: {e}");
        USER_FACING_ERROR.to_string()
    })
}
