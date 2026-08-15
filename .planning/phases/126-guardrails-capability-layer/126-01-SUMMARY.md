---
phase: 126-guardrails-capability-layer
plan: 126-01
subsystem: content
tags: [semver, sha256, content-pack, presets, token-budget, gate, tauri]

requires:
  - phase: 122-engine-assembly-pipeline-overhaul
    provides: engine paths module, lockfile assembler, acp.cordis.yml base
  - phase: 123-engine-supervisor-real-path
    provides: build_engine_env credential injection
provides:
  - ContentManifest serde model with semver pre-release-aware compatibility
  - ContentUpdater with UpdateOutcome enum (UpToDate/Updated/Skipped/RolledBack)
  - Per-skill sha256 verification + atomic skills/current pointer + one-gen retention
  - Tauri commands check_content_update + get_content_status
  - materialize_presets (overwrite deployment to DSH_HOME/.agent-presets/)
  - INKSTATUTE_SKILL_DIRS runtime env injection (acp.cordis.yml customSkillDirs)
  - Token budget gate (SKL-13) registered in run-gates.mjs
affects: [127-packaging-three-layer-updates, 128-multi-model-cross-review]

actuals:
  tokens: 5200
  tasks: 4
  commits: 4

tech-stack:
  added: [semver = "1", zip = "2"]
  patterns: [semver pre-release-aware compatibility, atomic pointer switch, env-injected skill dirs, frontmatter budget estimation]

key-files:
  created:
    - apps/desktop/src-tauri/src/content/mod.rs
    - apps/desktop/src-tauri/src/content/manifest.rs
    - apps/desktop/src-tauri/src/content/updater.rs
    - apps/desktop/src-tauri/src/content/presets.rs
    - apps/desktop/src-tauri/src/commands/content.rs
    - scripts/gates/v5/token-budget.mjs
  modified:
    - apps/desktop/src-tauri/Cargo.toml
    - apps/desktop/src-tauri/src/lib.rs
    - apps/desktop/src-tauri/src/commands/mod.rs
    - apps/desktop/src-tauri/src/engine/credentials.rs
    - engines/acp.cordis.yml
    - engines/engine-lock.json
    - scripts/gates/v5/run-gates.mjs

key-decisions:
  - "semver crate VersionReq::matches does not match pre-release versions; fall back to direct Version comparison when engine version has pre-release identifier"
  - "acp.cordis.yml customSkillDirs changed from static list to !!js env var injection — content updates need only engine restart, no yml rewrite"
  - "zip crate added (deflate-only) for content pack extraction — required by updater, not explicitly listed in plan but implied by zip download/extract flow"
  - "Engine lock regenerated after acp.cordis.yml change (cordis_config_sha256)"

patterns-established:
  - "Pre-release semver compatibility: parse as Version first (direct compare), fall back to VersionReq with manual comparator checking for pre-release engine versions"
  - "Atomic pointer switch: write to .tmp then rename — same pattern as engine/current pointer"
  - "Env-injected skill dirs: INKSTATUTE_SKILL_DIRS comma-separated absolute paths, parsed in acp.cordis.yml via !!js"

requirements-completed: [SKL-11, SKL-12, SKL-13]

coverage:
  - id: D1
    description: "ContentManifest serde model with semver pre-release-aware is_compatible_with"
    requirement: "SKL-12"
    verification:
      - kind: unit
        ref: "apps/desktop/src-tauri/src/content/manifest.rs#prerelease_rc6_vs_rc5_min_is_compatible"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/content/manifest.rs#prerelease_rc5_vs_rc6_min_is_incompatible"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/content/manifest.rs#prerelease_rc6_vs_stable_0_2_0_is_incompatible"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/content/manifest.rs#invalid_engine_version_returns_false_no_panic"
        status: pass
    human_judgment: false
  - id: D2
    description: "ContentUpdater with UpdateOutcome enum, sha256 verify, atomic pointer, rollback"
    requirement: "SKL-12"
    verification:
      - kind: unit
        ref: "apps/desktop/src-tauri/src/content/updater.rs#sha256_mismatch_deletes_partial_and_keeps_current"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/content/updater.rs#incompatible_manifest_returns_skipped_no_download"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/content/updater.rs#network_failure_returns_skipped_no_panic"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/content/updater.rs#success_path_current_points_to_new_version_old_dir_remains"
        status: pass
    human_judgment: false
  - id: D3
    description: "Presets materialization + INKSTATUTE_SKILL_DIRS runtime env injection"
    requirement: "SKL-11"
    verification:
      - kind: unit
        ref: "apps/desktop/src-tauri/src/content/presets.rs#materialize_presets_copies_domains_and_returns_names"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/content/presets.rs#build_skill_dirs_env_returns_absolute_paths"
        status: pass
      - kind: unit
        ref: "apps/desktop/src-tauri/src/engine/credentials.rs#build_engine_env_skill_dirs_are_absolute_paths"
        status: pass
      - kind: integration
        ref: "apps/desktop/src-tauri/src/content/presets.rs#real_engine_skill_catalog [#[ignore]]"
        status: unknown
    human_judgment: false
  - id: D4
    description: "Token budget gate (SKL-13) — frontmatter parseable, name unique, render length ≤ budget"
    requirement: "SKL-13"
    verification:
      - kind: unit
        ref: "scripts/gates/v5/token-budget.mjs — node scripts/gates/v5/token-budget.mjs"
        status: pass
      - kind: unit
        ref: "scripts/gates/v5/run-gates.mjs — 3 passed, 0 failed"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-08-16
status: complete
---

# Phase 126-01: Domain Presets, Content Packs, Token Budget Gate Summary

**Content manifest with semver pre-release compatibility, auto-updater with sha256/atomic/rollback, presets materialization with env-injected skill dirs, and token budget gate**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-08-16T01:35Z
- **Completed:** 2026-08-16T02:20Z
- **Tasks:** 4
- **Files modified:** 13 (6 created, 7 modified)

## Accomplishments
- ContentManifest serde model with semver pre-release-aware `is_compatible_with` — handles `0.1.0-rc.6 >= 0.1.0-rc.5` correctly (the key v5 semantic change from v4 string equality)
- ContentUpdater with `UpdateOutcome` enum (UpToDate/Updated/Skipped/RolledBack), per-skill sha256 verification, atomic `skills/current` pointer, one-generation retention, never blocks startup
- Tauri commands `check_content_update` + `get_content_status` registered in `lib.rs`
- `materialize_presets` copies repo `presets/<domain>/` to `<dsh_home>/.agent-presets/<domain>/` (overwrite deployment)
- `acp.cordis.yml` `customSkillDirs` changed to runtime-injected via `INKSTATUTE_SKILL_DIRS` env var — content updates need only engine restart
- `build_engine_env` (Phase 123-01) now sets `INKSTATUTE_SKILL_DIRS` to comma-separated absolute paths
- Token budget gate (SKL-13) scans `presets/*/` SKILL.md frontmatter, estimates render length, asserts ≤ 8,000 chars (INKSTATUTE_SKILL_BUDGET override), prints overflow + top 10 longest on failure

## Task Commits

Each task was committed atomically:

1. **Task 1: Content manifest serde model** - `9475ae5b` (feat)
2. **Task 2: Content updater with UpdateOutcome** - `63926dfa` (feat)
3. **Task 3: Presets materialization + INKSTATUTE_SKILL_DIRS** - `55273d45` (feat)
4. **Task 4: Token budget gate + engine-lock regen** - `28f12ebd` (feat)

## Files Created/Modified
- `apps/desktop/src-tauri/src/content/mod.rs` - Content module declaration
- `apps/desktop/src-tauri/src/content/manifest.rs` - ContentManifest serde model with semver pre-release compatibility
- `apps/desktop/src-tauri/src/content/updater.rs` - ContentUpdater with UpdateOutcome, sha256 verify, atomic pointer, rollback
- `apps/desktop/src-tauri/src/content/presets.rs` - materialize_presets + build_skill_dirs_env + skill_dir_paths
- `apps/desktop/src-tauri/src/commands/content.rs` - Tauri commands check_content_update + get_content_status
- `apps/desktop/src-tauri/src/lib.rs` - Content module + command registration
- `apps/desktop/src-tauri/src/commands/mod.rs` - Content command module
- `apps/desktop/src-tauri/src/engine/credentials.rs` - build_engine_env sets INKSTATUTE_SKILL_DIRS
- `apps/desktop/src-tauri/Cargo.toml` - Added semver = "1" and zip = "2" (deflate-only)
- `engines/acp.cordis.yml` - customSkillDirs changed to !!js env var injection
- `engines/engine-lock.json` - Regenerated after acp.cordis.yml change
- `scripts/gates/v5/token-budget.mjs` - Token budget gate (SKL-13)
- `scripts/gates/v5/run-gates.mjs` - Registered token-budget gate

## Decisions Made
- **semver pre-release handling**: The `semver` crate's `VersionReq::matches` does not match pre-release versions by default. When the engine version contains a pre-release identifier, we fall back to direct `Version` comparison (if min is exact) or manual comparator checking (if min is a range). This is the key v5 semantic change from v4's string equality.
- **zip crate added**: The plan implies zip download/extract for content packs (referencing the Flutter `zip_extractor.dart`). Added `zip = "2"` with deflate-only feature to minimize dependency footprint. This is a necessary dependency for the content updater functionality.
- **Engine lock regenerated**: After changing `acp.cordis.yml`, ran `scripts/gen-engine-lock.mjs` to update `cordis_config_sha256` in `engine-lock.json`. This is required by the engine-assembly gate (GATE-11.3).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added zip crate dependency**
- **Found during:** Task 2 (Content updater implementation)
- **Issue:** Plan references Flutter `zip_extractor.dart` as behavior reference but doesn't explicitly list `zip` crate in dependencies. Content pack extraction requires zip support.
- **Fix:** Added `zip = { version = "2", default-features = false, features = ["deflate"] }` to Cargo.toml — deflate-only to minimize footprint.
- **Files modified:** apps/desktop/src-tauri/Cargo.toml
- **Verification:** cargo check passes, extract_zip test passes
- **Committed in:** 63926dfa (Task 2 commit)

**2. [Rule 2 - Missing Critical] Regenerated engine-lock.json after acp.cordis.yml change**
- **Found during:** Task 4 (Plan-level verification)
- **Issue:** Changing `acp.cordis.yml` `customSkillDirs` invalidated `cordis_config_sha256` in `engine-lock.json`, causing GATE-11.3 to fail.
- **Fix:** Ran `node scripts/gen-engine-lock.mjs` to regenerate the lock file.
- **Files modified:** engines/engine-lock.json
- **Verification:** GATE-11.3 passes, engine-assembly gate all green
- **Committed in:** 28f12ebd (Task 4 commit)

---

**Total deviations:** 2 auto-fixed (2 missing critical)
**Impact on plan:** Both auto-fixes necessary for correctness. The zip crate is required by the updater's extract functionality; the engine-lock regen is required by the engine-assembly gate after any acp.cordis.yml change. No scope creep.

## Issues Encountered
- `semver` crate's `Op` enum is `#[non_exhaustive]`, requiring a wildcard match arm — fixed by adding `_ => return false` for conservative handling of Tilde/Caret/Wildcard ops.
- `zip` crate v2 API uses `SimpleFileOptions::default()` instead of `::new()` — fixed in test helper.
- Tests using `INKSTATUTE_APP_ROOT` env var needed a `Mutex` to prevent parallel execution race conditions — added `ENV_LOCK` static mutex.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Content manifest, updater, presets materialization, and token budget gate are complete.
- Phase 126-02 (guardrails double-layer) can proceed — the presets persona segments are already in place from Phase 113.
- Phase 127 (packaging) can use the content updater for the three-layer update system.
- The `#[ignore]` integration test for real engine spawn requires a real engine assembly + API key — run manually in Phase 127 integration testing.

## Self-Check: PASSED

### Verification Results
- `cargo test content`: **PASS** — 27 passed, 0 failed, 1 ignored
- `cargo check`: **PASS** — no errors, no warnings
- `node scripts/gates/v5/run-gates.mjs`: **PASS** — 3 passed, 0 failed (engine-assembly, event-mapping, token-budget)
- `node scripts/gates/v5/token-budget.mjs`: **PASS** — 15 skills, 669 chars ≤ 8000 budget
- `INKSTATUTE_SKILL_BUDGET=10 node scripts/gates/v5/token-budget.mjs`: **FAIL (expected)** — overflow 659 chars, top 10 longest printed
- `grep -n 'INKSTATUTE_SKILL_DIRS' engines/acp.cordis.yml apps/desktop/src-tauri/src/engine/credentials.rs`: **PASS** — hits in both files

---
*Phase: 126-guardrails-capability-layer*
*Completed: 2026-08-16*
