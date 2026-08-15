//! Tauri commands for content package management (SKL-12).
//!
//! Exposes `check_content_update` and `get_content_status` to the frontend.
//! The content updater never blocks startup — all failures are caught and
//! returned as `Skipped` or `RolledBack`.

use crate::content::updater::{ContentStatus, ContentUpdater, UpdateOutcome};

/// Checks for content package updates and applies them if available.
///
/// This is safe to call at startup — it never blocks on failure.
/// The engine version is read from the current engine pointer.
#[tauri::command]
pub async fn check_content_update() -> Result<UpdateOutcome, String> {
    // Read the current engine version from the engine pointer.
    let engine_version = crate::engine::paths::read_current()
        .map_err(|e| e.to_string())?
        .unwrap_or_else(|| "0.0.0".to_string());

    let updater = ContentUpdater::new(&engine_version);
    let outcome = updater.check_and_update().await;
    Ok(outcome)
}

/// Returns the current content status for the settings panel "skills" tab.
#[tauri::command]
pub fn get_content_status() -> Result<ContentStatus, String> {
    let engine_version = crate::engine::paths::read_current()
        .map_err(|e| e.to_string())?
        .unwrap_or_else(|| "0.0.0".to_string());

    let updater = ContentUpdater::new(&engine_version);
    Ok(updater.current_status())
}
