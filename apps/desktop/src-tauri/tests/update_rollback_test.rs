//! GATE-13: Bad-package rollback integration test.
//!
//! Verifies the core invariant: `engine/current` pointer is never moved
//! when a bad package is encountered. Two bad-package scenarios:
//!   A) Integrity failure (wrong sha512)
//!   B) Smoke failure (broken entrypoint)
//!
//! Also verifies the success path retains one previous version, and that
//! rollback works.
//!
//! These tests are `#[ignore]`d because they require network access to
//! download real npm packages. Run with:
//!   cargo test --test update_rollback_test -- --ignored --test-threads=1

use std::fs;
use std::path::{Path, PathBuf};
use std::time::Duration;

use inkstatute_desktop_lib::engine::assemble::{assemble, AssembleOptions, AssembleProgress};
use inkstatute_desktop_lib::engine::lock::EngineLock;
use inkstatute_desktop_lib::engine::paths;
use inkstatute_desktop_lib::engine::smoke::smoke_test;
use inkstatute_desktop_lib::engine::updater::EngineUpdater;

fn repo_root() -> PathBuf {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .to_path_buf()
}

fn read_lock() -> EngineLock {
    let lock_path = repo_root().join("engines/engine-lock.json");
    let text = fs::read_to_string(&lock_path).expect("read engine-lock.json");
    serde_json::from_str(&text).expect("parse engine-lock.json")
}

fn read_cordis() -> String {
    let cordis_path = repo_root().join("engines/acp.cordis.yml");
    fs::read_to_string(&cordis_path).expect("read acp.cordis.yml")
}

fn node_bin() -> PathBuf {
    paths::node_binary().expect("node binary must be available")
}

/// Set up an isolated app root for testing. Returns the temp dir path;
/// the caller is responsible for cleanup.
struct TestAppRoot {
    root: PathBuf,
}

impl TestAppRoot {
    fn new(test_name: &str) -> Self {
        let root = std::env::temp_dir().join(format!(
            "inkstatute-upd-{}-{}",
            test_name, std::process::id()
        ));
        fs::remove_dir_all(&root).ok();
        fs::create_dir_all(&root).expect("create temp app root");
        std::env::set_var("INKSTATUTE_APP_ROOT", &root);
        Self { root }
    }
}

impl Drop for TestAppRoot {
    fn drop(&mut self) {
        std::env::remove_var("INKSTATUTE_APP_ROOT");
        fs::remove_dir_all(&self.root).ok();
    }
}

/// Assemble a real engine into `engine/<version>/` and set current pointer.
async fn assemble_engine(version: &str) -> PathBuf {
    let dest = assemble_engine_only(version).await;
    paths::write_current(version).expect("write_current");
    dest
}

/// Assemble a real engine without touching the current pointer.
async fn assemble_engine_only(version: &str) -> PathBuf {
    let lock = read_lock();
    let cordis = read_cordis();
    let dest = paths::engine_dir(version).expect("engine_dir");
    if dest.exists() {
        fs::remove_dir_all(&dest).ok();
    }
    let opts = AssembleOptions::default();
    let progress = |_p: AssembleProgress| {};
    assemble(&lock, &cordis, &dest, &opts, progress)
        .await
        .expect("assemble engine");
    dest
}

/// Bad package A: tamper with a package's integrity hash in the lock.
fn make_bad_integrity_lock() -> EngineLock {
    let mut lock = read_lock();
    if let Some(pkg) = lock.packages.values_mut().next() {
        pkg.integrity = "sha512-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==".to_string();
    }
    lock
}

/// Bad package B: assemble normally, then break the entrypoint.
fn break_entrypoint(engine_dir: &Path) {
    let bin = engine_dir.join("node_modules/@deepseek-ai/dsh-acp-demo/lib/bin.js");
    if bin.exists() {
        fs::remove_file(&bin).expect("remove bin.js");
    }
}

#[tokio::test]
#[ignore = "requires network access to npm registry"]
async fn bad_integrity_does_not_move_current() {
    let _app_root = TestAppRoot::new("bad-integrity");

    let v1 = "0.1.0-rc.6";
    assemble_engine(v1).await;
    let current_before = paths::read_current().unwrap();
    assert_eq!(current_before.as_deref(), Some(v1));

    let bad_lock = make_bad_integrity_lock();
    let cordis = read_cordis();
    let v2_bad = "0.1.0-rc.7-bad-integrity";
    let dest = paths::engine_dir(v2_bad).unwrap();
    let opts = AssembleOptions::default();
    let progress = |_p: AssembleProgress| {};
    let result = assemble(&bad_lock, &cordis, &dest, &opts, progress).await;

    assert!(result.is_err(), "assemble with bad integrity should fail");

    let current_after = paths::read_current().unwrap();
    assert_eq!(current_after, current_before, "current must not move on failure");

    if dest.exists() {
        let bin = dest.join("node_modules/@deepseek-ai/dsh-acp-demo/lib/bin.js");
        assert!(!bin.exists(), "bad engine should not have a valid entrypoint");
    }
}

#[tokio::test]
#[ignore = "requires network access to npm registry"]
async fn bad_smoke_does_not_move_current() {
    let _app_root = TestAppRoot::new("bad-smoke");

    let v1 = "0.1.0-rc.6";
    let v1_dir = assemble_engine(v1).await;
    let current_before = paths::read_current().unwrap();
    assert_eq!(current_before.as_deref(), Some(v1));

    let v2_bad = "0.1.0-rc.7-bad-smoke";
    let v2_dir = assemble_engine_only(v2_bad).await;
    break_entrypoint(&v2_dir);

    let node = node_bin();
    let smoke = smoke_test(&v2_dir, &node, Duration::from_secs(60)).await;
    assert!(!smoke.ok, "smoke test should fail on broken entrypoint");

    let current_after = paths::read_current().unwrap();
    assert_eq!(current_after, current_before, "current must not move on smoke failure");

    let v1_smoke = smoke_test(&v1_dir, &node, Duration::from_secs(60)).await;
    assert!(v1_smoke.ok, "v1 engine should still be intact");
}

#[tokio::test]
#[ignore = "requires network access to npm registry"]
async fn success_path_retains_one_previous() {
    let _app_root = TestAppRoot::new("success");

    let v1 = "0.1.0-rc.6";
    assemble_engine(v1).await;

    let v2 = "0.1.0-rc.7";
    let v2_dir = assemble_engine(v2).await;

    let node = node_bin();
    let smoke = smoke_test(&v2_dir, &node, Duration::from_secs(60)).await;
    assert!(smoke.ok, "v2 smoke should pass");

    assert_eq!(paths::read_current().unwrap().as_deref(), Some(v2));

    let v1_dir = paths::engine_dir(v1).unwrap();
    assert!(v1_dir.exists(), "previous version should be retained");
}

#[tokio::test]
#[ignore = "requires network access to npm registry"]
async fn rollback_switches_to_previous() {
    let _app_root = TestAppRoot::new("rollback");

    let v1 = "0.1.0-rc.6";
    let v2 = "0.1.0-rc.7";
    assemble_engine(v1).await;
    assemble_engine(v2).await;

    assert_eq!(paths::read_current().unwrap().as_deref(), Some(v2));

    let updater = EngineUpdater::new(
        "http://localhost".to_string(),
        read_cordis(),
        AssembleOptions::default(),
    );
    let result = updater.rollback().await;
    assert!(result.is_ok(), "rollback should succeed: {:?}", result.err());

    assert_eq!(paths::read_current().unwrap().as_deref(), Some(v1));
}
