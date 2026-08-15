use std::env;
use std::fs;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};

use inkstatute_desktop_lib::engine::acp::{AcpClient, PermissionDecision, SessionUpdate};
use inkstatute_desktop_lib::engine::assemble::{assemble, AssembleOptions};
use inkstatute_desktop_lib::engine::credentials::{load_key, Provider};
use inkstatute_desktop_lib::engine::lock::EngineLock;
use inkstatute_desktop_lib::engine::paths;
use inkstatute_desktop_lib::engine::replay::{build_seed_prefix, compose_seeded_prompt, ReplayConfig, ReplayRole, ReplayTurn};
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

fn ask_answer_pair(i: usize) -> (String, String) {
    let user = format!(
        "审查买卖合同违约案件 #{i}：卖方未按期交货，买方主张违约金。请总结关键证据。"
    );
    let answer = format!(
        "案件 #{i} 的关键证据是2024年3月1日卖方法务负责人发给买方的电子邮件， \
         其中承认生产线故障导致延期两周，并承诺尽快补货。"
    );
    (user, answer)
}

fn build_history(turns: usize) -> Vec<ReplayTurn> {
    let mut history = Vec::new();
    for i in 0..turns {
        let (u, a) = ask_answer_pair(i + 1);
        history.push(ReplayTurn { role: ReplayRole::User, text: u });
        history.push(ReplayTurn { role: ReplayRole::Assistant, text: a });
    }
    history
}

fn context_question() -> &'static str {
    "在我们刚才讨论的系列违约案件中，第一个案件的关键证据是什么？"
}

fn unrelated_question() -> &'static str {
    "法国的首都是什么？"
}

fn baseline_question() -> &'static str {
    "简要解释合同违约金条款的法律效力。"
}

#[derive(Debug)]
struct PromptMetrics {
    pub first_token_ms: u64,
    pub total_ms: u64,
    pub prompt_tokens: Option<u64>,
    pub answer: String,
}

/// Prompt-token counts are NOT reachable from this test.
///
/// They live in the `usage` chunk of `assistant/chunk`, which the DSH ACP bridge
/// deliberately keeps off the wire — ACP emits only `agent_message_chunk`. The
/// `request/header` event this function used to inspect carries only
/// `config` / `adapterDefaults` / `system` / `tools`, never a token count.
///
/// The only source is the session JSONL log, i.e. the observation plane built in
/// Phase 124. The 20%-of-context-window budget criterion therefore moves to
/// Phase 124 (GATE-12); see `.planning/phases/124-observation-history-planes/`.
///
/// Kept returning `None` on purpose so the caller records "unmeasured" rather
/// than silently comparing `unwrap_or(0)` against the budget and always passing.
fn extract_prompt_tokens(_header: &serde_json::Value) -> Option<u64> {
    None
}

async fn run_prompt(client: Arc<AcpClient>, session_id: &str, text: &str) -> PromptMetrics {
    let mut updates = client.subscribe_updates();
    let start = Instant::now();
    let mut first_token_ms: Option<u64> = None;
    let mut prompt_tokens: Option<u64> = None;
    let mut answer = String::new();

    let client_clone = Arc::clone(&client);
    let sid = session_id.to_string();
    let text = text.to_string();
    let mut prompt_task = tokio::spawn(async move {
        client_clone.prompt(&sid, &text).await
    });

    let mut permission_rx = client.subscribe_permissions();

    let result = loop {
        tokio::select! {
            Ok(update) = updates.recv() => {
                match update {
                    SessionUpdate::AgentMessageChunk { text: chunk, .. } => {
                        if first_token_ms.is_none() {
                            first_token_ms = Some(start.elapsed().as_millis() as u64);
                        }
                        answer.push_str(&chunk);
                    }
                    SessionUpdate::RequestHeader { header, .. } => {
                        if prompt_tokens.is_none() {
                            prompt_tokens = extract_prompt_tokens(&header);
                        }
                    }
                    _ => {}
                }
            }
            Ok(req) = permission_rx.recv() => {
                // Auto-reject any permission request to keep the test focused on replay.
                client.respond_permission(req.request_id, PermissionDecision::RejectOnce)
                    .await
                    .expect("respond permission");
            }
            res = &mut prompt_task => break res.expect("prompt task"),
        }
    };

    let _ = result.expect("prompt should complete");

    PromptMetrics {
        first_token_ms: first_token_ms.unwrap_or(u64::MAX),
        total_ms: start.elapsed().as_millis() as u64,
        prompt_tokens,
        answer,
    }
}

async fn setup_app_and_engine() -> (PathBuf, PathBuf) {
    let temp = env::temp_dir().join(format!("inkstatute-replay-test-{}", std::process::id()));
    fs::remove_dir_all(&temp).ok();

    // Override app root for this test run.
    env::set_var("INKSTATUTE_APP_ROOT", &temp);

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
    assemble(&lock, &cordis_yml, &engine_dest, &opts, |_p| {}).await.expect("assemble engine");

    (temp, engine_dest)
}

fn load_or_prompt_key() -> String {
    if let Ok(key) = env::var("INKSTATUTE_TEST_API_KEY") {
        return key;
    }
    match load_key(Provider::DeepSeek).expect("load key from keyring") {
        Some(k) => k,
        None => panic!(
            "No DeepSeek API key found. Store one with:
  cargo run --bin store-key deepseek
or set INKSTATUTE_TEST_API_KEY for a manual test run."
        ),
    }
}

#[ignore = "requires real DeepSeek API key"]
#[tokio::test]
async fn real_replay_gate() {
    let key = load_or_prompt_key();
    if key.trim().is_empty() {
        panic!("DeepSeek API key is empty");
    }

    // Store in keyring so build_engine_env picks it up.
    inkstatute_desktop_lib::engine::credentials::store_key(Provider::DeepSeek, &key)
        .expect("store key");

    let (temp, engine_dir) = setup_app_and_engine().await;

    let dsh_home = paths::dsh_home().expect("dsh_home");
    fs::create_dir_all(&dsh_home).unwrap();

    let supervisor = EngineSupervisor::spawn(SpawnConfig {
        engine_dir,
        node_bin: node_bin(),
        dsh_home,
        provider: Provider::DeepSeek,
    })
    .await
    .expect("spawn engine");

    let _health = supervisor.health_probe(Duration::from_secs(30)).await.expect("health probe");
    let client = supervisor.acp_client();

    let workspace = temp.join("workspaces/replay-gate");
    fs::create_dir_all(&workspace).unwrap();
    let session_id = client.new_session(&workspace).await.expect("new session");

    // Group 1: baseline single-turn legal question.
    let baseline = run_prompt(Arc::clone(&client), &session_id, baseline_question()).await;

    // Group 2: 5-turn replay + context question.
    let history_5 = build_history(5);
    let seed_5 = build_seed_prefix(&history_5, &ReplayConfig::default()).unwrap();
    let text_5 = compose_seeded_prompt(Some(&seed_5), context_question());
    let replay_5 = run_prompt(Arc::clone(&client), &session_id, &text_5).await;

    // Group 3: 20-turn replay + context question.
    let history_20 = build_history(20);
    let seed_20 = build_seed_prefix(&history_20, &ReplayConfig::default()).unwrap();
    let text_20 = compose_seeded_prompt(Some(&seed_20), context_question());
    let replay_20 = run_prompt(Arc::clone(&client), &session_id, &text_20).await;

    // Group 4: 20-turn replay + unrelated question.
    let text_unrelated = compose_seeded_prompt(Some(&seed_20), unrelated_question());
    let unrelated = run_prompt(Arc::clone(&client), &session_id, &text_unrelated).await;

    // Evaluate criteria.
    let threshold_ratio = 3u64;
    let mut failures = Vec::new();

    if replay_5.first_token_ms > baseline.first_token_ms * threshold_ratio {
        failures.push(format!(
            "5-turn replay first-token latency {} ms > {}x baseline {} ms",
            replay_5.first_token_ms, threshold_ratio, baseline.first_token_ms
        ));
    }
    if replay_20.first_token_ms > baseline.first_token_ms * threshold_ratio {
        failures.push(format!(
            "20-turn replay first-token latency {} ms > {}x baseline {} ms",
            replay_20.first_token_ms, threshold_ratio, baseline.first_token_ms
        ));
    }

    let context_keywords = ["3月1日", "邮件", "电子邮件"];
    if !context_keywords.iter().any(|kw| replay_5.answer.contains(kw)) {
        failures.push("5-turn replay did not reference the historical evidence".to_string());
    }
    if !context_keywords.iter().any(|kw| replay_20.answer.contains(kw)) {
        failures.push("20-turn replay did not reference the historical evidence".to_string());
    }

    let unrelated_keywords = ["巴黎", "Paris"];
    if !unrelated_keywords.iter().any(|kw| unrelated.answer.contains(kw)) {
        failures.push(format!("Unrelated question was confused: answer was '{}'", unrelated.answer));
    }

    const CONTEXT_WINDOW: u64 = 1_000_000;
    const BUDGET: u64 = CONTEXT_WINDOW * 20 / 100;
    if replay_20.prompt_tokens.unwrap_or(0) >= BUDGET {
        failures.push(format!(
            "20-turn prompt tokens {} >= {} ({}% of context window)",
            replay_20.prompt_tokens.unwrap_or(0),
            BUDGET,
            20
        ));
    }

    let report = format!(
        "Phase 123 Real-API Replay Gate\n\n\
        Baseline\n  first-token: {} ms\n  total: {} ms\n  prompt_tokens: {:?}\n  answer: {}\n\n\
        Replay 5 turns\n  first-token: {} ms\n  total: {} ms\n  prompt_tokens: {:?}\n  answer: {}\n\n\
        Replay 20 turns\n  first-token: {} ms\n  total: {} ms\n  prompt_tokens: {:?}\n  answer: {}\n\n\
        Unrelated after 20 turns\n  first-token: {} ms\n  total: {} ms\n  prompt_tokens: {:?}\n  answer: {}\n\n",
        baseline.first_token_ms, baseline.total_ms, baseline.prompt_tokens, baseline.answer.trim(),
        replay_5.first_token_ms, replay_5.total_ms, replay_5.prompt_tokens, replay_5.answer.trim(),
        replay_20.first_token_ms, replay_20.total_ms, replay_20.prompt_tokens, replay_20.answer.trim(),
        unrelated.first_token_ms, unrelated.total_ms, unrelated.prompt_tokens, unrelated.answer.trim(),
    );

    let verdict = if failures.is_empty() {
        "回灌方案验证通过".to_string()
    } else {
        format!("触发架构回退评审\n\nFailures:\n{}", failures.join("\n"))
    };

    let decision_path = repo_root()
        .join(".planning/phases/123-engine-supervisor-real-path/123-DECISION.md");
    fs::create_dir_all(decision_path.parent().unwrap()).unwrap();
    let content = format!("{}\n\nVerdict: {}\n", report, verdict);
    fs::write(&decision_path, content).expect("write decision");

    // Clean up the app root override before assertions.
    env::remove_var("INKSTATUTE_APP_ROOT");
    fs::remove_dir_all(&temp).ok();

    if !failures.is_empty() {
        panic!("Replay gate failed. See {}\n\n{}", decision_path.display(), verdict);
    }

    println!("Real-API replay gate passed. Decision written to {}", decision_path.display());
}
