use std::fs;
use std::sync::Arc;

use tauri::{AppHandle, Emitter, Manager};

use crate::engine::assemble::AssembleOptions;
use crate::engine::updater::{EngineUpdater, UpdateCheck, UpdateOutcome, UpdateStage};

/// The app version reported to the updater for compatibility checks.
const APP_VERSION: &str = env!("CARGO_PKG_VERSION");

/// Read the cordis config from the bundled resource or the engines/ dir.
fn read_cordis_yml(app: &AppHandle) -> String {
    // In production, the cordis config is bundled as a resource.
    if let Ok(resource_dir) = app.path().resource_dir() {
        let bundled = resource_dir.join("engines/acp.cordis.yml");
        if bundled.is_file() {
            if let Ok(text) = fs::read_to_string(&bundled) {
                return text;
            }
        }
    }
    // Dev fallback: read from the repo's engines/ dir.
    let dev_path = std::env::var("CARGO_MANIFEST_DIR")
        .map(|d| std::path::Path::new(&d).join("../../engines/acp.cordis.yml"))
        .unwrap_or_else(|_| std::path::PathBuf::from("engines/acp.cordis.yml"));
    fs::read_to_string(&dev_path).unwrap_or_default()
}

/// The update base URL. In production this is the owner-hosted endpoint.
/// Override via `INKSTATUTE_UPDATE_BASE` env var for testing.
fn update_base() -> String {
    std::env::var("INKSTATUTE_UPDATE_BASE")
        .unwrap_or_else(|_| "https://updates.inkstatute.com/v5".to_string())
}

fn build_updater(app: &AppHandle) -> EngineUpdater {
    EngineUpdater::new(
        update_base(),
        read_cordis_yml(app),
        AssembleOptions::default(),
    )
}

#[tauri::command]
pub async fn check_engine_update(app: AppHandle) -> Result<UpdateCheck, String> {
    let updater = build_updater(&app);
    updater
        .check(APP_VERSION)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn apply_engine_update(app: AppHandle) -> Result<UpdateOutcome, String> {
    let updater = build_updater(&app);
    let app_handle = app.clone();
    let on_stage: Arc<dyn Fn(UpdateStage) + Send + Sync + 'static> = Arc::new(move |stage: UpdateStage| {
        let _ = app_handle.emit("inkstatute://engine-update", &stage);
    });
    // Spawn the update in a tokio task to decouple from the Tauri command's
    // lifetime constraints (the generate_handler! macro requires HRTB-compatible
    // futures, but assemble() borrows local EngineLock data).
    let handle = tokio::spawn(async move {
        updater.apply(APP_VERSION, on_stage).await
    });
    let outcome = handle.await.map_err(|e| format!("更新任务异常: {}", e))?;
    Ok(outcome)
}

#[tauri::command]
pub async fn rollback_engine(app: AppHandle) -> Result<String, String> {
    let updater = build_updater(&app);
    updater
        .rollback()
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn list_engine_versions(app: AppHandle) -> Result<Vec<String>, String> {
    let updater = build_updater(&app);
    updater
        .installed_versions()
        .map_err(|e| e.to_string())
}
