use std::env;
use std::fs;
use std::path::PathBuf;

use inkstatute_desktop_lib::engine::lock::EngineLock;
use inkstatute_desktop_lib::engine::assemble::{assemble, AssembleOptions};

fn repo_root() -> PathBuf {
    let manifest = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let mut root = manifest.clone();
    // CARGO_MANIFEST_DIR is apps/desktop/src-tauri; go up three levels to repo root.
    root.pop();
    root.pop();
    root.pop();
    root
}

#[ignore = "requires network"]
#[tokio::test]
async fn assemble_real_engine_from_lock() {
    let lock_path = repo_root().join("engines/engine-lock.json");
    let cordis_path = repo_root().join("engines/acp.cordis.yml");

    let lock_text = fs::read_to_string(&lock_path).expect("read engine-lock.json");
    let lock = EngineLock::from_json(&lock_text).expect("parse engine-lock.json");
    let cordis_yml = fs::read_to_string(&cordis_path).expect("read acp.cordis.yml");

    let temp = env::temp_dir().join(format!(
        "inkstatute-assemble-test-{}",
        std::process::id()
    ));
    fs::remove_dir_all(&temp).ok();
    let dest = temp.join("engine");

    let opts = AssembleOptions {
        registry: "https://registry.npmmirror.com".to_string(),
        registry_fallback: "https://registry.npmjs.org".to_string(),
        concurrency: 8,
    };

    let progress = |p: inkstatute_desktop_lib::engine::assemble::AssembleProgress| {
        eprintln!("progress {}/{} {}", p.done, p.total, p.current);
    };

    assemble(&lock, &cordis_yml, &dest, &opts, progress)
        .await
        .expect("assemble engine");

    let entrypoint = dest.join("node_modules/@deepseek-ai/dsh-acp-demo/lib/bin.js");
    assert!(
        entrypoint.is_file(),
        "entrypoint missing: {}",
        entrypoint.display()
    );

    // node-pty prebuilds must include the target Windows platform and may also
    // keep the build-host prebuild so that local smoke tests can load it.
    let prebuilds = dest.join("node_modules/node-pty/prebuilds");
    if prebuilds.exists() {
        let platforms: Vec<String> = fs::read_dir(&prebuilds)
            .unwrap()
            .filter_map(|e| e.ok())
            .map(|e| e.file_name().to_string_lossy().to_string())
            .collect();
        assert!(
            platforms.iter().any(|p| p == "win32-x64"),
            "missing win32-x64 prebuild: {:?}",
            platforms
        );
    }

    let cordis = dest.join("acp.cordis.yml");
    assert!(cordis.is_file());
    let cordis_text = fs::read_to_string(&cordis).unwrap();
    assert!(cordis_text.contains("process.env.DSH_HOME"));

    fs::remove_dir_all(&temp).ok();
}
