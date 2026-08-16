---
phase: 128-multi-model-review
plan: 128-02
subsystem: engine
tags: [guardrails, persona, multi-model-review, disagreement-parsing, early-stop, human-review, cordis-config]

requires:
  - phase: 128-multi-model-review
    plan: 128-01
    provides: "Three dsh-tool-subagent instances (legal_review_a/legal_review_b/adversarial_challenge) wired into engines/acp.cordis.yml, with spawn-only transport and read-only tool allowlists"
  - phase: 126-guardrails-capability-layer
    provides: "guardrails.rs::scan pure-parser pattern (Citation/Clarification/HumanReview text conventions) that review.rs is isomorphic to; the preset.yml + agent.cordis.yml dual-copy pattern for guardrail text"
provides:
  - "presets/legal-core: 7th and 8th persona guardrail segments — [GUARDRAIL:CROSS_REVIEW] (when to call legal_review_a/legal_review_b/adversarial_challenge) and [GUARDRAIL:SYNTHESIS] (disagreement rendering format, resolution standard, human-review escalation, adversarial early-stop rule, no citation-review relaxation)"
  - "review.rs: scan_review() — parses [分歧] disagreement lines, 【致命问题】 fatal-challenge items, and disagreement-related [HUMAN_REVIEW:] escalations from committed final text"
  - "review.rs: ensure_escalated() — fallback invariant that returns a human-review mark to append whenever unresolved disagreements exist but the model failed to mark them; never clears an existing mark"
  - "review.rs: RoundTracker — early-stops adversarial-challenge rounds at (fatal=0, attackable=0) or the round cap (default 2)"
affects: [128-03]

actuals:
  tokens: 10180
  tasks: 4
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Text-convention scanner isomorphic to guardrails.rs::scan — the model commits to a text format via the persona, Rust purely parses it (no I/O), conservative-by-default on ambiguity (missing/unclear segments => treated as the higher-caution state)"
    - "Fallback-invariant function re-derives its own check from raw input rather than trusting a caller-supplied pre-computed result, so a stale/mismatched argument cannot produce a wrong answer"

key-files:
  created:
    - apps/desktop/src-tauri/src/engine/review.rs
    - apps/desktop/src-tauri/tests/review_test.rs
  modified:
    - apps/desktop/src-tauri/src/engine/mod.rs
    - presets/legal-core/preset.yml
    - presets/legal-core/agent.cordis.yml

key-decisions:
  - "review.rs written without the regex crate (already a project dependency, used elsewhere) to stay structurally isomorphic with guardrails.rs's established byte/string-scanner style, per the plan's explicit '同构' instruction"
  - "Disagreement parsing distinguishes two malformed cases the tests require to behave differently: a missing 4th (resolution) segment still yields a valid Disagreement entry defaulting to unresolved (conservative), while missing/wrong 本意见：/复核意见： prefixes are not recognized as a structured entry at all"
  - "agent.cordis.yml's copy of the new guardrail text is reflowed to a single indentation level (no bold markers, no nested numbered-list indentation) because YAML '>-' folded-scalar semantics collapse same-indent lines into one paragraph and preserve only more-indented lines literally — a byte-identical copy of the plan's markdown-styled text would garble the numbered call sequence across differently-indented continuation lines. Verified by parsing the edited file with a permissive YAML loader and inspecting the assembled persona string before committing."

patterns-established:
  - "Persona guardrail additions must be synced to BOTH presets/<domain>/preset.yml (the grep-gated anchor copy scripts/gates/v5/guardrails.mjs checks) and presets/<domain>/agent.cordis.yml's persona.text field (what the engine actually sends to the model) — established by Phase 126, re-confirmed here since this plan's own files_modified list named only the former."

requirements-completed: [MMR-03, MMR-04, MMR-05]

coverage:
  - id: D1
    description: "Cross-review trigger + disagreement rendering: [GUARDRAIL:CROSS_REVIEW] instructs the model to call legal_review_a (then legal_review_b, then adversarial_challenge) before any [HUMAN_REVIEW:]-bound, high-stakes (>100万, contract/limitation/criminal, administrative-penalty, or unverified-supported) conclusion; [GUARDRAIL:SYNTHESIS] fixes the disagreement rendering format `[分歧] 争点 ｜ 本意见：… ｜ 复核意见：… ｜ 是否已消解` and requires reviewer-introduced citations to still carry [verified]/[retrieved]/[unverified]; review.rs::scan_review parses that exact format"
    requirement: "MMR-03"
    verification:
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/review.rs#disagreement_line_resolved_true_when_final_segment_says_resolved"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/review.rs#multiple_disagreement_lines_parsed_independently"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/review.rs#literal_bracket_text_without_pipe_structure_not_misrecognized"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/review.rs#literal_bracket_text_with_wrong_prefixes_not_misrecognized"
        status: pass
      - kind: integration
        ref: "apps/desktop/src-tauri/tests/review_test.rs#scan_review_counts_disagreements_and_fatal_challenges_from_constructed_final_draft"
        status: pass
      - kind: other
        ref: "node scripts/gates/v5/guardrails.mjs (model-layer: preset.yml 8 GUARDRAIL anchors + agent.cordis.yml references them)"
        status: pass
      - kind: other
        ref: "python3 tool-name cross-check: every dsh-tool-subagent toolName in engines/acp.cordis.yml is referenced in presets/legal-core/preset.yml"
        status: pass
    human_judgment: false
  - id: D2
    description: "Adversarial challenge early-stop: [GUARDRAIL:SYNTHESIS]'s 早停规则 caps adversarial-challenge rounds at 2 by default and instructs stopping the moment a round surfaces no new 【致命问题】/【可被攻击】 items (or the first round returns 无实质可攻击点); review.rs::RoundTracker + scan_fatal_challenges implement the round-accounting and item-extraction this rule depends on"
    requirement: "MMR-04"
    verification:
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/review.rs#round_tracker_stops_immediately_on_first_round_with_nothing_new"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/review.rs#round_tracker_stops_at_cap_after_max_rounds_with_findings"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/review.rs#round_tracker_second_round_with_nothing_new_stops_before_cap"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/review.rs#fatal_challenges_extracts_multiple_items_stopping_at_next_bracket"
        status: pass
      - kind: integration
        ref: "apps/desktop/src-tauri/tests/review_test.rs#cross_review_end_to_end (asserts challenge_rounds <= 2 from the real session log)"
        status: unknown
    human_judgment: true
    rationale: "The round cap/early-stop LOGIC is fully unit-tested and passing. Whether the persona instruction actually produces this behavior from real models across real multi-round adversarial exchanges can only be confirmed by cross_review_end_to_end, which is #[ignore]'d — it requires network plus real DeepSeek+OpenAI+Anthropic API keys unavailable in this execution environment, matching the project's existing pattern for every other real-engine test (history_test.rs, mapper_test.rs's fixture dump, etc.)."
  - id: D3
    description: "Disagreement escalation cannot be silently dropped: unresolved disagreements must carry a matching [HUMAN_REVIEW: …分歧…] mark; review.rs::ensure_escalated returns the fallback mark text whenever scan_review finds unresolved disagreements but no matching escalation in the text, and returns None (no-op) whenever the model already marked it — never clears an existing mark, matching the MMR-05 '徽记不可自动消除' constraint"
    requirement: "MMR-05"
    verification:
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/review.rs#ensure_escalated_returns_some_when_unresolved_and_unmarked"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/review.rs#ensure_escalated_returns_none_when_already_marked"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/review.rs#ensure_escalated_returns_none_when_no_unresolved_disagreements"
        status: pass
      - kind: integration
        ref: "apps/desktop/src-tauri/tests/review_test.rs#scan_review_ensure_escalated_fallback_fires_when_model_forgets_to_mark"
        status: pass
    human_judgment: false

duration: ~30min
completed: 2026-08-17
status: complete
---

# Phase 128 Plan 2: Review Orchestration Persona, Adversarial Rounds, Synthesis Summary

**Two new persona guardrail segments (`CROSS_REVIEW` trigger conditions, `SYNTHESIS` disagreement-rendering/escalation/early-stop rules) plus a pure Rust text scanner (`review.rs`) that parses `[分歧]` disagreement lines, `【致命问题】` fatal-challenge items, and enforces a never-auto-clearable human-review fallback when the model forgets to escalate**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-08-16T16:12Z (immediately after 128-01)
- **Completed:** 2026-08-16T16:42Z
- **Tasks:** 4
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments
- `presets/legal-core/preset.yml` now carries 8 `[GUARDRAIL:...]` anchors (was 6): `[GUARDRAIL:CROSS_REVIEW]` names the exact trigger conditions (any `[HUMAN_REVIEW:]`-bound conclusion, limitation/contract-validity/criminal-liability determinations, amounts over 100万, administrative-penalty judgments, or `[unverified]`-supported conclusions) and the call sequence (`legal_review_a` → `legal_review_b` if available → `adversarial_challenge` with the reviewers' disagreement list attached); `[GUARDRAIL:SYNTHESIS]` fixes the disagreement rendering format, the resolution standard ("one side produces current-law authority the other cannot rebut" — ambiguous defaults to unresolved), the human-review escalation trigger, the adversarial early-stop rule (cap 2, stop the moment a round finds nothing new), and the "review doesn't relax citation review" constraint
- The exact same content was also added to `presets/legal-core/agent.cordis.yml`'s `persona.text` field — the field actually fed to the model at runtime (the plan's `files_modified` named only `preset.yml`; see Deviations)
- `apps/desktop/src-tauri/src/engine/review.rs` (new, 456 lines): `scan_review()` parses `[分歧] issue｜本意见：…｜复核意见：…｜resolution` lines (conservative on a missing/ambiguous resolution segment, never misrecognizing a bare `[分歧]` in prose), `【致命问题】` fatal-challenge items (stopping at the next `【` section or end of text), and disagreement-related `[HUMAN_REVIEW:]` escalations (reusing `guardrails::scan`); `ensure_escalated()` is the fallback-invariant function — unresolved disagreement + no matching mark => `Some(fallback text)`, never clears an existing mark; `RoundTracker` early-stops adversarial rounds at `(fatal=0, attackable=0)` or the round cap (`DEFAULT_MAX_ROUNDS = 2`)
- `apps/desktop/src-tauri/tests/review_test.rs` (new, 304 lines): 2 offline tests running a constructed final-draft text (3 disagreements/1 unresolved/2 fatal-challenge items) through the public API, asserting both the "already escalated" and "fallback fires" paths; `#[ignore]`d `cross_review_end_to_end` assembles + spawns the real engine, sends a >100万 对赌条款-validity prompt guaranteed to trip `CROSS_REVIEW`, and asserts `subagent/start`/`subagent/end` appear in the session log, adversarial rounds stay ≤2, and the final text carries `[分歧]` or an explicit no-disagreement statement — gated on real DeepSeek+OpenAI+Anthropic keys, skips via `eprintln!` otherwise
- 15 new unit tests in `review.rs` + 2 new integration tests in `review_test.rs`, all passing; all 6 v5 gates (`node scripts/gates/v5/run-gates.mjs`) green throughout, including a real engine-assembly + smoke-start run

## Task Commits

Each task was committed atomically (executed in order 3, 4, 1, 2 — no cross-task dependency, all four are independent additions):

1. **Task 1: Persona guardrail 7 — when to call cross-review tools** - `21f31878` (feat)
2. **Task 2: Persona guardrail 8 — synthesis, disagreement escalation, early-stop** - `62562a60` (feat)
3. **Task 3: review.rs — review artifact scanner** - `03d37ebc` (feat)
4. **Task 4: review_test.rs — integration tests + real-engine e2e gate** - `71719683` (test)

## Files Created/Modified
- `apps/desktop/src-tauri/src/engine/review.rs` - New: `scan_review`, `ensure_escalated`, `RoundTracker`, plus 15 unit tests
- `apps/desktop/src-tauri/tests/review_test.rs` - New: 2 offline integration tests + `#[ignore]`d `cross_review_end_to_end`
- `apps/desktop/src-tauri/src/engine/mod.rs` - Registered `pub mod review;`
- `presets/legal-core/preset.yml` - Appended `[GUARDRAIL:CROSS_REVIEW]` and `[GUARDRAIL:SYNTHESIS]` (grep-gated anchor copy)
- `presets/legal-core/agent.cordis.yml` - Appended the same two guardrail segments to `persona.text` (not in the plan's `files_modified` — see Deviations)

## Decisions Made
- **review.rs stays regex-free**, matching `guardrails.rs`'s established byte/string-scanner style, even though the `regex` crate is already a project dependency (used in `credentials.rs`) — the plan explicitly calls for this module to be "同构" (structurally isomorphic) with `guardrails.rs::scan`.
- **Two distinct "malformed" behaviors for disagreement parsing**, because the plan's own test list requires both: a `[分歧]` line missing its 4th (resolution) segment still becomes a valid `Disagreement` defaulting to `resolved: false` (conservative — silence is treated as unresolved), while a `[分歧]` occurrence lacking the `本意见：`/`复核意见：` structure entirely (e.g. the literal characters appearing in ordinary prose) is not recognized as an entry at all.
- **`ensure_escalated` re-derives its "already marked" check from the raw `text` parameter** rather than trusting `scan.escalations` alone, so a caller that accidentally passes a `scan` computed from different text still gets a correct answer instead of a silently wrong one.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added the same guardrail text to `presets/legal-core/agent.cordis.yml`'s `persona.text`, not just `preset.yml`**
- **Found during:** Task 1, before making any edit — while reading `preset.yml`'s own header comment (line 6): "人设正文在 agent.cordis.yml 的 persona.text 字段中，此处为门禁可检测的锚点副本" (the persona body text lives in `agent.cordis.yml`'s `persona.text` field; this file is a gate-detectable anchor copy).
- **Issue:** The plan's Task 1 and Task 2 `files:` fields name only `presets/legal-core/preset.yml`. `preset.yml` is explicitly NOT what the engine sends to the model at runtime — `agent.cordis.yml`'s `persona.text` is. Editing only `preset.yml` would have satisfied every grep-based verify command in the plan (both tasks' own verify steps, and `scripts/gates/v5/guardrails.mjs`) while leaving the actual model persona completely unchanged — the entire feature (MMR-03/04/05: when to call review tools, how to synthesize, when to escalate) would have been a decorative no-op the drafting model never sees. This is exactly the "silently doing nothing" failure mode Rule 2 exists to catch, and Phase 126 already established the precedent that every guardrail lives in both files (confirmed: all 6 pre-existing guardrails are present verbatim in both `preset.yml` and `agent.cordis.yml`).
- **Fix:** Appended the same two guardrail sections to `agent.cordis.yml`'s `persona.text` YAML folded scalar (`>-`), in the same position (after `[GUARDRAIL:CONFIDENTIALITY]`, before `[SKILL_LOADING]`).
- **A second, related adjustment was required to do this safely:** the plan's literal Task 1/2 text uses markdown bold markers (`**必须**`) and a nested numbered list with extra-indented continuation lines. Tested against a scratch YAML file with a permissive `!!js`-tolerant loader (matching the workaround 128-01's SUMMARY documented for this same file's custom YAML tags) before touching the real file: copying that formatting byte-for-byte into a `>-` folded scalar causes YAML's line-folding rules to merge list items 2 and 3 onto the tail of item 1's continuation line, producing a garbled run-on ("...就什么都不知道。2. 若 legal_review_b 可用...3. 拿到复核意见后..."). Reflowed the `agent.cordis.yml` copy to a single indentation level with no bold markers and blank-line-separated paragraphs instead (still valid, semantically identical content) — confirmed clean by parsing the edited file and printing the assembled persona string before committing. `preset.yml` keeps the plan's exact original formatting since it is plain text with no YAML-folding concern.
- **Files modified:** `presets/legal-core/agent.cordis.yml` (in addition to `presets/legal-core/preset.yml`, which the plan already specified)
- **Verification:** `node scripts/gates/v5/guardrails.mjs` passes; parsed `agent.cordis.yml` with a permissive YAML loader before and after each commit and confirmed the assembled `persona.text` contains both new `[GUARDRAIL:...]` anchors, all three tool names, the `[分歧]` format line, and the `[HUMAN_REVIEW: 模型间存在未消解分歧` escalation format; all 6 v5 gates green
- **Committed in:** `21f31878` (Task 1) and `62562a60` (Task 2) — split one file-pair change per task to keep each commit atomic to its own guardrail segment, per the executor's per-task commit protocol

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing critical functionality), applied identically across both new guardrail segments (2 commits).
**Impact on plan:** Necessary for the plan's actual purpose (multi-model review triggering/synthesis) to reach the model at all, rather than existing only as gate-satisfying dead text. No scope creep beyond the one additional file the fix required; no other file outside the plan's stated scope was touched.

## Issues Encountered
- `cargo clippy --lib --tests -- -D warnings` still reports pre-existing findings in `engine/tailer.rs` and `engine/updater.rs` (17 with `--tests` included, vs. the 12 `--lib`-only count 128-01's `deferred-items.md` already recorded). None are attributable to `review.rs` or `review_test.rs` — spot-checked via targeted grep on clippy's output. Not fixed (out of scope, pre-existing, clippy is not part of `run-gates.mjs`); no new entry needed in `deferred-items.md` since 128-01 already recorded this category.
- The plan's own `<verification>` python snippet requires the same `!!js`-tag workaround 128-01's SUMMARY already documented (`yaml.safe_load` cannot parse `engines/acp.cordis.yml`'s custom Cordis tags without a permissive constructor). Not a regression — pre-existing, and the Rust `subagent_config_test.rs` gate (via `serde_yaml`, which already tolerates these tags) remains the actually-enforced check.

## User Setup Required
None - no external service configuration required. (Runtime note, same as 128-01: `cross_review_end_to_end` needs `OPENAI_API_KEY` + `ANTHROPIC_API_KEY` + `DEEPSEEK_API_KEY` configured via the dev-credentials store to actually run — it is `#[ignore]`d and was not executed in this environment.)

## Next Phase Readiness
- `review.rs`'s `scan_review`/`ensure_escalated`/`RoundTracker` are pure functions with no caller yet — nothing in the running app invokes them after a turn completes. Wiring them into the actual turn-completion path (append `ensure_escalated`'s fallback text to the displayed output when it fires, log the fact that it fired) is explicitly out of this plan's scope (`<context>`: "本 plan 只有一处 Rust 代码...职责是解析...编排本身由主代理人设驱动") and is the most likely next piece of work — REQUIREMENTS.md's MMR-05 also mentions "app 侧兜底补标并记诊断日志" (app-side fallback marking + diagnostic logging), which this plan's `ensure_escalated` makes possible but does not itself perform.
- MMR-06 ("呈现与触发" — reusing `ReviewSummary`/`SynthesisViewer`/etc., the "深度复核" manual-trigger button, 0/1/≥2-vendor adaptive degradation messaging) is untouched by this plan, as expected — it is the next plan's (128-03, presumably) work, and can now consume `credentials::review_capability()` (from 128-01) and `review::scan_review()`/`ensure_escalated()` (from this plan) as its primitives.
- The `cross_review_end_to_end` integration test is ready to run manually once real DeepSeek + OpenAI + Anthropic keys are configured — it is the only evidence that the persona actually drives the DSH engine to invoke the three review subagents end to end; nothing in this plan's automated (non-`#[ignore]`) test suite proves that.

## Self-Check: PASSED

### Verification Results
- `cargo test review` (apps/desktop/src-tauri): **PASS** — 23 passed (lib) + 2 passed/1 ignored (review_test.rs) + 3 passed (subagent_config_test.rs, unaffected), 0 failed
- `cargo check` (apps/desktop/src-tauri): **PASS** — clean build
- `grep -c '\[GUARDRAIL:' presets/legal-core/preset.yml`: **PASS** — 8
- `grep -c '\[分歧\]' presets/legal-core/preset.yml`: **PASS** — 1 (the format-spec line)
- Tool-name cross-check (`legal_review_a`/`legal_review_b`/`adversarial_challenge` all referenced in `preset.yml`): **PASS**
- `grep -rn "fork-in-process"` across all files this plan touched: **PASS** — 0 hits
- `node scripts/gates/v5/run-gates.mjs`: **PASS** — 6 passed, 0 failed (engine-assembly, event-mapping, token-budget, guardrails, offline-assets, update-rollback)
- `apps/flutter_app/` diff across this plan's commits: **PASS** — 0 files touched
- File existence: all 5 files (2 created, 3 modified) confirmed present on disk
- Commit existence: all 4 task commit hashes confirmed present via `git log --oneline`
- `git status --short`: clean — no untracked files left behind

---
*Phase: 128-multi-model-review*
*Completed: 2026-08-17*
