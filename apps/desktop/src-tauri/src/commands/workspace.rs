use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager};

use crate::workspace::{
    bind_and_index, get_status_for_path, hash_root_path, search, IndexProgress, IndexStats,
    WorkspaceStatus,
};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BindWorkspaceResult {
    pub root_id: String,
    pub root_path: String,
    pub status: String,
    pub file_count: u32,
    pub chunk_count: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkspaceIndexProgressEvent {
    pub root_id: String,
    pub root_path: String,
    pub conversation_id: Option<String>,
    pub processed: u32,
    pub total: u32,
    pub current_file: Option<String>,
    pub done: bool,
    pub stats: Option<IndexStats>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchWorkspaceHit {
    pub chunk_id: String,
    pub relative_path: String,
    pub text: String,
    pub score: f64,
}

fn emit_index_progress(
    app: &AppHandle,
    root_id: &str,
    root_path: &str,
    conversation_id: Option<&str>,
    progress: &IndexProgress,
    done: bool,
    stats: Option<IndexStats>,
) {
    let _ = app.emit(
        "workspace-index-progress",
        WorkspaceIndexProgressEvent {
            root_id: root_id.to_string(),
            root_path: root_path.to_string(),
            conversation_id: conversation_id.map(|s| s.to_string()),
            processed: progress.processed,
            total: progress.total,
            current_file: progress.current_file.clone(),
            done,
            stats,
        },
    );
}

/// Bind a directory root and start background indexing.
/// Grants sandbox access via grant_path_access, then spawns indexing task.
#[tauri::command]
pub async fn bind_workspace(
    app: AppHandle,
    path: String,
    conversation_id: Option<String>,
) -> Result<BindWorkspaceResult, String> {
    // Grant sandbox access
    let canon = std::fs::canonicalize(&path).map_err(|e| format!("无法解析路径: {}", e))?;
    if !canon.is_dir() {
        return Err(format!("路径不是目录: {}", path));
    }
    let granted = canon.to_string_lossy().to_string();

    // Persist allowed dir via files command
    let sandbox = app.state::<std::sync::Arc<tokio::sync::RwLock<crate::security::path_sandbox::PathSandbox>>>();
    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("failed to get app data dir: {}", e))?;
    let mut dirs = crate::security::path_sandbox::load_allowed_dirs(&data_dir);
    if !dirs.iter().any(|d| d == &granted) {
        dirs.push(granted.clone());
        crate::security::path_sandbox::save_allowed_dirs(&data_dir, &dirs)
            .map_err(|e| e.to_string())?;
        sandbox
            .write()
            .await
            .reload(&dirs)
            .map_err(|e| e.to_string())?;
    }

    let root_id = hash_root_path(&granted);

    if let Ok(Some(existing)) = get_status_for_path(&granted).await {
        if existing.status == "ready" || existing.status == "indexing" {
            return Ok(BindWorkspaceResult {
                root_id: existing.root_id,
                root_path: existing.root_path,
                status: existing.status,
                file_count: existing.file_count,
                chunk_count: existing.chunk_count,
            });
        }
    }

    let root = PathBuf::from(&granted);
    let app_handle = app.clone();
    let root_id_spawn = root_id.clone();
    let root_path_spawn = granted.clone();
    let conv_id = conversation_id.clone();

    tauri::async_runtime::spawn(async move {
        let result = bind_and_index(root, |progress| {
            emit_index_progress(
                &app_handle,
                &root_id_spawn,
                &root_path_spawn,
                conv_id.as_deref(),
                &progress,
                false,
                None,
            );
        })
        .await;

        match result {
            Ok(stats) => {
                let done_progress = IndexProgress {
                    processed: stats.file_count,
                    total: stats.file_count,
                    current_file: None,
                };
                emit_index_progress(
                    &app_handle,
                    &root_id_spawn,
                    &root_path_spawn,
                    conv_id.as_deref(),
                    &done_progress,
                    true,
                    Some(stats),
                );
            }
            Err(e) => {
                log::error!("workspace index failed for {}: {}", root_path_spawn, e);
                let _ = app_handle.emit(
                    "workspace-index-progress",
                    WorkspaceIndexProgressEvent {
                        root_id: root_id_spawn,
                        root_path: root_path_spawn,
                        conversation_id: conv_id,
                        processed: 0,
                        total: 0,
                        current_file: None,
                        done: true,
                        stats: None,
                    },
                );
            }
        }
    });

    Ok(BindWorkspaceResult {
        root_id,
        root_path: granted,
        status: "indexing".into(),
        file_count: 0,
        chunk_count: 0,
    })
}

#[tauri::command]
pub async fn get_workspace_index_status(path: String) -> Result<Option<WorkspaceStatus>, String> {
    get_status_for_path(&path).await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn search_workspace(
    path: String,
    query: String,
    k: Option<usize>,
) -> Result<Vec<SearchWorkspaceHit>, String> {
    let root_id = hash_root_path(
        &std::fs::canonicalize(&path)
            .map_err(|e| format!("无法解析路径: {}", e))?
            .to_string_lossy(),
    );
    let limit = k.unwrap_or(8).clamp(1, 30);
    let hits = search(&root_id, &query, limit)
        .await
        .map_err(|e| e.to_string())?;
    Ok(hits
        .into_iter()
        .map(|h| SearchWorkspaceHit {
            chunk_id: h.chunk_id,
            relative_path: h.relative_path,
            text: h.text,
            score: h.score,
        })
        .collect())
}

/// Start indexing in background (used from chat when directory ref is attached).
pub fn spawn_bind_and_index(app: &AppHandle, root_path: String, conversation_id: Option<String>) {
    let app_handle = app.clone();
    let root_id = hash_root_path(&root_path);
    let conv_id = conversation_id;

    tauri::async_runtime::spawn(async move {
        if let Ok(Some(st)) = get_status_for_path(&root_path).await {
            if st.status == "ready" || st.status == "indexing" {
                return;
            }
        }

        let root = PathBuf::from(&root_path);
        let root_id_spawn = root_id.clone();
        let root_path_spawn = root_path.clone();

        let result = bind_and_index(root, |progress| {
            emit_index_progress(
                &app_handle,
                &root_id_spawn,
                &root_path_spawn,
                conv_id.as_deref(),
                &progress,
                false,
                None,
            );
        })
        .await;

        if let Ok(stats) = result {
            let done_progress = IndexProgress {
                processed: stats.file_count,
                total: stats.file_count,
                current_file: None,
            };
            emit_index_progress(
                &app_handle,
                &root_id_spawn,
                &root_path_spawn,
                conv_id.as_deref(),
                &done_progress,
                true,
                Some(stats),
            );
        }
    });
}
