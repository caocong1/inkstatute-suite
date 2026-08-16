//! GATE (Phase 128 / MMR-01..02): static fresh-context + config-shape gate
//! for the cross-review / adversarial-challenge subagents.
//!
//! v3.1 equivalent: `packages/arena-engine/tests/test_fresh_context.py`, an
//! AST gate that forbade `resume` / `session/resume` anywhere in arena
//! source ("every arena run must use a fresh context"). v5 has no arena
//! source to AST-scan — multi-model review is pure Cordis config, not
//! orchestration code — so this is the config-shape equivalent: static
//! assertions against `engines/acp.cordis.yml` and `engines/engine-lock.json`
//! that a later config drift (someone re-adds fork transport, opens up
//! bash/write for a reviewer, or collapses all reviewers onto one vendor)
//! gets caught by `cargo test`, before it ships.

use std::collections::HashSet;
use std::fs;
use std::path::PathBuf;

use serde::Deserialize;
use serde_yaml::Value;

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

fn read_cordis() -> String {
    fs::read_to_string(repo_root().join("engines/acp.cordis.yml")).expect("read acp.cordis.yml")
}

fn read_lock() -> String {
    fs::read_to_string(repo_root().join("engines/engine-lock.json")).expect("read engine-lock.json")
}

#[derive(Debug, Deserialize)]
struct CordisItem {
    id: String,
    #[serde(default)]
    name: String,
    #[serde(default)]
    config: Option<Value>,
}

fn parse_cordis() -> Vec<CordisItem> {
    serde_yaml::from_str(&read_cordis()).expect("acp.cordis.yml must parse as a Cordis item list")
}

/// The three review/challenge subagent instances registered as
/// `@deepseek-ai/dsh-tool-subagent` (reviewer-a, reviewer-b, challenger).
fn tool_subagents(items: &[CordisItem]) -> Vec<&CordisItem> {
    items
        .iter()
        .filter(|i| i.name == "@deepseek-ai/dsh-tool-subagent")
        .collect()
}

#[test]
fn subagent_config_no_fork_transport_in_config_or_lock() {
    // MMR-02 fresh-context invariant: a reviewer must never inherit the
    // drafter's session history. fork-in-process is the only transport that
    // does that; it must never appear, wired or merely present in the
    // dependency tree, in either file.
    let cordis = read_cordis();
    let lock = read_lock();
    assert!(
        !cordis.contains("fork-in-process"),
        "acp.cordis.yml must not reference the fork-in-process subagent transport"
    );
    assert!(
        !lock.contains("fork-in-process"),
        "engine-lock.json must not contain the fork-in-process subagent transport"
    );
}

#[test]
fn subagent_config_exactly_three_review_tool_subagents_with_unique_tool_names() {
    let items = parse_cordis();
    let subs = tool_subagents(&items);
    assert_eq!(
        subs.len(),
        3,
        "expected exactly 3 @deepseek-ai/dsh-tool-subagent instances, found {}",
        subs.len()
    );

    let tool_names: HashSet<&str> = subs
        .iter()
        .map(|i| {
            i.config
                .as_ref()
                .and_then(|c| c.get("toolName"))
                .and_then(|v| v.as_str())
                .unwrap_or_else(|| panic!("subagent {:?} config must declare toolName", i.id))
        })
        .collect();
    assert_eq!(
        tool_names.len(),
        3,
        "toolName values must be unique across the 3 subagents, found: {:?}",
        tool_names
    );
}

#[test]
fn subagent_config_every_review_tool_subagent_has_max_depth_one() {
    let items = parse_cordis();
    for sub in tool_subagents(&items) {
        let max_depth = sub
            .config
            .as_ref()
            .and_then(|c| c.get("maxDepth"))
            .and_then(|v| v.as_i64());
        assert_eq!(
            max_depth,
            Some(1),
            "subagent {:?} must have maxDepth: 1 — reviewers must not spawn reviewers",
            sub.id
        );
    }
}

#[test]
fn subagent_config_every_review_tool_subagent_has_nonempty_read_only_tool_allowlist() {
    let items = parse_cordis();
    for sub in tool_subagents(&items) {
        let allow = sub
            .config
            .as_ref()
            .and_then(|c| c.get("toolFilter"))
            .and_then(|tf| tf.get("allow"))
            .and_then(|v| v.as_sequence())
            .unwrap_or_else(|| panic!("subagent {:?} must declare config.toolFilter.allow", sub.id));

        assert!(
            !allow.is_empty(),
            "subagent {:?} toolFilter.allow must be non-empty",
            sub.id
        );

        let forbidden = ["bash", "write", "edit"];
        for v in allow {
            let tool = v.as_str().unwrap_or_default();
            assert!(
                !forbidden.contains(&tool),
                "subagent {:?} toolFilter.allow must not include {:?} — reviewers are read-only",
                sub.id,
                tool
            );
        }
    }
}

#[test]
fn subagent_config_every_subagent_provider_is_declared_in_llm_providers_and_spans_two_vendors() {
    let items = parse_cordis();
    let llm = items
        .iter()
        .find(|i| i.id == "llm")
        .expect("acp.cordis.yml must have an llm entry");
    let llm_providers: HashSet<String> = llm
        .config
        .as_ref()
        .and_then(|c| c.get("providers"))
        .and_then(|p| p.as_mapping())
        .expect("llm entry must declare config.providers")
        .keys()
        .filter_map(|k| k.as_str().map(str::to_string))
        .collect();

    let subs = tool_subagents(&items);
    let mut vendors: HashSet<String> = HashSet::new();
    for sub in &subs {
        let provider = sub
            .config
            .as_ref()
            .and_then(|c| c.get("agentOptions"))
            .and_then(|a| a.get("provider"))
            .and_then(|v| v.as_str())
            .unwrap_or_else(|| panic!("subagent {:?} must declare config.agentOptions.provider", sub.id));

        assert!(
            llm_providers.contains(provider),
            "subagent {:?} agentOptions.provider {:?} is not declared under llm.config.providers ({:?})",
            sub.id,
            provider,
            llm_providers
        );
        vendors.insert(provider.to_string());
    }

    assert!(
        vendors.len() >= 2,
        "the 3 review subagents must span at least 2 distinct vendors to avoid same-vendor blind \
         spots (MMR-01), found only: {:?}",
        vendors
    );
}
