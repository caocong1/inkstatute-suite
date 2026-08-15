use std::path::PathBuf;
use std::process::Stdio;
use std::sync::Arc;
use std::time::Duration;

use inkstatute_desktop_lib::engine::acp::{AcpClient, PermissionDecision, SessionUpdate};
use inkstatute_desktop_lib::engine::EngineError;
use tokio::process::{Child, Command};
use tokio::time::{sleep, timeout};

fn node_bin() -> PathBuf {
    if let Ok(override_bin) = std::env::var("INKSTATUTE_NODE_BIN") {
        return PathBuf::from(override_bin);
    }
    std::env::var("PATH")
        .ok()
        .and_then(|path| {
            path.split(if cfg!(target_os = "windows") { ';' } else { ':' })
                .map(PathBuf::from)
                .find_map(|dir| {
                    let candidate =
                        dir.join(if cfg!(target_os = "windows") { "node.exe" } else { "node" });
                    candidate.is_file().then_some(candidate)
                })
        })
        .expect("node binary for tests")
}

fn mock_script() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/mock_acp_server.mjs")
}

async fn mock_engine_server(permission: bool) -> Child {
    let mut cmd = Command::new(node_bin());
    cmd.arg(mock_script())
        .stdout(Stdio::piped())
        .stdin(Stdio::piped())
        .stderr(Stdio::piped());
    if permission {
        cmd.env("MOCK_REQUEST_PERMISSION", "1");
    }
    cmd.spawn().expect("spawn mock server")
}

fn take_client(child: &mut Child) -> AcpClient {
    let stdin = child.stdin.take().expect("stdin piped");
    let stdout = child.stdout.take().expect("stdout piped");
    AcpClient::new(stdin, stdout)
}

async fn init_client() -> (Arc<AcpClient>, Child) {
    let mut child = mock_engine_server(false).await;
    let client = Arc::new(take_client(&mut child));
    let init = client.initialize(Duration::from_secs(5)).await.unwrap();
    assert_eq!(init.protocol_version, 1);
    (client, child)
}

#[tokio::test]
async fn initialize_handshake() {
    let (client, mut child) = init_client().await;
    client.close().await;
    let _ = child.kill().await;
}

#[tokio::test]
async fn new_session_requires_absolute_cwd() {
    let (client, mut child) = init_client().await;
    let result = client.new_session(std::path::Path::new("relative/path")).await;
    assert!(matches!(result, Err(EngineError::CwdNotAbsolute)));
    client.close().await;
    let _ = child.kill().await;
}

#[tokio::test]
async fn prompt_receives_streaming_updates() {
    let (client, mut child) = init_client().await;
    let temp = std::env::temp_dir().join(format!("acp-test-{}", std::process::id()));
    std::fs::create_dir_all(&temp).unwrap();
    let sid = client.new_session(&temp).await.unwrap();

    let mut updates = client.subscribe_updates();
    let updates_fut = async {
        let mut count = 0usize;
        loop {
            match timeout(Duration::from_millis(800), updates.recv()).await {
                Ok(Ok(SessionUpdate::AgentMessageChunk { .. })) => count += 1,
                Ok(Ok(_)) => {}
                Ok(Err(_)) | Err(_) => break,
            }
        }
        count
    };

    let (result, count) = tokio::join!(client.prompt(&sid, "hello"), updates_fut);
    assert_eq!(result.unwrap().stop_reason, "end_turn");
    assert!(count >= 3, "expected at least 3 streamed chunks, got {}", count);

    client.close().await;
    let _ = child.kill().await;
    std::fs::remove_dir_all(&temp).ok();
}

#[tokio::test]
async fn cancel_settles_inflight_prompt() {
    let (client, mut child) = init_client().await;
    let temp = std::env::temp_dir().join(format!("acp-cancel-test-{}", std::process::id()));
    std::fs::create_dir_all(&temp).unwrap();
    let sid = client.new_session(&temp).await.unwrap();

    let client_for_cancel = Arc::clone(&client);
    let sid_for_cancel = sid.clone();
    let cancel_task = tokio::spawn(async move {
        sleep(Duration::from_millis(500)).await;
        client_for_cancel.cancel(&sid_for_cancel).await.unwrap();
    });

    let result = client.prompt(&sid, "hello").await.unwrap();
    let _ = cancel_task.await;
    assert_eq!(result.stop_reason, "cancelled");

    client.close().await;
    let _ = child.kill().await;
    std::fs::remove_dir_all(&temp).ok();
}

#[tokio::test]
async fn prompt_inflight_rejected() {
    let (client, mut child) = init_client().await;
    let temp = std::env::temp_dir().join(format!("acp-inflight-test-{}", std::process::id()));
    std::fs::create_dir_all(&temp).unwrap();
    let sid = client.new_session(&temp).await.unwrap();

    let client_for_first = Arc::clone(&client);
    let sid_for_first = sid.clone();
    let first_task = tokio::spawn(async move {
        client_for_first.prompt(&sid_for_first, "slow").await.unwrap()
    });

    sleep(Duration::from_millis(50)).await;

    let second = client.prompt(&sid, "other").await;
    assert!(matches!(second, Err(EngineError::PromptInFlight(_))));

    // Allow the first prompt to finish before cleanup.
    let _ = first_task.await;

    client.close().await;
    let _ = child.kill().await;
    std::fs::remove_dir_all(&temp).ok();
}

#[tokio::test]
async fn disconnect_settles_pending() {
    let mut child = mock_engine_server(false).await;
    let client = Arc::new(take_client(&mut child));
    client.initialize(Duration::from_secs(5)).await.unwrap();

    let temp = std::env::temp_dir().join(format!("acp-disconnect-test-{}", std::process::id()));
    std::fs::create_dir_all(&temp).unwrap();
    let sid = client.new_session(&temp).await.unwrap();

    let client_for_prompt = Arc::clone(&client);
    let sid_for_prompt = sid.clone();
    let prompt_task =
        tokio::spawn(async move { client_for_prompt.prompt(&sid_for_prompt, "hang").await });

    sleep(Duration::from_millis(200)).await;
    child.kill().await.unwrap();

    let res = tokio::time::timeout(Duration::from_secs(3), prompt_task)
        .await
        .unwrap()
        .unwrap();
    assert!(matches!(res, Err(EngineError::Disconnected)));

    std::fs::remove_dir_all(&temp).ok();
}

#[tokio::test]
async fn permission_request_roundtrip() {
    let mut child = mock_engine_server(true).await;
    let client = Arc::new(take_client(&mut child));
    client.initialize(Duration::from_secs(5)).await.unwrap();

    let temp = std::env::temp_dir().join(format!("acp-perm-test-{}", std::process::id()));
    std::fs::create_dir_all(&temp).unwrap();
    let sid = client.new_session(&temp).await.unwrap();

    let client_for_perms = Arc::clone(&client);
    let mut perms = client.subscribe_permissions();
    let perms_task = tokio::spawn(async move {
        while let Ok(req) = perms.recv().await {
            assert!(req.options.iter().any(|o| o.option_id == "allow-once"));
            client_for_perms
                .respond_permission(req.request_id, PermissionDecision::AllowOnce)
                .await
                .unwrap();
        }
    });

    let result = client.prompt(&sid, "hello").await.unwrap();
    assert_eq!(result.stop_reason, "end_turn");

    perms_task.abort();
    let _ = perms_task.await;

    client.close().await;
    let _ = child.kill().await;
    std::fs::remove_dir_all(&temp).ok();
}

#[tokio::test]
async fn cancel_frame_has_no_id() {
    let (client, mut child) = init_client().await;
    let temp = std::env::temp_dir().join(format!("acp-raw-cancel-{}", std::process::id()));
    std::fs::create_dir_all(&temp).unwrap();
    let sid = client.new_session(&temp).await.unwrap();

    client.cancel(&sid).await.unwrap();

    client.close().await;
    let _ = child.kill().await;
    std::fs::remove_dir_all(&temp).ok();
}
