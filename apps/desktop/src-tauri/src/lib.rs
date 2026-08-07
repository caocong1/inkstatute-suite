#![allow(
    dead_code,
    unused_variables,
    clippy::collapsible_str_replace,
    clippy::explicit_auto_deref,
    clippy::explicit_counter_loop,
    clippy::into_iter_on_ref,
    clippy::manual_is_multiple_of,
    clippy::manual_pattern_char_comparison,
    clippy::manual_strip,
    clippy::map_identity,
    clippy::needless_borrow,
    clippy::needless_borrows_for_generic_args,
    clippy::needless_return,
    clippy::new_without_default,
    clippy::ptr_arg,
    clippy::redundant_closure,
    clippy::too_many_arguments
)]

mod commands;
mod security;

use security::path_sandbox::PathSandbox;
use std::sync::Arc;
use tauri::Manager;
use tokio::sync::RwLock;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .setup(move |app| {
            let data_dir = app
                .path()
                .app_data_dir()
                .map_err(|e| format!("failed to get app data dir: {}", e))?;
            std::fs::create_dir_all(&data_dir)
                .map_err(|e| format!("failed to create app data dir: {}", e))?;

            // Initialize path sandbox from persisted allowed dirs (JSON file)
            let allowed_dirs = security::path_sandbox::load_allowed_dirs(&data_dir);
            let sandbox = Arc::new(RwLock::new(
                PathSandbox::with_defaults(&allowed_dirs)
                    .unwrap_or_else(|_| PathSandbox::new(Vec::new())),
            ));
            app.manage(sandbox);

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::files::read_file_content,
            commands::files::list_directory,
            commands::files::prepare_attachment,
            commands::files::classify_dropped_paths,
            commands::files::grant_path_access,
            commands::files::get_allowed_file_dirs,
            commands::files::set_allowed_file_dirs,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
