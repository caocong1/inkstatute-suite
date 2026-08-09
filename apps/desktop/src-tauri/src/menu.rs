/**
 * Native menu bar — Tauri 2 menu configuration.
 *
 * 6 menus: 墨律 InkStatute (app), 文件 (File), 编辑 (Edit), 视图 (View),
 * 窗口 (Window), 帮助 (Help).
 *
 * Menu events are forwarded to the frontend via `app.emit("menu-event", id)`.
 * The frontend's `menuHandlers.ts` listens for "menu-event" and dispatches
 * to the appropriate callback.
 *
 * Menu structure per 94-UI-SPEC §Native Menus.
 */
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem, Submenu};
use tauri::{Emitter, AppHandle};

/// Build the native menu bar with 6 menus.
///
/// Menus:
/// 1. 墨律 InkStatute (app menu) — about, settings, quit
/// 2. 文件 (File) — new conversation, open file, export word
/// 3. 编辑 (Edit) — undo, redo, cut, copy, paste, select all (predefined)
/// 4. 视图 (View) — theme submenu, zoom, fullscreen
/// 5. 窗口 (Window) — minimize, maximize, close
/// 6. 帮助 (Help) — search workspace, check update
pub fn build_menu(app: &AppHandle<tauri::Wry>) -> tauri::Result<Menu<tauri::Wry>> {
    // 1. 墨律 InkStatute (app menu)
    let app_menu = Submenu::with_items(
        app,
        "墨律 InkStatute",
        true,
        &[
            &MenuItem::with_id(app, "about", "关于墨律", true, None::<&str>)?,
            &PredefinedMenuItem::separator(app)?,
            &MenuItem::with_id(app, "settings", "设置...", true, Some("CmdOrCtrl+,"))?,
            &PredefinedMenuItem::separator(app)?,
            &MenuItem::with_id(app, "quit", "退出", true, Some("CmdOrCtrl+Q"))?,
        ],
    )?;

    // 2. 文件 (File)
    let file_menu = Submenu::with_items(
        app,
        "文件",
        true,
        &[
            &MenuItem::with_id(app, "new-conversation", "新建对话", true, Some("CmdOrCtrl+N"))?,
            &PredefinedMenuItem::separator(app)?,
            &MenuItem::with_id(app, "open-file", "打开文件...", true, Some("CmdOrCtrl+O"))?,
            &PredefinedMenuItem::separator(app)?,
            &MenuItem::with_id(app, "export-word", "导出为 Word", true, Some("CmdOrCtrl+E"))?,
        ],
    )?;

    // 3. 编辑 (Edit) — predefined items for browser default behavior
    let edit_menu = Submenu::with_items(
        app,
        "编辑",
        true,
        &[
            &PredefinedMenuItem::undo(app, Some("撤销"))?,
            &PredefinedMenuItem::redo(app, Some("重做"))?,
            &PredefinedMenuItem::separator(app)?,
            &PredefinedMenuItem::cut(app, Some("剪切"))?,
            &PredefinedMenuItem::copy(app, Some("复制"))?,
            &PredefinedMenuItem::paste(app, Some("粘贴"))?,
            &PredefinedMenuItem::select_all(app, Some("全选"))?,
        ],
    )?;

    // 4. 视图 (View) — theme submenu + zoom + fullscreen
    let theme_submenu = Submenu::with_items(
        app,
        "主题",
        true,
        &[
            &MenuItem::with_id(app, "theme-a", "传统律所 (A)", true, None::<&str>)?,
            &MenuItem::with_id(app, "theme-b", "深色法务终端 (B)", true, None::<&str>)?,
            &MenuItem::with_id(app, "theme-c", "克制现代 (C)", true, None::<&str>)?,
        ],
    )?;

    let view_menu = Submenu::with_items(
        app,
        "视图",
        true,
        &[
            &theme_submenu,
            &PredefinedMenuItem::separator(app)?,
            &MenuItem::with_id(app, "zoom-in", "放大", true, Some("CmdOrCtrl+="))?,
            &MenuItem::with_id(app, "zoom-out", "缩小", true, Some("CmdOrCtrl+-"))?,
            &MenuItem::with_id(app, "actual-size", "实际大小", true, Some("CmdOrCtrl+0"))?,
            &PredefinedMenuItem::separator(app)?,
            &MenuItem::with_id(app, "toggle-fullscreen", "切换全屏", true, Some("F11"))?,
        ],
    )?;

    // 5. 窗口 (Window)
    let window_menu = Submenu::with_items(
        app,
        "窗口",
        true,
        &[
            &MenuItem::with_id(app, "minimize", "最小化", true, Some("CmdOrCtrl+M"))?,
            &MenuItem::with_id(app, "maximize", "最大化", true, None::<&str>)?,
            &PredefinedMenuItem::separator(app)?,
            &MenuItem::with_id(app, "close-window", "关闭窗口", true, Some("CmdOrCtrl+W"))?,
        ],
    )?;

    // 6. 帮助 (Help)
    let help_menu = Submenu::with_items(
        app,
        "帮助",
        true,
        &[
            &MenuItem::with_id(
                app,
                "search-workspace",
                "搜索工作区文件",
                true,
                Some("CmdOrCtrl+Shift+F"),
            )?,
            &PredefinedMenuItem::separator(app)?,
            &MenuItem::with_id(app, "check-update", "检查更新", true, None::<&str>)?,
        ],
    )?;

    // Assemble all menus into the menu bar
    let menu = Menu::with_items(
        app,
        &[
            &app_menu,
            &file_menu,
            &edit_menu,
            &view_menu,
            &window_menu,
            &help_menu,
        ],
    )?;

    Ok(menu)
}

/// Handle menu events by forwarding them to the frontend.
///
/// Each menu item's ID is emitted as a "menu-event" payload.
/// The frontend's `menuHandlers.ts` listens for this event and
/// dispatches to the appropriate callback.
pub fn on_menu_event(app: &AppHandle<tauri::Wry>, event: &tauri::menu::MenuEvent) {
    let id = event.id().as_ref();
    let _ = app.emit("menu-event", id);
}
