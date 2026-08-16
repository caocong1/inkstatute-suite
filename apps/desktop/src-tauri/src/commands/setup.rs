use serde::Serialize;
use std::fs;
use std::path::PathBuf;

use crate::engine::paths;
use crate::engine::smoke::smoke_test;
use std::time::Duration;

/// Check if this is the first run: settings.json doesn't exist or has no
/// active provider configured.
#[tauri::command]
pub fn is_first_run() -> bool {
    // Check if the app root has any engine installed.
    match paths::read_current() {
        Ok(Some(_)) => {
            // Engine exists — check if a provider key is set.
            // The credentials module tracks active provider in settings.json.
            // If no active provider is set, it's still first run.
            !has_active_provider()
        }
        _ => true,
    }
}

/// Check if an active provider is configured.
fn has_active_provider() -> bool {
    // Read the settings file from the app root.
    let settings_path = match settings_path() {
        Some(p) => p,
        None => return false,
    };
    if !settings_path.exists() {
        return false;
    }
    let text = match fs::read_to_string(&settings_path) {
        Ok(t) => t,
        Err(_) => return false,
    };
    // Check for active_provider field in settings JSON.
    let v: serde_json::Value = match serde_json::from_str(&text) {
        Ok(v) => v,
        Err(_) => return false,
    };
    v.get("active_provider")
        .and_then(|p| p.as_str())
        .map(|s| !s.is_empty())
        .unwrap_or(false)
}

fn settings_path() -> Option<PathBuf> {
    paths::app_root().ok().map(|r| r.join("settings.json"))
}

/// Mark setup as complete by recording the provider.
#[tauri::command]
pub async fn complete_setup(provider: String) -> Result<(), String> {
    let settings_path = settings_path().ok_or("无法确定应用数据目录")?;
    if let Some(parent) = settings_path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }

    // Read existing settings or start fresh.
    let mut settings: serde_json::Value = if settings_path.exists() {
        fs::read_to_string(&settings_path)
            .ok()
            .and_then(|t| serde_json::from_str(&t).ok())
            .unwrap_or(serde_json::json!({}))
    } else {
        serde_json::json!({})
    };

    // Set active provider.
    if let Some(obj) = settings.as_object_mut() {
        obj.insert("active_provider".to_string(), serde_json::json!(provider));
        obj.insert("setup_complete".to_string(), serde_json::json!(true));
    }

    let settings_json = serde_json::to_string_pretty(&settings)
        .map_err(|e| format!("设置序列化失败: {}", e))?;
    fs::write(&settings_path, settings_json)
        .map_err(|e| e.to_string())?;

    Ok(())
}

/// Preflight report — checks engine, skills, and smoke test.
#[derive(Serialize)]
pub struct PreflightReport {
    pub engine_installed: bool,
    pub engine_version: Option<String>,
    pub skills_available: bool,
    pub smoke_passed: bool,
    pub smoke_failure: Option<String>,
}

/// Run preflight checks: engine installed, skills available, smoke test.
#[tauri::command]
pub async fn preflight() -> Result<PreflightReport, String> {
    let current = paths::read_current().map_err(|e| e.to_string())?;
    let engine_version = current.clone();
    let engine_installed = current.is_some();

    // Check skills directory (presets or skills in app root).
    let skills_dir = paths::app_root()
        .map(|r| r.join("presets"))
        .unwrap_or_else(|_| PathBuf::from("presets"));
    let skills_available = skills_dir.exists() && skills_dir.read_dir().map(|mut d| d.next().is_some()).unwrap_or(false);

    // Run smoke test if engine is installed.
    let mut smoke_passed = false;
    let mut smoke_failure = None;
    if let Some(ref version) = current {
        if let Ok(engine_dir) = paths::engine_dir(version) {
            if let Ok(node_bin) = paths::node_binary() {
                let result = smoke_test(&engine_dir, &node_bin, Duration::from_secs(60)).await;
                smoke_passed = result.ok;
                if !result.ok {
                    smoke_failure = result.failure;
                }
            } else {
                smoke_failure = Some("Node 运行环境缺失".to_string());
            }
        }
    }

    Ok(PreflightReport {
        engine_installed,
        engine_version,
        skills_available,
        smoke_passed,
        smoke_failure,
    })
}
