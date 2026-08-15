use std::collections::{HashMap, HashSet};
use std::path::Path;
use std::sync::atomic::{AtomicI64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{ChildStdin, ChildStdout};
use tokio::sync::{broadcast, oneshot};
use tokio::time::timeout;

use super::EngineError;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentInfo {
    pub name: String,
    pub version: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InitializeResult {
    #[serde(rename = "protocolVersion")]
    pub protocol_version: u32,
    #[serde(rename = "agentInfo")]
    pub agent_info: AgentInfo,
    #[serde(default, rename = "authMethods")]
    pub auth_methods: Vec<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NewSessionResult {
    #[serde(rename = "sessionId")]
    pub session_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PromptResult {
    #[serde(rename = "stopReason")]
    pub stop_reason: String,
}

#[derive(Debug, Clone)]
pub enum SessionUpdate {
    AgentMessageChunk { session_id: String, text: String },
    /// Contains the prompt header returned by the model router, including
    /// token counts and model metadata.
    RequestHeader { session_id: String, header: Value },
    Unknown { session_id: String, raw: Value },
}

#[derive(Debug, Clone)]
pub struct PermissionOption {
    pub option_id: String,
    pub name: String,
    pub kind: Option<String>,
}

#[derive(Debug, Clone)]
pub struct PermissionRequest {
    pub request_id: i64,
    pub session_id: String,
    pub tool_call_id: Option<String>,
    pub tool_name: Option<String>,
    pub options: Vec<PermissionOption>,
    pub raw: Value,
}

#[derive(Debug, Clone, Copy)]
pub enum PermissionDecision {
    AllowOnce,
    RejectOnce,
}

impl PermissionDecision {
    fn option_id(&self) -> &'static str {
        match self {
            PermissionDecision::AllowOnce => "allow-once",
            PermissionDecision::RejectOnce => "reject-once",
        }
    }
}

#[derive(Debug, Clone)]
struct JsonRpcError {
    code: i64,
    message: String,
}

impl std::fmt::Display for JsonRpcError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "JSON-RPC error {}: {}", self.code, self.message)
    }
}

pub struct AcpClient {
    next_id: AtomicI64,
    pending: Arc<Mutex<HashMap<i64, oneshot::Sender<Result<Value, JsonRpcError>>>>>,
    stdin: Arc<tokio::sync::Mutex<Option<ChildStdin>>>,
    in_flight: Arc<Mutex<HashSet<String>>>,
    updates_tx: broadcast::Sender<SessionUpdate>,
    permissions_tx: broadcast::Sender<PermissionRequest>,
    _read_handle: Arc<tokio::task::JoinHandle<()>>,
    _close_tx: Option<oneshot::Sender<()>>,
}

impl AcpClient {
    /// Takes ownership of the engine's stdin/stdout and starts the read loop.
    pub fn new(stdin: ChildStdin, stdout: ChildStdout) -> Self {
        let next_id = AtomicI64::new(1);
        let pending: Arc<Mutex<HashMap<i64, oneshot::Sender<Result<Value, JsonRpcError>>>>> =
            Arc::new(Mutex::new(HashMap::new()));
        let pending_clone = pending.clone();
        let in_flight = Arc::new(Mutex::new(HashSet::new()));

        let (updates_tx, _) = broadcast::channel::<SessionUpdate>(256);
        let (permissions_tx, _) = broadcast::channel::<PermissionRequest>(32);

        let (close_tx, close_rx) = oneshot::channel::<()>();

        let updates_for_task = updates_tx.clone();
        let permissions_for_task = permissions_tx.clone();

        let handle = tokio::spawn(read_loop(
            stdout,
            pending_clone,
            updates_for_task,
            permissions_for_task,
            close_rx,
        ));

        Self {
            next_id,
            pending,
            stdin: Arc::new(tokio::sync::Mutex::new(Some(stdin))),
            in_flight,
            updates_tx,
            permissions_tx,
            _read_handle: Arc::new(handle),
            _close_tx: Some(close_tx),
        }
    }

    pub async fn initialize(&self, dur: Duration) -> Result<InitializeResult, EngineError> {
        let params = json!({
            "protocolVersion": 1,
            "clientCapabilities": {
                "fs": { "readTextFile": false, "writeTextFile": false },
                "terminal": false
            }
        });
        let value = self.request("initialize", params, dur).await?;
        let init: InitializeResult = serde_json::from_value(value)
            .map_err(|e| EngineError::Protocol(format!("invalid initialize response: {e}")))?;
        Ok(init)
    }

    pub async fn new_session(&self, cwd: &Path) -> Result<String, EngineError> {
        if !cwd.is_absolute() {
            return Err(EngineError::CwdNotAbsolute);
        }
        let params = json!({
            "cwd": cwd.to_string_lossy(),
            "mcpServers": []
        });
        let value = self.request("session/new", params, Duration::from_secs(30)).await?;
        let res: NewSessionResult = serde_json::from_value(value)
            .map_err(|e| EngineError::Protocol(format!("invalid session/new response: {e}")))?;
        Ok(res.session_id)
    }

    pub async fn prompt(&self, session_id: &str, text: &str) -> Result<PromptResult, EngineError> {
        {
            let mut guard = self.in_flight.lock().unwrap();
            if guard.contains(session_id) {
                return Err(EngineError::PromptInFlight(session_id.to_string()));
            }
            guard.insert(session_id.to_string());
        }

        let params = json!({
            "sessionId": session_id,
            "prompt": [{"type": "text", "text": text}]
        });

        let result = self
            .request("session/prompt", params, Duration::from_secs(300))
            .await;

        {
            let mut guard = self.in_flight.lock().unwrap();
            guard.remove(session_id);
        }

        match result {
            Ok(value) => {
                let res: PromptResult = serde_json::from_value(value)
                    .map_err(|e| EngineError::Protocol(format!("invalid prompt response: {e}")))?;
                Ok(res)
            }
            Err(e) => Err(e),
        }
    }

    /// `session/cancel` is a JSON-RPC **notification**, not a request.
    /// Real-engine measurement: sending with an `id` returns
    /// `{"error":{"code":-32601,"message":"Method not found: session/cancel"}}`
    /// and the in-flight prompt is left hanging. The correct form has no `id`.
    pub async fn cancel(&self, session_id: &str) -> Result<(), EngineError> {
        self.notify("session/cancel", json!({"sessionId": session_id}))
            .await
    }

    pub fn subscribe_updates(&self) -> broadcast::Receiver<SessionUpdate> {
        self.updates_tx.subscribe()
    }

    pub fn subscribe_permissions(&self) -> broadcast::Receiver<PermissionRequest> {
        self.permissions_tx.subscribe()
    }

    pub async fn respond_permission(
        &self,
        request_id: i64,
        decision: PermissionDecision,
    ) -> Result<(), EngineError> {
        let result = json!({
            "outcome": {
                "outcome": "selected",
                "optionId": decision.option_id()
            }
        });
        self.respond(request_id, result, Duration::from_secs(10))
            .await
    }

    /// Drops the engine's stdin, causing the child to receive EOF.
    pub async fn close(&self) {
        let _ = self.stdin.lock().await.take();
    }

    async fn request(
        &self,
        method: &str,
        params: Value,
        dur: Duration,
    ) -> Result<Value, EngineError> {
        let id = self.next_id.fetch_add(1, Ordering::SeqCst);
        let (tx, rx) = oneshot::channel();
        {
            let mut guard = self.pending.lock().unwrap();
            guard.insert(id, tx);
        }

        let frame = json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": method,
            "params": params
        });

        if let Err(e) = self.send_frame(&frame).await {
            let mut guard = self.pending.lock().unwrap();
            guard.remove(&id);
            return Err(e);
        }

        match timeout(dur, rx).await {
            Ok(Ok(Ok(value))) => Ok(value),
            Ok(Ok(Err(rpc_err))) => Err(EngineError::Protocol(rpc_err.to_string())),
            Ok(Err(_)) => Err(EngineError::Disconnected),
            Err(_) => {
                // Timeout: stop tracking to avoid stale entries.
                let mut guard = self.pending.lock().unwrap();
                guard.remove(&id);
                Err(EngineError::Protocol(format!("request {method} timed out")))
            }
        }
    }

    async fn notify(&self, method: &str, params: Value) -> Result<(), EngineError> {
        let frame = json!({
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        });
        self.send_frame(&frame).await
    }

    async fn respond(
        &self,
        request_id: i64,
        result: Value,
        dur: Duration,
    ) -> Result<(), EngineError> {
        let frame = json!({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        });
        // Responses are one-way; we do not expect a reply.
        self.send_frame(&frame).await
    }

    async fn send_frame(&self, frame: &Value) -> Result<(), EngineError> {
        let mut text = serde_json::to_string(frame)
            .map_err(|e| EngineError::Json(e))?;
        text.push('\n');
        let mut guard = self.stdin.lock().await;
        let stdin = guard
            .as_mut()
            .ok_or(EngineError::Disconnected)?;
        stdin.write_all(text.as_bytes()).await?;
        stdin.flush().await?;
        Ok(())
    }
}

async fn read_loop(
    stdout: ChildStdout,
    pending: Arc<Mutex<HashMap<i64, oneshot::Sender<Result<Value, JsonRpcError>>>>>,
    updates_tx: broadcast::Sender<SessionUpdate>,
    permissions_tx: broadcast::Sender<PermissionRequest>,
    mut close_rx: oneshot::Receiver<()>,
) {
    let mut reader = BufReader::new(stdout).lines();

    loop {
        tokio::select! {
            _ = &mut close_rx => break,
            line = reader.next_line() => match line {
                Ok(Some(line)) => handle_line(&line, &pending, &updates_tx, &permissions_tx),
                Ok(None) => break,
                Err(_) => break,
            },
        }
    }

    // Settle all pending requests as Disconnected by dropping their oneshot
    // senders; the receiver turns a Canceled into EngineError::Disconnected.
    let mut guard = pending.lock().unwrap();
    for (_, tx) in guard.drain() {
        drop(tx);
    }
}

fn handle_line(
    line: &str,
    pending: &Mutex<HashMap<i64, oneshot::Sender<Result<Value, JsonRpcError>>>>,
    updates_tx: &broadcast::Sender<SessionUpdate>,
    permissions_tx: &broadcast::Sender<PermissionRequest>,
) {
    let value: Value = match serde_json::from_str(line) {
        Ok(v) => v,
        Err(_) => return, // Non-JSON lines are ignored (engine occasionally prints to stdout).
    };

    let id = value.get("id").and_then(|v| v.as_i64());
    let method = value.get("method").and_then(|v| v.as_str());

    match (id, method) {
        (Some(request_id), Some("session/request_permission")) => {
            if let Ok(req) = parse_permission_request(request_id, &value) {
                let _ = permissions_tx.send(req);
            }
        }
        (Some(request_id), Some(_)) => {
            // Unknown server-to-client request; ignore to avoid hanging.
        }
        (Some(response_id), None) => {
            let mut guard = pending.lock().unwrap();
            if let Some(tx) = guard.remove(&response_id) {
                if let Some(error) = value.get("error") {
                    let code = error.get("code").and_then(|v| v.as_i64()).unwrap_or(-32603);
                    let message = error
                        .get("message")
                        .and_then(|v| v.as_str())
                        .unwrap_or("unknown error")
                        .to_string();
                    let _ = tx.send(Err(JsonRpcError { code, message }));
                } else if let Some(result) = value.get("result") {
                    let _ = tx.send(Ok(result.clone()));
                } else {
                    let _ = tx.send(Err(JsonRpcError {
                        code: -32603,
                        message: "response missing result and error".to_string(),
                    }));
                }
            }
        }
        (None, Some("session/update")) => {
            if let Some(params) = value.get("params") {
                let session_id = params
                    .get("sessionId")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                if let Some(update) = params.get("update") {
                    if let Some(session_update) = update.get("sessionUpdate").and_then(|v| v.as_str()) {
                        if session_update == "agent_message_chunk" {
                            if let Some(content) = update.get("content") {
                                let text = content
                                    .get("text")
                                    .and_then(|v| v.as_str())
                                    .unwrap_or("")
                                    .to_string();
                                let _ = updates_tx.send(SessionUpdate::AgentMessageChunk {
                                    session_id,
                                    text,
                                });
                                return;
                            }
                        } else if session_update == "request/header" {
                            let _ = updates_tx.send(SessionUpdate::RequestHeader {
                                session_id,
                                header: update.clone(),
                            });
                            return;
                        }
                    }
                }
                let _ = updates_tx.send(SessionUpdate::Unknown {
                    session_id,
                    raw: value.clone(),
                });
            }
        }
        (None, Some(_)) | (_, _) => {
            // Ignore other notifications and malformed frames.
        }
    }
}

fn parse_permission_request(request_id: i64, value: &Value) -> Result<PermissionRequest, EngineError> {
    let params = value
        .get("params")
        .ok_or_else(|| EngineError::Protocol("permission request missing params".to_string()))?;
    let session_id = params
        .get("sessionId")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let tool_call_id = params
        .get("toolCall")
        .and_then(|v| v.get("toolCallId"))
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());
    let tool_name = params
        .get("tool")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());
    let raw_options = params
        .get("options")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let mut options = Vec::new();
    for opt in raw_options {
        let option_id = opt
            .get("optionId")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let name = opt
            .get("name")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let kind = opt.get("kind").and_then(|v| v.as_str()).map(|s| s.to_string());
        options.push(PermissionOption { option_id, name, kind });
    }
    Ok(PermissionRequest {
        request_id,
        session_id,
        tool_call_id,
        tool_name,
        options,
        raw: value.clone(),
    })
}

#[cfg(test)]
mod tests {
    // ACP client integration tests live in tests/acp_client_test.rs.
}
