use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::{AppHandle, Manager};

/// In-memory settings store (backed by a JSON file on disk).
/// Simple key-value store for desktop-specific app settings
/// (update channel, auto-check flag, etc.).
/// NOT for session data — the offline-cache SQLite DB handles that.

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct AppSettings {
    #[serde(flatten)]
    pub settings: HashMap<String, serde_json::Value>,
}

/// Get the path to the app settings JSON file.
fn settings_file_path(app: &AppHandle<tauri::Wry>) -> Result<PathBuf, String> {
    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("failed to get app data dir: {}", e))?;
    Ok(data_dir.join("app_settings.json"))
}

/// Load settings from the JSON file. Returns empty settings if file doesn't exist.
fn load_settings(app: &AppHandle<tauri::Wry>) -> AppSettings {
    let path = match settings_file_path(app) {
        Ok(p) => p,
        Err(_) => return AppSettings::default(),
    };
    match std::fs::read_to_string(&path) {
        Ok(content) => serde_json::from_str(&content).unwrap_or_default(),
        Err(_) => AppSettings::default(),
    }
}

/// Save settings to the JSON file.
fn save_settings(app: &AppHandle<tauri::Wry>, settings: &AppSettings) -> Result<(), String> {
    let path = settings_file_path(app)?;
    let content = serde_json::to_string_pretty(settings)
        .map_err(|e| format!("failed to serialize settings: {}", e))?;
    std::fs::write(&path, content)
        .map_err(|e| format!("failed to write settings file: {}", e))?;
    Ok(())
}

/// Get a single app setting by key.
/// Returns null if the key doesn't exist.
#[tauri::command]
pub async fn get_app_setting(
    app: AppHandle<tauri::Wry>,
    key: String,
) -> Result<Option<serde_json::Value>, String> {
    let settings = load_settings(&app);
    Ok(settings.settings.get(&key).cloned())
}

/// Set a single app setting by key.
/// Writes the entire settings map back to disk.
#[tauri::command]
pub async fn set_app_setting(
    app: AppHandle<tauri::Wry>,
    key: String,
    value: serde_json::Value,
) -> Result<(), String> {
    // Use a Mutex to prevent concurrent writes from racing
    let state = app.state::<Mutex<AppSettings>>();
    let mut current = {
        let guard = state
            .lock()
            .map_err(|e| format!("settings lock poisoned: {}", e))?;
        guard.clone()
    };
    current.settings.insert(key, value);
    save_settings(&app, &current)?;
    // Update in-memory state
    {
        let mut guard = state
            .lock()
            .map_err(|e| format!("settings lock poisoned: {}", e))?;
        *guard = current;
    }
    Ok(())
}
