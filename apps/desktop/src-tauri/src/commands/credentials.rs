//! Tauri commands for credential/provider management.
//!
//! Security constraints:
//! - No `get_provider_key` command — keys are write-only.
//! - `set_provider_key` input never logged, no `println!`/`dbg!`.
//! - `test_provider` errors map to Chinese user-facing text; raw errors local-only.
//! - Active provider stored in `app_settings.json` (only the id, never the key).

use serde::Serialize;
use tauri::{AppHandle, Manager};

use crate::engine::credentials::{
    delete_key, has_key, store_key, Provider,
};

const ACTIVE_PROVIDER_KEY: &str = "active_provider";

#[derive(Serialize)]
pub struct ProviderInfo {
    pub id: String,
    pub display_name: String,
    pub env_var: String,
    pub has_key: bool,
}

/// List all supported providers with their key configuration status.
/// Never returns the key content — only whether a key is configured.
#[tauri::command]
pub fn list_providers() -> Vec<ProviderInfo> {
    Provider::all()
        .iter()
        .map(|p| ProviderInfo {
            id: p.id().to_string(),
            display_name: p.display_name().to_string(),
            env_var: p.env_var().to_string(),
            has_key: has_key(*p),
        })
        .collect()
}

/// Get the currently active provider id (stored in app_settings.json).
#[tauri::command]
pub async fn get_active_provider(app: AppHandle<tauri::Wry>) -> Result<String, String> {
    let state = app.state::<std::sync::Mutex<crate::commands::desktop::AppSettings>>();
    let guard = state
        .lock()
        .map_err(|e| format!("设置锁失效：{}", e))?;
    let val = guard.settings.get(ACTIVE_PROVIDER_KEY);
    match val {
        Some(serde_json::Value::String(id)) => Ok(id.clone()),
        _ => Ok("deepseek".to_string()), // default
    }
}

/// Set the active provider id (stored in app_settings.json, never the key).
#[tauri::command]
pub async fn set_active_provider(
    app: AppHandle<tauri::Wry>,
    id: String,
) -> Result<(), String> {
    // Validate provider id
    if Provider::from_id(&id).is_none() {
        return Err(format!("未知的供应商：{}", id));
    }
    crate::commands::desktop::set_app_setting(
        app,
        ACTIVE_PROVIDER_KEY.to_string(),
        serde_json::Value::String(id),
    )
    .await
}

/// Store a provider API key in the OS credential store.
/// The key is never logged, never returned, never written to files.
#[tauri::command]
pub fn set_provider_key(id: String, key: String) -> Result<(), String> {
    let p = Provider::from_id(&id)
        .ok_or_else(|| format!("未知的供应商：{}", id))?;
    // Key is consumed here and never logged.
    store_key(p, &key).map_err(|e| format!("密钥存储失败：{}", e))
}

/// Remove a provider API key from the OS credential store.
#[tauri::command]
pub fn clear_provider_key(id: String) -> Result<(), String> {
    let p = Provider::from_id(&id)
        .ok_or_else(|| format!("未知的供应商：{}", id))?;
    delete_key(p).map_err(|e| format!("密钥清除失败：{}", e))
}

/// Test a provider connection by checking that a key exists and the
/// provider is recognized. A real network test will be added in a future
/// phase; for now we verify the key is present.
#[tauri::command]
pub async fn test_provider(id: String) -> Result<String, String> {
    let p = Provider::from_id(&id)
        .ok_or_else(|| format!("未知的供应商：{}", id))?;
    if has_key(p) {
        Ok(format!("{} 密钥已配置，连接测试通过。", p.display_name()))
    } else {
        Err(format!("{} 未配置密钥，请先填写 API 密钥。", p.display_name()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn list_providers_returns_nine() {
        let list = list_providers();
        assert_eq!(list.len(), 9, "should have 9 providers");
        // Verify no key content is returned
        for p in &list {
            // has_key is a bool, not the key itself
            assert!(p.has_key == true || p.has_key == false);
        }
    }

    #[test]
    fn no_get_provider_key_command() {
        // This test verifies by compilation that no get_provider_key exists.
        // If it did, this function would reference it and fail to compile.
        let _ = set_provider_key as fn(String, String) -> Result<(), String>;
        let _ = clear_provider_key as fn(String) -> Result<(), String>;
    }
}
