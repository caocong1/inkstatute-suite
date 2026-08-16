//! Assembles the DSH engine from engine-lock.json into a target directory.
//!
//! Usage: `assemble-engine --out <dir> [--lock <engine-lock.json>] [--cordis <acp.cordis.yml>] [--smoke]`
//!
//! This is the dedicated binary the installer script and dev bring-up use
//! instead of driving the ignored integration test. `--smoke` boots the
//! assembled engine once (initialize → session/new) before reporting success.

use std::path::PathBuf;

use inkstatute_desktop_lib::engine::assemble::{assemble, AssembleOptions};
use inkstatute_desktop_lib::engine::lock::EngineLock;
use inkstatute_desktop_lib::engine::paths;
use inkstatute_desktop_lib::engine::smoke::smoke_test;

fn arg(args: &[String], name: &str) -> Option<String> {
    args.iter()
        .position(|a| a == name)
        .and_then(|i| args.get(i + 1))
        .cloned()
}

#[tokio::main]
async fn main() {
    let args: Vec<String> = std::env::args().collect();
    let out = match arg(&args, "--out") {
        Some(o) => PathBuf::from(o),
        None => {
            eprintln!("Usage: assemble-engine --out <dir> [--lock <path>] [--cordis <path>] [--smoke]");
            std::process::exit(1);
        }
    };

    // Default to the repo layout when run from anywhere inside the repo.
    let repo_root = std::env::var("INKSTATUTE_REPO_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            // src-tauri manifest dir → repo root is three levels up.
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("../../..")
                .canonicalize()
                .expect("repo root")
        });
    let lock_path = arg(&args, "--lock")
        .map(PathBuf::from)
        .unwrap_or_else(|| repo_root.join("engines/engine-lock.json"));
    let cordis_path = arg(&args, "--cordis")
        .map(PathBuf::from)
        .unwrap_or_else(|| repo_root.join("engines/acp.cordis.yml"));

    let lock_json = std::fs::read_to_string(&lock_path).unwrap_or_else(|e| {
        eprintln!("cannot read {}: {e}", lock_path.display());
        std::process::exit(1);
    });
    let lock = EngineLock::from_json(&lock_json).unwrap_or_else(|e| {
        eprintln!("bad lock: {e}");
        std::process::exit(1);
    });
    let cordis = std::fs::read_to_string(&cordis_path).unwrap_or_else(|e| {
        eprintln!("cannot read {}: {e}", cordis_path.display());
        std::process::exit(1);
    });

    eprintln!(
        "Assembling engine {} ({} packages) → {}",
        lock.engine_version,
        lock.packages.len(),
        out.display()
    );
    let opts = AssembleOptions::default();
    assemble(&lock, &cordis, &out, &opts, |p| {
        if p.done % 25 == 0 || p.done == p.total {
            eprintln!("  {}/{} {}", p.done, p.total, p.current);
        }
    })
    .await
    .unwrap_or_else(|e| {
        eprintln!("assembly failed: {e}");
        std::process::exit(1);
    });

    if args.iter().any(|a| a == "--smoke") {
        let node = paths::node_binary().or_else(|_| {
            // Dev fallback: PATH lookup is inside node_binary already; if that
            // failed too, there is nothing to boot with.
            Err(())
        });
        match node {
            Ok(node_bin) => {
                let r = smoke_test(&out, &node_bin, std::time::Duration::from_secs(60)).await;
                if !r.ok {
                    eprintln!("smoke failed: {}", r.failure.unwrap_or_default());
                    std::process::exit(1);
                }
                eprintln!(
                    "smoke ok: {} v{} in {} ms",
                    r.agent_name.unwrap_or_default(),
                    r.protocol_version.unwrap_or_default(),
                    r.elapsed_ms
                );
            }
            Err(_) => {
                eprintln!("smoke skipped: no node binary resolvable");
                std::process::exit(1);
            }
        }
    }
    println!("engine ready: {}", out.display());
}
