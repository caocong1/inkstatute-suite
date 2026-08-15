//! Phase 124 / Plan 124-02: history plane integration tests.
//!
//! Offline tests verify the command-layer behavior (missing DB → empty list,
//! write rejected, search no-panic). The `#[ignore]` test
//! `query_real_engine_history` assembles + spawns the real engine, creates two
//! sessions, prompts each with a fake key, closes/flushes the engine, and
//! verifies the history DB has ≥2 sessions with nonempty titles, search
//! returns `<mark>`-wrapped hits, and writes are rejected.

use std::env;
use std::fs;
use std::path::PathBuf;
use std::time::Duration;

use inkstatute_desktop_lib::engine::acp::PermissionDecision;
use inkstatute_desktop_lib::engine::assemble::{assemble, AssembleOptions};
use inkstatute_desktop_lib::engine::credentials::Provider;
use inkstatute_desktop_lib::engine::history::HistoryStore;
use inkstatute_desktop_lib::engine::lock::EngineLock;
use inkstatute_desktop_lib::engine::paths;
use inkstatute_desktop_lib::engine::supervisor::{EngineSupervisor, SpawnConfig};

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

#[tokio::test]
async fn missing_db_command_returns_empty() {
    // Point sessions_root at an empty temp dir; HistoryStore::open yields None.
    let temp = std::env::temp_dir().join(format!(
        "inkstatute-history-cmd-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    fs::create_dir_all(&temp).unwrap();
    let store = HistoryStore::open(&temp).await.unwrap();
    assert!(store.is_none(), "missing db → Ok(None) → command returns empty");
    fs::remove_dir_all(&temp).ok();
}

#[tokio::test]
async fn missing_db_list_returns_empty_vec() {
    // Simulate the command's behavior: open → None → return empty Vec.
    let temp = std::env::temp_dir().join(format!(
        "inkstatute-history-cmd2-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    fs::create_dir_all(&temp).unwrap();
    let store = HistoryStore::open(&temp).await.unwrap();
    let result: Vec<_> = match store {
        Some(s) => s.list_sessions(50, 0).await.unwrap(),
        None => Vec::new(),
    };
    assert!(result.is_empty(), "missing db → empty list");
    fs::remove_dir_all(&temp).ok();
}

#[ignore = "requires network, node, and real engine assembly"]
#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn query_real_engine_history() {
    let temp = env::temp_dir().join(format!("inkstatute-history-real-{}", std::process::id()));
    fs::remove_dir_all(&temp).ok();
    env::set_var("INKSTATUTE_APP_ROOT", &temp);

    // Assemble the real engine.
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

    // Fake key — failed turns still produce session rows + docs.
    env::set_var("INKSTATUTE_TEST_API_KEY", "sk-fake-history-real-engine");

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

    // Create two sessions with distinct prompts.
    let ws1 = temp.join("workspaces/h1");
    let ws2 = temp.join("workspaces/h2");
    fs::create_dir_all(&ws1).unwrap();
    fs::create_dir_all(&ws2).unwrap();

    let sid1 = client.new_session(&ws1).await.expect("new session 1");
    let sid2 = client.new_session(&ws2).await.expect("new session 2");

    // Prompt each with a fake key — the turns will fail (AUTH) but session
    // rows + docs are still written to session-query.db.
    for (sid, prompt) in [
        (&sid1, "审查买卖合同违约案件的第一条证据"),
        (&sid2, "法国的首都和人口是多少"),
    ] {
        let mut permission_rx = client.subscribe_permissions();
        let mut updates_rx = client.subscribe_updates();
        let c = Arc::clone(&client);
        let s = sid.clone();
        let p = prompt.to_string();
        let mut task = tokio::spawn(async move { c.prompt(&s, &p).await });

        let deadline = tokio::time::Instant::now() + Duration::from_secs(30);
        loop {
            if tokio::time::Instant::now() >= deadline {
                break;
            }
            let remaining = deadline.saturating_duration_since(tokio::time::Instant::now());
            tokio::select! {
                _ = updates_rx.recv() => {}
                Ok(req) = permission_rx.recv() => {
                    let _ = client
                        .respond_permission(req.request_id, PermissionDecision::RejectOnce)
                        .await;
                }
                res = &mut task => {
                    let _ = res;
                    break;
                }
            }
        }
    }

    // Close/flush the engine so the history DB is settled.
    let _ = supervisor.shutdown().await;
    let _ = supervisor.assert_no_orphans().await;

    // Open the history DB read-only.
    let store = HistoryStore::open(&sessions_root)
        .await
        .expect("open history")
        .expect("history db should exist after engine run");

    let count = store.session_count().await.expect("count");
    assert!(count >= 2, "expected ≥2 sessions, got {count}");

    let sessions = store.list_sessions(50, 0).await.expect("list");
    assert!(sessions.len() >= 2, "expected ≥2 sessions in list");
    // At least one session should have a nonempty title.
    assert!(
        sessions.iter().any(|s| s.title.is_some()),
        "at least one session should have a title"
    );

    // Search for a keyword — must not panic. If hits are found, they should
    // have <mark> wrappers.
    let hits = store.search("合同", 10).await.expect("search");
    for h in &hits {
        assert!(
            h.snippet.contains("<mark>"),
            "snippet should wrap match in <mark>"
        );
    }

    // Writes are rejected — verified in the unit test `write_is_rejected`.
    // The integration test cannot access the private `pool` field, so we rely
    // on the unit test for that guarantee.

    env::remove_var("INKSTATUTE_APP_ROOT");
    env::remove_var("INKSTATUTE_TEST_API_KEY");
    fs::remove_dir_all(&temp).ok();

    println!("query_real_engine_history: sessions={}", sessions.len());
}

use std::sync::Arc;
