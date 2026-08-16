//! Phase 128 / Plan 128-02: review/adversarial-challenge integration tests.
//!
//! Offline: constructs final-draft texts (disagreements, fatal-challenge
//! items, human-review escalations) and runs them through `scan_review` /
//! `ensure_escalated`, asserting parsed counts and the fallback-invariant
//! behavior end to end through the public API.
//!
//! `#[ignore]` `cross_review_end_to_end`: assembles + spawns the real engine,
//! sends a prompt guaranteed to trip `[GUARDRAIL:CROSS_REVIEW]` (a >100万
//! equity-transfer valuation-adjustment ["对赌"] clause — both a contract-
//! validity determination and an amount over the 100万 threshold), and
//! asserts the session log shows `subagent/start`/`subagent/end`, the final
//! text carries `[分歧]` entries (or an explicit no-disagreement statement),
//! and adversarial-challenge rounds stayed within the early-stop cap.
//! Requires a DeepSeek key (drafting model) plus OpenAI + Anthropic keys
//! (reviewer-a/challenger and reviewer-b — `engines/acp.cordis.yml`) — skips
//! via `eprintln!` rather than failing when they are not configured.

use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

use inkstatute_desktop_lib::engine::acp::{PermissionDecision, SessionUpdate};
use inkstatute_desktop_lib::engine::assemble::{assemble, AssembleOptions};
use inkstatute_desktop_lib::engine::credentials::{self, Provider};
use inkstatute_desktop_lib::engine::events::{self, ParsedLine, SessionEventKind};
use inkstatute_desktop_lib::engine::lock::EngineLock;
use inkstatute_desktop_lib::engine::paths;
use inkstatute_desktop_lib::engine::review::{ensure_escalated, scan_review};
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

// ── Offline ──────────────────────────────────────────────────────────────

#[test]
fn scan_review_counts_disagreements_and_fatal_challenges_from_constructed_final_draft() {
    let text = "\
根据本案事实与现行有效法律，初步意见如下：本次股权转让协议中的对赌条款效力认定，
已与两位独立复核律师核对如下分歧：

[分歧] 对赌条款是否因排除股东法定权利而无效｜本意见：有效，系目标公司与投资人之间的对赌，不违反公司法强制性规定｜复核意见：应审查是否存在变相抽逃出资情形｜已消解，现行司法解释已明确该情形下的效力认定标准

[分歧] 违约金调整请求权的行使期间｜本意见：应参照诉讼时效三年计算｜复核意见：违约金调整属抗辩权，不受诉讼时效限制｜已消解，双方最终援引同一现行司法解释条文达成一致

[分歧] 案涉条款是否构成有效对赌的定性认定｜本意见：符合估值调整机制的典型特征，应认定为有效对赌条款｜复核意见：条款文义存在歧义，不能排除是变相借贷的可能｜未消解，双方依据均为现行有效法律，无法互相反驳

对抗质询意见：

【致命问题】
- 若认定为变相借贷，则本合同项下的股权转让条款可能因通谋虚伪表示而整体无效
- 原告未能举证证明目标公司在对赌期间的实际经营数据来源具有可核实性

【可被攻击】
- 违约金比例约定偏高，存在被法院酌情调低的空间

综上，本次结论存在未消解分歧，涉及金额超过100万元。
[HUMAN_REVIEW: 模型间存在未消解分歧 —— 案涉条款是否构成有效对赌的定性认定]
";

    let scan = scan_review(text);

    assert_eq!(scan.disagreements.len(), 3, "expected 3 disagreement lines");
    assert_eq!(scan.unresolved_count, 1, "expected exactly 1 unresolved disagreement");
    assert_eq!(scan.fatal_challenges.len(), 2, "expected 2 fatal-challenge items");
    assert!(
        !scan.fatal_challenges.iter().any(|i| i.contains("违约金比例")),
        "must not cross into the 【可被攻击】 section"
    );

    // The model DID emit a matching [HUMAN_REVIEW: …分歧…] mark, so the
    // fallback invariant must not fire.
    assert_eq!(scan.escalations.len(), 1);
    assert!(
        ensure_escalated(&scan, text).is_none(),
        "already escalated by the model — no fallback needed"
    );
}

#[test]
fn scan_review_ensure_escalated_fallback_fires_when_model_forgets_to_mark() {
    // Same shape as above, but the trailing [HUMAN_REVIEW:] mark is omitted —
    // simulates the model failing to follow [GUARDRAIL:SYNTHESIS].
    let text = "\
[分歧] 争点甲｜本意见：立场A，依据现行有效司法解释｜复核意见：立场B，依据同一司法解释的但书条款｜已消解，本意见援引条文更贴合案情
[分歧] 争点乙｜本意见：立场C｜复核意见：立场D｜未消解，双方依据均为现行有效法律
";

    let scan = scan_review(text);
    assert_eq!(scan.unresolved_count, 1);
    assert!(scan.escalations.is_empty(), "model forgot to emit the escalation mark");

    let fallback = ensure_escalated(&scan, text);
    assert!(
        fallback.is_some(),
        "unresolved disagreement with no [HUMAN_REVIEW:] mark must trigger the fallback"
    );
    let fallback_text = fallback.unwrap();
    assert!(fallback_text.starts_with("[HUMAN_REVIEW:"));
    assert!(fallback_text.contains("分歧"));
}

/// Recursively search `sessions_root` for a `session.jsonl` file whose
/// content carries the given session id. Directory naming under
/// `sessions_root` is a lossy normalization of the session cwd (see
/// `tailer.rs`), so matching by id rather than by predicted path is the only
/// reliable way to locate the file.
fn find_session_log(sessions_root: &Path, sid: &str) -> Option<PathBuf> {
    fn walk(dir: &Path, sid: &str) -> Option<PathBuf> {
        let entries = fs::read_dir(dir).ok()?;
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                if let Some(found) = walk(&path, sid) {
                    return Some(found);
                }
            } else if path.file_name().map(|n| n == "session.jsonl").unwrap_or(false) {
                if let Ok(content) = fs::read_to_string(&path) {
                    if content.contains(sid) {
                        return Some(path);
                    }
                }
            }
        }
        None
    }
    walk(sessions_root, sid)
}

// ── #[ignore] real engine end-to-end ────────────────────────────────────

#[ignore = "requires network, node, and DeepSeek + OpenAI + Anthropic API keys configured"]
#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn cross_review_end_to_end() {
    // Gate: need real keys (not the blanket INKSTATUTE_TEST_API_KEY override,
    // which answers has_key() for every provider with the same fake value)
    // for the drafting model plus both review vendors — reviewer-a/challenger
    // use OpenAI, reviewer-b uses Anthropic (engines/acp.cordis.yml).
    let have_deepseek = credentials::has_key(Provider::DeepSeek);
    let have_openai = credentials::has_key(Provider::OpenAI);
    let have_anthropic = credentials::has_key(Provider::Anthropic);
    if !(have_deepseek && have_openai && have_anthropic) {
        eprintln!(
            "SKIP cross_review_end_to_end: requires DeepSeek + OpenAI + Anthropic keys \
             (deepseek={have_deepseek} openai={have_openai} anthropic={have_anthropic}). \
             Configure real per-provider keys (store-key binary or $INKSTATUTE_DEV_CREDENTIALS), \
             then rerun with `cargo test -- --ignored cross_review_end_to_end`."
        );
        return;
    }

    let temp = env::temp_dir().join(format!("inkstatute-cross-review-real-{}", std::process::id()));
    fs::remove_dir_all(&temp).ok();
    env::set_var("INKSTATUTE_APP_ROOT", &temp);

    // Assemble the real engine (network required — npm registry).
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

    let ws = temp.join("workspaces/cross-review");
    fs::create_dir_all(&ws).unwrap();
    let sid = client.new_session(&ws).await.expect("new session");

    // Guaranteed to trip [GUARDRAIL:CROSS_REVIEW]: contract-validity
    // determination (对赌条款效力) on an amount > 100万.
    let prompt_text = "这份500万的股权转让协议的对赌条款有效吗";

    let mut updates_rx = client.subscribe_updates();
    let mut permission_rx = client.subscribe_permissions();
    let c = Arc::clone(&client);
    let s = sid.clone();
    let p = prompt_text.to_string();
    let mut task = tokio::spawn(async move { c.prompt(&s, &p).await });

    // Multi-model review (2 reviewers + up to 2 adversarial rounds +
    // synthesis) is several real model round-trips — allow a generous window.
    let deadline = tokio::time::Instant::now() + Duration::from_secs(600);
    let mut final_text = String::new();
    loop {
        if tokio::time::Instant::now() >= deadline {
            panic!("cross_review_end_to_end timed out waiting for the prompt to finish");
        }
        tokio::select! {
            update = updates_rx.recv() => {
                if let Ok(SessionUpdate::AgentMessageChunk { session_id, text }) = update {
                    if session_id == sid {
                        final_text.push_str(&text);
                    }
                }
            }
            Ok(req) = permission_rx.recv() => {
                // Never blanket-allow: only the review tools and the
                // subagents' own read-only allowlist may proceed; anything
                // else (bash, write, …) is rejected so a misconfigured
                // allowlist fails loudly instead of silently granting
                // unexpected access.
                let decision = if matches!(
                    req.tool_name.as_deref(),
                    Some("legal_review_a") | Some("legal_review_b") | Some("adversarial_challenge")
                        | Some("read") | Some("grep") | Some("glob") | Some("skill")
                ) {
                    PermissionDecision::AllowOnce
                } else {
                    PermissionDecision::RejectOnce
                };
                let _ = client.respond_permission(req.request_id, decision).await;
            }
            res = &mut task => {
                let result = res.expect("prompt task join").expect("prompt turn");
                println!("cross_review_end_to_end: stop_reason={}", result.stop_reason);
                break;
            }
        }
    }

    // Locate the session log and scan for subagent lifecycle events, and
    // count adversarial-challenge rounds specifically.
    let log_path = find_session_log(&sessions_root, &sid).expect("session log for the review session");
    let log_content = fs::read_to_string(&log_path).expect("read session log");

    let mut subagent_start = 0usize;
    let mut subagent_end = 0usize;
    let mut challenge_rounds = 0usize;
    for line in log_content.lines() {
        if let Ok(ParsedLine::Event(ev)) = events::parse_line(line) {
            if let SessionEventKind::Other(t) = &ev.kind {
                if t == "subagent/start" {
                    subagent_start += 1;
                    if ev.raw.to_string().contains("adversarial_challenge") {
                        challenge_rounds += 1;
                    }
                } else if t == "subagent/end" {
                    subagent_end += 1;
                }
            }
        }
    }

    assert!(subagent_start > 0, "expected ≥1 subagent/start event in the session log");
    assert!(subagent_end > 0, "expected ≥1 subagent/end event in the session log");
    assert!(
        challenge_rounds <= 2,
        "adversarial-challenge rounds should be ≤ 2 (early-stop / round cap), got {challenge_rounds}"
    );

    let scan = scan_review(&final_text);
    let has_disagreement_marker = !scan.disagreements.is_empty();
    let explicit_no_disagreement =
        final_text.contains("无分歧") || final_text.contains("没有分歧") || final_text.contains("不存在分歧");
    assert!(
        has_disagreement_marker || explicit_no_disagreement,
        "final text must either carry [分歧] entries or explicitly state there is no disagreement; got:\n{final_text}"
    );

    let _ = supervisor.shutdown().await;
    let _ = supervisor.assert_no_orphans().await;

    env::remove_var("INKSTATUTE_APP_ROOT");
    fs::remove_dir_all(&temp).ok();
}
