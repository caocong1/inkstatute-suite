use serde::{Deserialize, Serialize};
use std::path::Path;
use std::sync::Arc;
use tauri::Manager;
use tokio::sync::RwLock;

use crate::security::path_sandbox::PathSandbox;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileInfo {
    pub path: String,
    pub name: String,
    pub file_type: String,
    pub size: u64,
    pub is_dir: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileAttachment {
    pub path: String,
    pub name: String,
    pub file_type: String,
    pub size: u64,
    pub content_preview: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DroppedPathKind {
    pub path: String,
    pub is_dir: bool,
    pub exists: bool,
}

/// Read file content with UTF-8 → GB18030 fallback.
pub async fn read_file_inner(file_path: &Path) -> Result<String, String> {
    if !file_path.exists() {
        return Err(format!("File not found: {}", file_path.display()));
    }

    let extension = file_path
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();

    match extension.as_str() {
        "txt" | "md" | "json" | "csv" | "xml" | "html" | "yaml" | "yml" | "toml" | "log" => {
            // Try UTF-8 first, fall back to GB18030 for Chinese text files
            match tokio::fs::read_to_string(file_path).await {
                Ok(content) => Ok(content),
                Err(_) => {
                    let bytes = tokio::fs::read(file_path)
                        .await
                        .map_err(|e| format!("Failed to read file: {}", e))?;
                    let (text, _, _) = encoding_rs::GB18030.decode(&bytes);
                    Ok(text.into_owned())
                }
            }
        }
        _ => match tokio::fs::read_to_string(file_path).await {
            Ok(content) => Ok(content),
            Err(_) => {
                let size = tokio::fs::metadata(file_path)
                    .await
                    .map(|m| m.len())
                    .unwrap_or(0);
                Ok(format!(
                    "[二进制文件: {} — {} bytes]",
                    file_path.display(),
                    size
                ))
            }
        },
    }
}

#[tauri::command]
pub async fn read_file_content(
    path: String,
    sandbox: tauri::State<'_, Arc<RwLock<PathSandbox>>>,
) -> Result<String, String> {
    let validated = sandbox
        .read()
        .await
        .validate(&path)
        .map_err(|e| e.to_string())?;
    read_file_inner(&validated).await
}

#[tauri::command]
pub async fn list_directory(
    path: String,
    recursive: Option<bool>,
    sandbox: tauri::State<'_, Arc<RwLock<PathSandbox>>>,
) -> Result<Vec<FileInfo>, String> {
    let dir_path = sandbox
        .read()
        .await
        .validate(&path)
        .map_err(|e| e.to_string())?;

    if !dir_path.is_dir() {
        return Err(format!("Not a directory: {}", path));
    }

    let recursive = recursive.unwrap_or(false);
    let mut files = Vec::new();
    scan_dir_recursive(&dir_path, &mut files, recursive).await?;
    files.sort_by(|a, b| a.name.cmp(&b.name));
    Ok(files)
}

fn scan_dir_recursive<'a>(
    dir: &'a Path,
    files: &'a mut Vec<FileInfo>,
    recursive: bool,
) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<(), String>> + Send + 'a>> {
    Box::pin(async move {
        let mut entries = tokio::fs::read_dir(dir).await.map_err(|e| e.to_string())?;

        while let Some(entry) = entries.next_entry().await.map_err(|e| e.to_string())? {
            let metadata = entry.metadata().await.map_err(|e| e.to_string())?;
            let file_type = if metadata.is_dir() {
                "directory".to_string()
            } else {
                entry
                    .path()
                    .extension()
                    .and_then(|e| e.to_str())
                    .unwrap_or("unknown")
                    .to_string()
            };

            files.push(FileInfo {
                path: entry.path().to_string_lossy().to_string(),
                name: entry.file_name().to_string_lossy().to_string(),
                file_type,
                size: metadata.len(),
                is_dir: metadata.is_dir(),
            });

            if recursive && metadata.is_dir() {
                scan_dir_recursive(&entry.path(), files, recursive).await?;
            }
        }

        Ok(())
    })
}

#[tauri::command]
pub async fn prepare_attachment(
    path: String,
    sandbox: tauri::State<'_, Arc<RwLock<PathSandbox>>>,
) -> Result<FileAttachment, String> {
    let validated = sandbox
        .read()
        .await
        .validate(&path)
        .map_err(|e| e.to_string())?;
    let metadata = tokio::fs::metadata(&validated)
        .await
        .map_err(|e| e.to_string())?;

    let name = validated
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("unknown")
        .to_string();

    let file_type = validated
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();

    let content_preview = match read_file_inner(&validated).await {
        Ok(content) => {
            if content.len() > 50000 {
                Some(format!(
                    "{}...\n\n[文件已截断，共 {} 字符]",
                    &content[..50000],
                    content.len()
                ))
            } else {
                Some(content)
            }
        }
        Err(_) => None,
    };

    Ok(FileAttachment {
        path: validated.to_string_lossy().to_string(),
        name,
        file_type,
        size: metadata.len(),
        content_preview,
    })
}

/// Classify OS drag-and-drop paths as file vs directory.
/// No sandbox check — the user explicitly dropped the path.
#[tauri::command]
pub async fn classify_dropped_paths(paths: Vec<String>) -> Result<Vec<DroppedPathKind>, String> {
    let mut out = Vec::with_capacity(paths.len());
    for path in paths {
        let (is_dir, exists) = match tokio::fs::metadata(&path).await {
            Ok(meta) => (meta.is_dir(), true),
            Err(_) => (false, false),
        };
        out.push(DroppedPathKind {
            path,
            is_dir,
            exists,
        });
    }
    Ok(out)
}

/// Grant sandbox read access to a directory path.
#[tauri::command]
pub async fn grant_path_access(
    path: String,
    app: tauri::AppHandle,
    sandbox: tauri::State<'_, Arc<RwLock<PathSandbox>>>,
) -> Result<Vec<String>, String> {
    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("failed to get app data dir: {}", e))?;

    let canon = std::fs::canonicalize(&path).map_err(|e| format!("无法解析路径: {}", e))?;
    if !canon.is_dir() {
        return Err(format!("路径不是目录: {}", path));
    }
    let path_str = canon.to_string_lossy().to_string();

    let mut dirs = crate::security::path_sandbox::load_allowed_dirs(&data_dir);
    if !dirs.iter().any(|d| d == &path_str) {
        dirs.push(path_str.clone());
        crate::security::path_sandbox::save_allowed_dirs(&data_dir, &dirs)
            .map_err(|e| e.to_string())?;

        // Hot-reload sandbox
        sandbox
            .write()
            .await
            .reload(&dirs)
            .map_err(|e| e.to_string())?;
    }

    Ok(dirs)
}

/// Get the current list of allowed directories.
#[tauri::command]
pub async fn get_allowed_file_dirs(
    app: tauri::AppHandle,
) -> Result<Vec<String>, String> {
    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("failed to get app data dir: {}", e))?;
    Ok(crate::security::path_sandbox::load_allowed_dirs(&data_dir))
}

/// Set the list of allowed directories.
#[tauri::command]
pub async fn set_allowed_file_dirs(
    dirs: Vec<String>,
    app: tauri::AppHandle,
    sandbox: tauri::State<'_, Arc<RwLock<PathSandbox>>>,
) -> Result<Vec<String>, String> {
    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("failed to get app data dir: {}", e))?;

    crate::security::path_sandbox::save_allowed_dirs(&data_dir, &dirs)
        .map_err(|e| e.to_string())?;

    sandbox
        .write()
        .await
        .reload(&dirs)
        .map_err(|e| e.to_string())?;

    Ok(dirs)
}
