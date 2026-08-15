use std::env;
use std::fs;
use std::path::PathBuf;
use std::time::Duration;

use inkstatute_desktop_lib::engine::assemble::{assemble, AssembleOptions};
use inkstatute_desktop_lib::engine::lock::EngineLock;
use inkstatute_desktop_lib::engine::paths;
use inkstatute_desktop_lib::engine::smoke::smoke_test;

fn repo_root() -> PathBuf {
    let manifest = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let mut root = manifest.clone();
    root.pop();
    root.pop();
    root.pop();
    root
}

#[ignore = "requires network and node"]
#[tokio::test]
async fn smoke_real_assembled_engine() {
    let lock_path = repo_root().join("engines/engine-lock.json");
    let cordis_path = repo_root().join("engines/acp.cordis.yml");

    let lock_text = fs::read_to_string(&lock_path).expect("read engine-lock.json");
    let lock = EngineLock::from_json(&lock_text).expect("parse engine-lock.json");
    let cordis_yml = fs::read_to_string(&cordis_path).expect("read acp.cordis.yml");

    let temp = env::temp_dir().join(format!(
        "inkstatute-smoke-test-{}",
        std::process::id()
    ));
    fs::remove_dir_all(&temp).ok();
    let dest = temp.join("engine");

    let opts = AssembleOptions {
        registry: "https://registry.npmmirror.com".to_string(),
        registry_fallback: "https://registry.npmjs.org".to_string(),
        concurrency: 8,
    };

    assemble(&lock, &cordis_yml, &dest, &opts, |_p| {}).await.expect("assemble engine");

    let node_bin = paths::node_binary_for_test().expect("find node binary");
    let result = smoke_test(&dest, &node_bin, Duration::from_secs(30)).await;

    assert!(result.ok, "smoke failed: {:?}", result);
    assert_eq!(result.protocol_version, Some(1));
    assert_eq!(result.agent_name.as_deref(), Some("deepseek-harness-acp"));
    assert!(result.session_id.is_some());
    assert!(result.elapsed_ms < 30_000);

    fs::remove_dir_all(&temp).ok();
}
