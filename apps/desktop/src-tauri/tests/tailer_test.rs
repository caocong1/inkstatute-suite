//! Phase 124 / Plan 124-01 Task 4: real-engine log tail integration.
//!
//! Assembles + spawns the real DSH engine, opens a session, sends a prompt
//! with a **fake** API key (a failed turn still produces the full event stream
//! up to `turn/end` with `reason.kind == "error"`), and asserts the tailer
//! observes the expected event kinds. Also records the `session.jsonl` byte
//! size for the volume assessment written into the phase SUMMARY.
//!
//! `#[ignore]` — requires network (npm assemble) and node. Run with:
//!   cargo test -- --ignored tail_real_engine_session

use std::env;
use std::fs;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

use inkstatute_desktop_lib::engine::acp::PermissionDecision;
use inkstatute_desktop_lib::engine::assemble::{assemble, AssembleOptions};
use inkstatute_desktop_lib::engine::credentials::Provider;
use inkstatute_desktop_lib::engine::events::{SessionEvent, SessionEventKind};
use inkstatute_desktop_lib::engine::lock::EngineLock;
use inkstatute_desktop_lib::engine::paths;
use inkstatute_desktop_lib::engine::supervisor::{EngineSupervisor, SpawnConfig};
use inkstatute_desktop_lib::engine::tailer::{tail_session, TailedEvent};

fn repo_root() -> PathBuf {
    let manifest = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    manifest.parent().unwrap().parent().unwrap().parent().unwrap().to_path_buf()
}

fn node_bin() -> PathBuf {
    if let Ok(override_bin) = env::var("INKSTATUTE_NODE_BIN") {
        return PathBuf::from(override_bin);
    }
    paths::node_binary_for_test().expect("node binary")
}

#[ignore = "requires network and node"]
#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn tail_real_engine_session() {
    let temp = env::temp_dir().join(format!("inkstatute-tail-real-{}", std::process::id()));
    fs::remove_dir_all(&temp).ok();
    env::set_var("INKSTATUTE_APP_ROOT", &temp);

    // Assemble the real engine from the pinned lockfile.
    let lock_path = repo_root().join("engines/engine-lock.json");
    let cordis_path = repo_root().join("engines/acp.cordis.yml");
    let lock_text = fs::read_to_string(&lock_path).expect("read engine-lock.json");
    let lock = EngineLock::from_json(&lock_text).expect("parse engine-lock.json");
    let cordis_yml = fs::read_to_string(&cordis_path).expect("read acp.cordis.yml");
    let engine_dest = temp.join("engine");
    let opts = AssembleOptions {
        registry: "https://registry.npmmirror.com".to_string(),
        registry_fallback: "https://registry.npmjs.org".to_string(),
        concurrency: 8,
    };
    assemble(&lock, &cordis_yml, &engine_dest, &opts, |_p| {})
        .await
        .expect("assemble engine");

    // Use a fake API key — a failed turn still produces the full event stream.
    env::set_var("INKSTATUTE_TEST_API_KEY", "sk-fake-tail-real-engine-test");

    let dsh_home = paths::dsh_home().expect("dsh_home");
    fs::create_dir_all(&dsh_home).unwrap();
    let sessions_root = paths::sessions_root().expect("sessions_root");
    fs::create_dir_all(&sessions_root).unwrap();

    let mut supervisor = EngineSupervisor::spawn(SpawnConfig {
        engine_dir: engine_dest.clone(),
        node_bin: node_bin(),
        dsh_home: dsh_home.clone(),
        provider: Provider::DeepSeek,
    })
    .await
    .expect("spawn engine");

    let _health = supervisor
        .health_probe(Duration::from_secs(30))
        .await
        .expect("health probe");
    let client = supervisor.acp_client();

    let workspace = temp.join("workspaces/tail-real");
    fs::create_dir_all(&workspace).unwrap();
    let session_id = client
        .new_session(&workspace)
        .await
        .expect("new session");

    // Start tailing before sending the prompt so we capture the header.
    let mut tail = tail_session(
        sessions_root.clone(),
        session_id.clone(),
        Duration::from_secs(30),
    );

    // Send a prompt with the fake key. The turn will fail (AUTH) but the full
    // event stream (turn/start, step/start, user/message, session/title,
    // request/header, request/context, turn/end error) is still written.
    let client_for_prompt = Arc::clone(&client);
    let sid = session_id.clone();
    let mut prompt_task = tokio::spawn(async move {
        client_for_prompt.prompt(&sid, "请总结买卖合同违约案件的关键证据。").await
    });

    let mut permission_rx = client.subscribe_permissions();
    let mut updates_rx = client.subscribe_updates();

    // Collect tailed events until we see TurnEnd, with a 30s hard cap.
    let mut got_header = false;
    let mut got_turn_start = false;
    let mut got_step_start = false;
    let mut got_real_user_message = false;
    let mut got_session_title = false;
    let mut got_request_header = false;
    let mut got_request_context = false;
    let mut got_turn_end = false;
    let mut real_user_message_count = 0usize;
    let mut other_event_count = 0usize;

    let deadline = tokio::time::Instant::now() + Duration::from_secs(30);
    loop {
        if tokio::time::Instant::now() >= deadline {
            break;
        }
        let remaining = deadline.saturating_duration_since(tokio::time::Instant::now());
        tokio::select! {
            ev = tokio::time::timeout(remaining, tail.events.recv()) => {
                match ev {
                    Ok(Some(TailedEvent::Header(_))) => got_header = true,
                    Ok(Some(TailedEvent::Event(ev))) => {
                        match ev.kind {
                            SessionEventKind::TurnStart => got_turn_start = true,
                            SessionEventKind::StepStart => got_step_start = true,
                            SessionEventKind::UserMessage => {
                                if ev.is_real_user_message() {
                                    got_real_user_message = true;
                                    real_user_message_count += 1;
                                }
                            }
                            SessionEventKind::SessionTitle => got_session_title = true,
                            SessionEventKind::RequestHeader => got_request_header = true,
                            SessionEventKind::RequestContext => got_request_context = true,
                            SessionEventKind::TurnEnd => got_turn_end = true,
                            _ => other_event_count += 1,
                        }
                    }
                    Ok(Some(_)) | Ok(None) | Err(_) => {}
                }
            }
            Ok(update) = updates_rx.recv() => {
                // Drain ACP updates so the prompt task can progress; not asserted here.
                let _ = update;
            }
            Ok(req) = permission_rx.recv() => {
                let _ = client
                    .respond_permission(req.request_id, PermissionDecision::RejectOnce)
                    .await;
            }
            res = &mut prompt_task => {
                let _ = res; // prompt result is irrelevant for the tail assertion
                // Keep draining the tail a bit longer to catch trailing events.
                let tail_grace = tokio::time::Instant::now() + Duration::from_secs(3);
                while tokio::time::Instant::now() < tail_grace && !got_turn_end {
                    if let Ok(Some(ev)) = tokio::time::timeout(
                        Duration::from_millis(200),
                        tail.events.recv(),
                    ).await {
                        match ev {
                            TailedEvent::Event(SessionEvent { kind: SessionEventKind::TurnEnd, .. }) => got_turn_end = true,
                            TailedEvent::Event(_) => other_event_count += 1,
                            _ => {}
                        }
                    }
                }
                break;
            }
        }
    }

    // Locate the session.jsonl file to record its byte size for the volume
    // assessment written into the phase SUMMARY.
    let mut jsonl_bytes: Option<u64> = None;
    if let Ok(entries) = fs::read_dir(&sessions_root) {
        for entry in entries.flatten() {
            let candidate = entry.path().join(&session_id).join("session.jsonl");
            if candidate.is_file() {
                if let Ok(meta) = fs::metadata(&candidate) {
                    jsonl_bytes = Some(meta.len());
                }
                break;
            }
        }
    }

    // Shut the engine down before assertions so a failure doesn't leak a child.
    let _ = supervisor.shutdown().await;
    let _ = supervisor.assert_no_orphans().await;
    env::remove_var("INKSTATUTE_APP_ROOT");
    env::remove_var("INKSTATUTE_TEST_API_KEY");
    fs::remove_dir_all(&temp).ok();

    println!(
        "tail_real_engine_session: jsonl_bytes={:?} other_event_count={}",
        jsonl_bytes, other_event_count
    );

    assert!(got_header, "missing Header");
    assert!(got_turn_start, "missing TurnStart");
    assert!(got_step_start, "missing StepStart");
    assert!(
        got_real_user_message,
        "missing real user/message (is_real_user_message)"
    );
    assert_eq!(
        real_user_message_count, 1,
        "exactly one real user message expected, got {real_user_message_count}"
    );
    assert!(got_session_title, "missing SessionTitle");
    assert!(got_request_header, "missing RequestHeader");
    assert!(got_request_context, "missing RequestContext");
    assert!(got_turn_end, "missing TurnEnd");
}
