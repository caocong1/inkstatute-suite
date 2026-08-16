---
phase: 128-multi-model-review
plan: 128-01
subsystem: engine
tags: [subagent, multi-model-review, dsh-tool-subagent, fresh-context, cordis-config, credentials, mmr]

requires:
  - phase: 122-engine-assembly-pipeline-overhaul
    provides: engine paths module, lockfile assembler, gen-engine-lock.mjs pipeline, run-gates.mjs
  - phase: 126-guardrails-capability-layer
    provides: build_engine_env credential injection point, precedent for re-syncing engine-lock.json after acp.cordis.yml edits
provides:
  - Four subagent packages pinned at the exact dsh_version (dsh-subagent, dsh-subagent-spawn-in-process, dsh-tool-subagent, dsh-tool-subagent-report); dsh-subagent-fork-in-process deliberately excluded from the pin
  - Three @deepseek-ai/dsh-tool-subagent Cordis instances (reviewer-a/openai, reviewer-b/anthropic, challenger/openai) with independent personas, read-only tool allowlists, maxDepth 1
  - configured_providers() / review_capability() (SingleVendor/CrossVendor/None) primitives in credentials.rs
  - build_engine_env injects every configured provider's key, not just the active one, so subagents can call a different vendor than the drafting model
  - Static fresh-context + config-shape gate (subagent_config_test.rs) — v5 equivalent of v3.1's test_fresh_context.py AST gate
affects: [128-02, 128-03]

actuals:
  tokens: 6507
  tasks: 5
  commits: 5

tech-stack:
  added: []
  patterns: [spawn-only subagent transport for fresh-context guarantee, pure-function extraction for testability around shared process-global credential state]

key-files:
  created:
    - apps/desktop/src-tauri/tests/subagent_config_test.rs
  modified:
    - engines/dsh-pin.txt
    - engines/acp.cordis.yml
    - engines/engine-lock.json
    - apps/desktop/src-tauri/src/engine/credentials.rs

key-decisions:
  - "Fresh-context guarantee enforced structurally, not at runtime: dsh-subagent-fork-in-process is simply never pinned, so it cannot enter the dependency tree regardless of what any config later references"
  - "review_capability()'s 0/1/N branch selection (classify_review_capability) and build_engine_env's env-pair assembly (provider_env_pairs) are pure, private helper functions — split out specifically so they are unit-testable with synthetic input rather than depending on the real credential store"
  - "reviewer-b's persona is a verbatim copy of reviewer-a's, per the plan's explicit instruction (both are independent-review personas; only agentOptions differs)"
  - "engine-lock.json regenerated a second time after the acp.cordis.yml edit (Task 3), not just once after the pin edit (Task 2), to keep cordis_config_sha256 in sync — same pattern documented in 126-01's SUMMARY"
  - "Test function names in subagent_config_test.rs are prefixed subagent_config_* specifically so the plan's own `cargo test subagent_config` filter selects them (cargo filters by function name, not file name)"

patterns-established:
  - "Pure-function extraction for credential-adjacent test determinism: when a function's correctness depends on has_key()/load_key() across every provider, split the I/O (credential lookup) from the logic (branch selection, env-pair assembly) so the logic can be unit-tested without touching global env state shared across the crate's test binary"

requirements-completed: [MMR-01, MMR-02]

coverage:
  - id: D1
    description: "acp.cordis.yml registers exactly 3 dsh-tool-subagent instances (reviewer-a, reviewer-b, challenger), each bound to a different vendor model, independent persona, read-only tool allowlist, maxDepth 1"
    requirement: "MMR-01"
    verification:
      - kind: unit
        ref: "apps/desktop/src-tauri/tests/subagent_config_test.rs#subagent_config_exactly_three_review_tool_subagents_with_unique_tool_names"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/tests/subagent_config_test.rs#subagent_config_every_review_tool_subagent_has_max_depth_one"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/tests/subagent_config_test.rs#subagent_config_every_review_tool_subagent_has_nonempty_read_only_tool_allowlist"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/tests/subagent_config_test.rs#subagent_config_every_subagent_provider_is_declared_in_llm_providers_and_spans_two_vendors"
        status: pass
      - kind: integration
        ref: "node scripts/gates/v5/run-gates.mjs (engine-assembly: real lockfile assembly + smoke start with the 3 subagent instances wired into acp.cordis.yml)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Fresh-context guarantee: spawn-only subagent transport, fork-in-process absent from pin, lock, and config"
    requirement: "MMR-02"
    verification:
      - kind: unit
        ref: "apps/desktop/src-tauri/tests/subagent_config_test.rs#subagent_config_no_fork_transport_in_config_or_lock"
        status: pass
      - kind: other
        ref: "grep -c 'fork-in-process' engines/acp.cordis.yml engines/engine-lock.json engines/dsh-pin.txt (all 0)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Credential provisioning for cross-vendor review: build_engine_env injects every configured provider's key (not just active), review_capability() reports SingleVendor/CrossVendor/None so the engine and future UI can degrade gracefully when only one vendor is configured"
    requirement: "MMR-01"
    verification:
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/credentials.rs#classify_review_capability_variants_by_configured_count"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/credentials.rs#provider_env_pairs_only_includes_given_providers"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/credentials.rs#configured_providers_and_build_engine_env_cover_every_provider_when_all_configured"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/credentials.rs#review_capability_debug_never_leaks_key_material"
        status: pass
    human_judgment: false

duration: ~50min
completed: 2026-08-16
status: complete
---

# Phase 128-01: Reviewer Subagents — Config + Fresh Context Guarantee Summary

**Three cross-review/adversarial dsh-tool-subagent instances wired into acp.cordis.yml (openai/anthropic vendors, read-only, maxDepth 1), fork-in-process structurally excluded from the pin, and credentials.rs now injects every configured provider's key with a SingleVendor/CrossVendor/None capability report for graceful degradation**

## Performance

- **Duration:** ~50 min
- **Started:** 2026-08-16T15:20Z
- **Completed:** 2026-08-16T16:10Z
- **Tasks:** 5
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments
- `engines/dsh-pin.txt` pins 4 new subagent packages at the exact `dsh_version` (`dsh-subagent`, `dsh-subagent-spawn-in-process`, `dsh-tool-subagent`, `dsh-tool-subagent-report`); `dsh-subagent-fork-in-process` deliberately never pinned
- `engines/engine-lock.json` regenerated: 196 → 201 locked entries, no fork transport anywhere in the dependency tree
- `engines/acp.cordis.yml` registers `subagent-runtime` + `subagent-spawn` (spawn-only transport) and three `dsh-tool-subagent` instances: `reviewer-a` (openai/gpt-5), `reviewer-b` (anthropic/claude-sonnet-4-5, persona verbatim-copied from reviewer-a), `challenger` (openai/gpt-5) — each `maxDepth: 1` with a `read/grep/glob/skill`-only tool allowlist
- `credentials.rs` adds `configured_providers()` and `review_capability()` (`SingleVendor { provider }` / `CrossVendor { providers }` / `None`, judged by distinct-vendor count) and changes `build_engine_env` to inject the API key for every configured provider, not just the active one — the review/challenge subagents can now actually reach a different vendor than the drafting model
- `apps/desktop/src-tauri/tests/subagent_config_test.rs` — 5 static assertions against the real `acp.cordis.yml`/`engine-lock.json` on disk (the v5 equivalent of v3.1's `test_fresh_context.py` AST gate), spot-checked to actually catch drift by temporarily injecting `bash` into a reviewer's allowlist and confirming the test fails
- All 6 v5 gates green throughout (`node scripts/gates/v5/run-gates.mjs`), including a real engine assembly + smoke start with the new subagent plugins wired in

## Task Commits

Each task was committed atomically:

1. **Task 1: Pin subagent packages** - `2d9b9a9e` (feat)
2. **Task 2: Regenerate engine-lock.json** - `9dc4afbe` (feat)
3. **Task 3: Register subagent transport + review tools in acp.cordis.yml** - `fedce194` (feat)
4. **Task 4: Graceful degradation for unconfigured review vendors** - `4c045a4c` (feat)
5. **Task 5: Static fresh-context gate** - `66e02f73` (test)

## Files Created/Modified
- `engines/dsh-pin.txt` - Added 4 subagent packages to the pin list; `dsh-subagent-fork-in-process` deliberately omitted
- `engines/acp.cordis.yml` - Registered subagent-runtime, subagent-spawn, and 3 dsh-tool-subagent instances (reviewer-a, reviewer-b, challenger)
- `engines/engine-lock.json` - Regenerated twice (once per pin change, once per acp.cordis.yml change) — 196 → 201 packages
- `apps/desktop/src-tauri/src/engine/credentials.rs` - Added configured_providers(), ReviewCapability, review_capability(), classify_review_capability(); build_engine_env now injects every configured provider's key via the new provider_env_pairs() helper
- `apps/desktop/src-tauri/tests/subagent_config_test.rs` - New: static config-shape + fresh-context gate for the 3 review subagents

## Decisions Made
- **Fork transport excluded structurally, not at runtime:** `dsh-subagent-fork-in-process` is simply never added to `dsh-pin.txt`, so `npm install` can never pull it into the dependency tree regardless of what any future config change references. The static test (Task 5) then locks this invariant in.
- **Pure-function extraction for testability:** `classify_review_capability` (0/1/N → `ReviewCapability` variant) and `provider_env_pairs` (provider/key pairs → env var pairs) are private pure functions, unit-tested with synthetic input. This was not just a style preference — see Deviations below for the concrete bug this design choice sidesteps.
- **reviewer-b's persona is a verbatim copy of reviewer-a's,** per the plan's explicit instruction ("与 reviewer-a 相同的复核人设，逐字复制"). Only `agentOptions` (vendor/model) differs between the two.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Regenerated engine-lock.json a second time after the acp.cordis.yml edit**
- **Found during:** Task 3
- **Issue:** The plan's task order runs `gen-engine-lock.mjs` in Task 2, *before* Task 3 edits `acp.cordis.yml`. `engine-lock.json`'s `cordis_config_sha256` is a hash of whatever `acp.cordis.yml` contains at generation time, so after Task 3's edit the lock's stored hash no longer matched the file — GATE-11.3 ("cordis sha256 must match actual file") would fail, and Task 3's own verify step explicitly requires the full gate suite to pass.
- **Fix:** Re-ran `node scripts/gen-engine-lock.mjs` after the `acp.cordis.yml` edit, before committing Task 3. Same pattern already documented in Phase 126-01's SUMMARY ("Engine lock regenerated after acp.cordis.yml change").
- **Files modified:** engines/engine-lock.json (bundled into the Task 3 commit alongside acp.cordis.yml, since the two must stay in sync)
- **Verification:** `node scripts/gates/v5/run-gates.mjs` — 6 passed, 0 failed, including a real assembly + smoke start with the new plugins wired in
- **Committed in:** fedce194 (Task 3 commit)

**2. [Rule 1 - Bug] Renamed test functions so the plan's own `cargo test subagent_config` filter actually selects them**
- **Found during:** Task 5, running the plan's own overall `<verification>` block
- **Issue:** `cargo test <substring>` filters by fully-qualified test *function* name, not by the file/binary name. My first draft named the test functions descriptively (e.g. `no_fork_transport_in_config_or_lock`) without the substring "subagent_config" anywhere in them. Running `cargo test subagent_config` therefore matched and ran **zero** tests across the whole crate and printed "test result: ok" for every binary — a gate that silently verifies nothing while reporting success is worse than no gate at all.
- **Fix:** Renamed all 5 test functions with a `subagent_config_` prefix. Confirmed `cargo test subagent_config` now runs exactly the intended 5 tests.
- **Files modified:** apps/desktop/src-tauri/tests/subagent_config_test.rs
- **Verification:** `cargo test subagent_config` → "5 passed, 0 failed" from `tests/subagent_config_test.rs`, 0 from every other binary
- **Committed in:** 66e02f73 (Task 5 commit)

**3. [Rule 1 - Bug] Serialized credentials.rs tests that mutate a shared process-global env var**
- **Found during:** Task 4, first run of the new `build_engine_env`/`configured_providers` test
- **Issue:** The new test set `TEST_API_KEY_ENV` and expected it to stay set across several `has_key()`/`load_key()` calls, but 3 *pre-existing* tests in the same file already mutate the same env var (set → assert → remove) with no synchronization. `cargo test` runs `#[test]` fns on a thread pool by default, so one test's `remove_var` interleaved with mine mid-run: the new test failed non-deterministically with `configured_providers().len()` returning 1 instead of 9. Separately (not fixed, out of scope — see `deferred-items.md`): `engine::supervisor`'s spawn-test helper sets the *same* env var and never clears it, which would make any test asserting a provider is *unconfigured* order-dependent on whether a supervisor test happened to run first in the same test binary.
- **Fix:** Added a `static ENV_TEST_LOCK: Mutex<()>` to `credentials.rs`'s test module (poison-recovering, so one panicking test can't cascade-fail the rest) and acquired it in all 4 tests that mutate `TEST_API_KEY_ENV` (3 pre-existing + 1 new). For the *negative* assertion specifically ("an unconfigured provider must not appear in build_engine_env's output"), extracted `provider_env_pairs` as a pure function tested with synthetic input instead — sidesteps the cross-file pollution risk entirely rather than just reducing it.
- **Files modified:** apps/desktop/src-tauri/src/engine/credentials.rs
- **Verification:** 8 repeated `cargo test credentials` runs and 4 repeated full `cargo test --lib` runs, all green with shuffled test order each time (confirms parallel execution, confirms the fix holds)
- **Committed in:** 4c045a4c (Task 4 commit)

**4. [Documentation adjustment, not a code fix] Reworded a plan-specified comment that collided with the plan's own verify command**
- **Found during:** Task 3
- **Issue:** The plan's literal Task 3 content includes the comment `# 刻意不装 fork-in-process —— 复核者若看见起草者的推理会被锚定` immediately above the new subagent block — but Task 3's own verify step is `grep -c 'fork-in-process' engines/acp.cordis.yml` expecting **0**. The plan's prescribed action content and its prescribed verify command directly contradict each other: the explanatory comment necessarily contains the exact string the grep checks for absence.
- **Resolution:** Reworded the comment to "刻意不用 fork 型子代理传输（继承父会话全部历史）" — same explanation (fork inherits the drafter's full session history, so it's deliberately not used), without the literal substring. Preserves the documentation intent while satisfying the grep exactly as specified.
- **Files modified:** engines/acp.cordis.yml
- **Committed in:** fedce194 (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (1 blocking, 1 bug/gate-integrity, 1 bug/test-flakiness) + 1 documentation wording adjustment.
**Impact on plan:** All fixes were necessary for the plan's own stated verify criteria to hold, or for the new gate to actually verify what it claims to. No scope creep — no file outside the plan's `files_modified` list was changed.

## Issues Encountered
- **`dsh-pin.txt`'s raw `grep -c '@deepseek-ai/'` count is 21, not the plan's stated 20.** The file's pre-existing header comment (line 6: `# @deepseek-ai/dsh-* 的 latest 标签指向 0.0.1-rc.1...`) also matches the pattern, inflating the naive count by 1. Confirmed via `grep -n` that the actual package-list line count is exactly 20 (16 original + 4 new), matching the task's real acceptance criterion ("四包入 pin"). Left the pre-existing comment untouched — out of scope for this task's action (append 4 packages), and rewriting unrelated prose just to satisfy a substring-count script felt like optimizing the wrong thing.
- **`python3 -c "import yaml; yaml.safe_load(...)"` cannot parse `engines/acp.cordis.yml` as shipped** — the file has used Cordis's custom `!!js <expr>` YAML tag since Phase 122/126 (`persistenceRoot: !!js process.env.DSH_HOME + '/sessions'`, etc.), which is not standard YAML and PyYAML's default `SafeLoader` has no constructor for it (`ConstructorError: could not determine a constructor for the tag 'tag:yaml.org,2002:js'`). This affects the plan's own overall `<verification>` python snippet, and is pre-existing (not caused by this plan — the tag was already in the file). Worked around for my own verification by registering a permissive constructor that treats `!!js` scalars as plain strings (sufficient for structural assertions; does not evaluate the JS). The Rust integration test (Task 5) is unaffected — `serde_yaml` in this crate already tolerates these tags (proven by the pre-existing `env_vars_match_cordis_config` test), so `subagent_config_test.rs` is the actually-enforced gate going forward, not the plan's python snippet.

## User Setup Required
None - no external service configuration required. (Runtime note for later plans: `reviewer-a`/`challenger` need an `OPENAI_API_KEY` and `reviewer-b` needs an `ANTHROPIC_API_KEY` configured for cross-vendor review to actually activate at request time — `review_capability()` reports `SingleVendor`/`None` gracefully when they are absent, matching CONTEXT.md Risk #2's mitigation.)

## Next Phase Readiness
- `review_capability()` (`SingleVendor`/`CrossVendor`/`None`) is exactly the primitive MMR-06's "按已配置厂商数自适应降级" (0/1/≥2 vendor degradation) UI messaging will consume in a later plan (128-02 or 128-03) — not wired to any UI yet, since this plan is deliberately config + credentials only ("本 plan 不写任何编排逻辑").
- The 3 subagent tools (`legal_review_a`, `legal_review_b`, `adversarial_challenge`) are now callable by the main agent per its persona, but no persona anchor yet instructs it *when* to call them (MMR-03/04/05/06 — automatic trigger on `[HUMAN_REVIEW:]`-level conclusions, the "深度复核" button, structured output format, disagreement escalation) — that is the next plans' work.
- `deferred-items.md` in this phase directory records 3 out-of-scope discoveries (an un-cleaned test env var in `engine::supervisor`, 12 pre-existing clippy findings elsewhere, Phase 127's missing SUMMARY.md files) for future cleanup — none block this plan or the phase.

## Self-Check: PASSED

### Verification Results
- `cargo test subagent_config` (apps/desktop/src-tauri): **PASS** — 5 passed, 0 failed
- `cargo test credentials` (apps/desktop/src-tauri): **PASS** — 13 passed, 0 failed (8 repeated runs, all green)
- `cargo test --lib` (apps/desktop/src-tauri): **PASS** — 138 passed, 0 failed, 1 pre-existing `#[ignore]`d real-engine test (4 repeated runs, all green)
- `node scripts/gates/v5/run-gates.mjs`: **PASS** — 6 passed, 0 failed
- `grep -c 'fork-in-process' engines/acp.cordis.yml engines/engine-lock.json engines/dsh-pin.txt`: **PASS** — 0, 0, 0
- Gate spot-check: temporarily added `bash` to reviewer-a's `toolFilter.allow` → `subagent_config_every_review_tool_subagent_has_nonempty_read_only_tool_allowlist` failed with a clear message; reverted via `git checkout -- engines/acp.cordis.yml`, re-ran clean
- File existence: all 5 files (2 tracked config, 1 lock, 1 credentials module, 1 new test file) confirmed present on disk with `[ -f ... ]`
- Commit existence: all 5 task commit hashes confirmed present via `git log --oneline --all | grep`

---
*Phase: 128-multi-model-review*
*Completed: 2026-08-16*
