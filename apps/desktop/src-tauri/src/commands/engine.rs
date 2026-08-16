//! Tauri commands for engine control: start, status, send, cancel, permission.
//!
//! The engine supervisor is owned by a `State<EngineState>` managed by Tauri.
//! Only one engine instance exists per app lifetime.

use serde::Serialize;
use tauri::{AppHandle, Emitter, State};
use tokio::sync::RwLock;

use crate::engine::credentials::{has_key, Provider};
use crate::engine::paths;
use crate::engine::session_map::SessionMap;
use crate::engine::supervisor::{EngineSupervisor, SpawnConfig};
use crate::engine::acp::PermissionDecision;
use crate::engine::EngineError;

/// Persistent engine state managed by Tauri.
pub struct EngineState {
    supervisor: RwLock<Option<EngineSupervisor>>,
    sessions: SessionMap,
    /// Live observation handles keyed by conversation id. ObservationHandle
    /// sets its stop flag on Drop, so the handle MUST be kept alive here —
    /// discarding start_observation()'s return value (the original bug) stops
    /// the tail loop in the same statement it was started in, and the UI never
    /// receives a single engine event. Inserting for the same conversation
    /// drops the previous handle, which is exactly the stop we want then.
    observations: tokio::sync::Mutex<std::collections::HashMap<String, crate::engine::runtime::ObservationHandle>>,
}

impl EngineState {
    pub fn new() -> Self {
        Self {
            supervisor: RwLock::new(None),
            sessions: SessionMap::new(),
            observations: tokio::sync::Mutex::new(std::collections::HashMap::new()),
        }
    }
}

impl Default for EngineState {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Serialize, Default)]
pub struct EngineStatus {
    pub running: bool,
    pub engine_version: String,
    pub agent_name: String,
    pub failure: String,
}

/// Start the engine child process and initialize the ACP session.
#[tauri::command]
pub async fn engine_start(
    app: AppHandle,
    state: State<'_, EngineState>,
) -> Result<EngineStatus, String> {
    let mut guard = state.supervisor.write().await;
    if guard.is_some() {
        return Ok(EngineStatus {
            running: true,
            ..Default::default()
        });
    }

    let engine_dir = {
        let version = paths::read_current()
            .map_err(|e| format!("引擎版本未找到：{}", e))?
            .ok_or("引擎未装配，请先运行引擎装配")?;
        paths::engine_dir(&version)
            .map_err(|e| format!("引擎目录未找到：{}", e))?
    };

    let node_bin = paths::node_binary()
        .map_err(|e| format!("Node.js 未找到：{}", e))?;

    let dsh_home = paths::dsh_home()
        .map_err(|e| format!("无法获取 DSH 主目录：{}", e))?;
    std::fs::create_dir_all(&dsh_home)
        .map_err(|e| format!("无法创建 DSH 主目录：{}", e))?;

    let provider = select_provider()
        .map_err(|e| format!("未配置 API 密钥：{}", e))?;

    let cfg = SpawnConfig {
        engine_dir,
        node_bin,
        dsh_home,
        provider,
    };

    let sup = EngineSupervisor::spawn(cfg)
        .await
        .map_err(|e| format!("引擎启动失败：{}", e))?;

    let health = sup
        .acp_client()
        .initialize(std::time::Duration::from_secs(30))
        .await
        .map_err(|e| format!("引擎握手失败：{}", e))?;

    let status = EngineStatus {
        running: true,
        engine_version: health.agent_info.version.clone(),
        agent_name: health.agent_info.name.clone(),
        failure: String::new(),
    };

    *guard = Some(sup);
    drop(guard);
    Ok(status)
}

/// Get current engine status.
#[tauri::command]
pub async fn engine_status(state: State<'_, EngineState>) -> Result<EngineStatus, String> {
    let guard = state.supervisor.read().await;
    Ok(if guard.is_some() {
        EngineStatus {
            running: true,
            ..Default::default()
        }
    } else {
        EngineStatus::default()
    })
}

/// Send a prompt to the engine for the given conversation.
/// Creates an ACP session lazily if needed and starts observation.
#[tauri::command]
pub async fn engine_send(
    conversation_id: String,
    text: String,
    state: State<'_, EngineState>,
    app: AppHandle,
) -> Result<(), String> {
    let guard = state.supervisor.read().await;
    let sup = guard.as_ref().ok_or("引擎未启动")?;
    let acp = sup.acp_client();

    // Per-conversation workspace: the DSH file sandbox (workspace-write) is
    // scoped to the session cwd. Using the process cwd here handed the agent
    // the entire source tree in dev, and let AGENTS.md leak into its context
    // via workspaceContext.
    let cwd = paths::app_root()
        .map_err(|e| format!("无法获取应用目录：{}", e))?
        .join("workspaces")
        .join(&conversation_id);
    std::fs::create_dir_all(&cwd).map_err(|e| format!("无法创建工作区：{}", e))?;
    let session_id = state
        .sessions
        .ensure(&conversation_id, &cwd, &acp)
        .await
        .map_err(|e| format!("创建会话失败：{}", e))?;

    // Start observing this session's log
    let sessions_root = paths::sessions_root()
        .map_err(|e| format!("无法获取会话目录：{}", e))?;
    let handle = crate::engine::runtime::start_observation(
        app.clone(),
        sessions_root,
        session_id.clone(),
        conversation_id.clone(),
    );
    state
        .observations
        .lock()
        .await
        .insert(conversation_id.clone(), handle);

    // Emit a session.started event so the UI knows the run is active
    let _ = app.emit(
        crate::engine::runtime::RUN_EVENT_CHANNEL,
        &serde_json::json!({
            "event_id": format!("evt-{}", uuid::Uuid::new_v4()),
            "run_id": conversation_id,
            "event_type": "session.started",
            "occurred_at": chrono::Utc::now().to_rfc3339(),
            "seq": 0,
            "payload": null,
            "metadata": { "conversation_id": conversation_id }
        }),
    );

    // Send the prompt (updates arrive via session log observation)
    acp.prompt(&session_id, &text)
        .await
        .map_err(|e| format!("发送消息失败：{}", e))?;

    Ok(())
}

/// Cancel the current run for a conversation.
#[tauri::command]
pub async fn engine_cancel(
    conversation_id: String,
    state: State<'_, EngineState>,
) -> Result<(), String> {
    let guard = state.supervisor.read().await;
    let sup = guard.as_ref().ok_or("引擎未启动")?;
    let acp = sup.acp_client();

    if let Some(entry) = state.sessions.get(&conversation_id) {
        acp.cancel(&entry.acp_session_id)
            .await
            .map_err(|e| format!("取消失败：{}", e))?;
    }
    Ok(())
}

/// Respond to a permission request (allow/deny).
#[tauri::command]
pub async fn engine_respond_permission(
    request_id: i64,
    allow: bool,
    state: State<'_, EngineState>,
) -> Result<(), String> {
    let guard = state.supervisor.read().await;
    let sup = guard.as_ref().ok_or("引擎未启动")?;
    let acp = sup.acp_client();

    let decision = if allow {
        PermissionDecision::AllowOnce
    } else {
        PermissionDecision::RejectOnce
    };
    acp.respond_permission(request_id, decision)
        .await
        .map_err(|e| format!("权限响应失败：{}", e))?;
    Ok(())
}

// --- Helpers ---

fn select_provider() -> Result<Provider, EngineError> {
    let all = Provider::all();
    for p in all {
        if p.id() == "deepseek" && has_key(*p) {
            return Ok(*p);
        }
    }
    for p in all {
        if has_key(*p) {
            return Ok(*p);
        }
    }
    Err(EngineError::MissingApiKey("deepseek".to_string()))
}
