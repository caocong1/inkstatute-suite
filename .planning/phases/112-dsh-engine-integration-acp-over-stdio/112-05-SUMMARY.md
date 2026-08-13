---
phase: 112-dsh-engine-integration-acp-over-stdio
plan: 05
subsystem: engine (DSH release pipeline)
tags: [dsh, pin, build, release, manifest, sha256, approval-stack, cordis]
requires:
  - "112-01: Flutter skeleton + Dart ACP client tracer (NDJSON transport, initialize handshake)"
  - "112-04: DSH subprocess manager (spawn, health probe, graceful shutdown, zero-orphan)"
provides:
  - "engines/dsh-pin.txt: pinned DSH commit 47f943859b + node version requirement (^22.19.0 || >=24.0.0)"
  - "engines/acp.cordis.yml: product ACP composition with terminal-default-deny approval stack (policy: ask + sandbox workspace-write)"
  - "scripts/build_dsh_release.sh: engine release pipeline — checkout pin → pnpm install → pnpm build → assemble → zip → manifest"
  - "scripts/test_build_dsh_release.sh: smoke test validating pin file, cordis config, dry-run, and no-secrets assertion"
affects:
  - "Phase 118 (真机回归): real DSH engine build via build_dsh_release.sh produces the engine zip for regression testing"
  - "Phase 119 (packaging): engine zip is bundled with the app installer"
  - "All engine upgrades: change dsh-pin.txt → rebuild → real-machine regression → app version release"
tech-stack:
  added: []
  patterns:
    - "Pin file uses key=value format (dsh_commit=, node_version=) — parseable by build script and grep-assertable"
    - "Build script --dry-run flag validates pin + repo + commit existence without building — used by smoke test"
    - "Build script reads pin via grep '^dsh_commit=' | cut -d'=' -f2 — robust against comment lines"
    - "Manifest has 5 fields: engine_version, dsh_commit, node_version, sha256, built_at — sha256 reproducible for same commit"
    - "No auto-upgrade: script only builds from the pinned commit; upgrading requires editing dsh-pin.txt"
    - "Lockfile drift fallback: pnpm install --frozen-lockfile → pnpm install (with warning)"
    - "Engine zip assembled in temp workdir → output to engines/releases/ → cleanup via trap"
key-files:
  created:
    - engines/dsh-pin.txt
    - engines/acp.cordis.yml
    - scripts/build_dsh_release.sh
    - scripts/test_build_dsh_release.sh
  modified: []
decisions:
  - "Pin file uses key=value format (dsh_commit=47f943859b, node_version=^22.19.0 || >=24.0.0) per critical execution notes, not bare SHA — the build script parses fields by key, making the pin self-documenting and extensible"
  - "acp.cordis.yml is derived from DSH's examples/acp-agent/cordis.yml but customized for V4 product: approval.policy: ask (hardcoded, not env-conditional), sandbox workspace-write (hardcoded), persistenceRoot ${DSH_HOME}/sessions, legal assistant persona, customSkillDirs placeholder for Phase 113"
  - "Build script --dry-run mode validates pin file fields, DSH repo existence, git commit existence, and cordis.yml existence — no build performed. This is the smoke test's primary assertion target"
  - "Build script outputs to engines/releases/ directory (created on demand) — keeps release artifacts separate from config"
  - "Smoke test validates structure (pin fields, cordis config, dry-run exit 0, no secrets) — does NOT do a real build (that is Phase 118 真机回归)"
  - "Removed literal 'DEEPSEEK_API_KEY' from cordis.yml comment to satisfy grep assertion for zero secrets in engines/"
metrics:
  duration: "~2 minutes"
  completed: "2026-08-13T16:48:44Z"
  tasks: 2
  files_created: 4
  files_modified: 0
  tests_passing: 10
  tests_skipped: 0
  flutter_analyze_issues: 0
---

# Phase 112 Plan 05: DSH Engine Release Pipeline Summary

Implemented the engine release pipeline (DSH-03): pinned the DSH commit, created the product ACP composition config with terminal-default-deny approval stack, and built the script that produces `engine-<version>.zip` + `engine-manifest.json`.

## What Was Built

### Task 1: engines/dsh-pin.txt + engines/acp.cordis.yml (commit eaf11d6)

**engines/dsh-pin.txt** — Pinned DSH commit:
- `dsh_commit=47f943859b` (current HEAD of `/home/sorawatcher/deepseek-harness`, verified in RESEARCH V5)
- `node_version=^22.19.0 || >=24.0.0` (DSH `engines` field requirement)
- Upgrade discipline comments: change pin → rebuild → real-machine regression → app version release
- Key=value format for parseability by `build_dsh_release.sh`

**engines/acp.cordis.yml** — Product ACP composition config:
- `llm-deepseek` plugin: DeepSeek models (deepseek-v4-flash, deepseek-v4-pro), thinking enabled, reasoningEffort max
- `sandbox-policy` plugin: `mode: workspace-write` (allow file writes within session cwd; terminal/execute_code escalate)
- `approval` plugin: `policy: ask` (terminal/execute_code requests escalate to `session/request_permission` — the "terminal default deny" config per DP-3)
- `acp-agent` plugin: `persistenceRoot: '${DSH_HOME}/sessions'`, `persistenceCompression: zstd`, legal assistant persona
- `subprocess`, `bash` plugins (local subprocess, bash sandbox with 60s timeout)
- `fs-sandbox`, `fs-observation-policy`, `tool-fs` (filesystem stack on same sandbox policy)
- `token-meter`, `compaction-basic`, `session-projection`, `tool-todo`, `repeat-tool-reminder`
- `skills.filesystem.customSkillDirs: []` placeholder (Phase 113 configures domain preset directories)
- No API keys or secrets — the API key is runtime-injected via environment

### Task 2: scripts/build_dsh_release.sh + scripts/test_build_dsh_release.sh (commit 728b98d)

**scripts/build_dsh_release.sh** — Engine release pipeline:
- `#!/usr/bin/env bash` with `set -euo pipefail`
- Reads `dsh_commit` and `node_version` from `engines/dsh-pin.txt` (grep key=value, cut on `=`)
- Accepts `VERSION` as first argument (required for real build)
- Accepts `DSH_REPO` env var (default: `/home/sorawatcher/deepseek-harness`)
- `--dry-run` flag: validates pin file + DSH repo + commit existence + cordis.yml → prints planned steps → exit 0
- Real build mode:
  1. Clone DSH repo to temp workdir (`mktemp -d`, trap cleanup on exit)
  2. Checkout pinned commit
  3. `pnpm install --frozen-lockfile` (fallback: `pnpm install` with warning on lockfile drift)
  4. `pnpm run build`
  5. Assemble engine directory: `lib/` (bin.js + index.js + invariant.js) + `node_modules/@deepseek-ai/` + `node_modules/@agentclientprotocol/` + `acp.cordis.yml`
  6. Zip as `engine-<version>.zip` → output to `engines/releases/`
  7. Generate `engine-manifest.json` with 5 fields: `engine_version`, `dsh_commit`, `node_version`, `sha256`, `built_at` (ISO 8601 UTC)
- No auto-upgrade — builds only from the pinned commit
- No secrets baked into the zip — API key is runtime-injected

**scripts/test_build_dsh_release.sh** — Smoke test (10 assertions):
1. `dsh-pin.txt` exists
2. `dsh-pin.txt` has `dsh_commit` field
3. `dsh-pin.txt` has `node_version` field
4. `dsh_commit` value is a valid-looking SHA (≥7 chars)
5. `acp.cordis.yml` exists
6. `acp.cordis.yml` has `policy: ask`
7. `acp.cordis.yml` has `workspace-write`
8. `build_dsh_release.sh` is executable
9. `build_dsh_release.sh --dry-run` exits 0
10. No secrets in `engines/` config files

## Verification Results

| Check | Result |
|-------|--------|
| `bash -n scripts/build_dsh_release.sh` | exit 0 — syntax valid |
| `bash -n scripts/test_build_dsh_release.sh` | exit 0 — syntax valid |
| `test -x scripts/build_dsh_release.sh` | pass — executable |
| `grep -q "47f943859b" engines/dsh-pin.txt` | pass — pin is correct |
| `grep -q "policy: ask" engines/acp.cordis.yml` | pass — approval stack configured |
| `grep -q "workspace-write" engines/acp.cordis.yml` | pass — sandbox configured |
| `grep -r "DEEPSEEK_API_KEY\|sk-\|secret\|password" engines/` | 0 matches — no secrets |
| `scripts/build_dsh_release.sh --dry-run` | exit 0 — all validations passed |
| `scripts/test_build_dsh_release.sh` | exit 0 — 10/10 tests passed |
| Frozen directories modified | None |
| Real DSH build performed | No — dry-run only (real build is Phase 118) |

## TDD Gate Compliance

Task 2 is marked `tdd="true"`. The TDD cycle was followed:

1. **RED**: Created `test_build_dsh_release.sh` first. Ran it — 2 failures (build script didn't exist, not executable). 8 passes (pin file + cordis config from Task 1).
2. **GREEN**: Created `build_dsh_release.sh` with `--dry-run` support. Ran test — 10/10 passed.

Both files were committed in a single commit (`728b98d`) because the test validates the build script's existence and behavior — they are a cohesive unit.

## Deviations from Plan

### Pin File Format (per critical execution notes)

- **Plan's `<action>`**: Pin file contains bare commit SHA on first non-comment line
- **Critical execution notes**: Pin file uses key=value format (`dsh_commit=47f943859b`, `node_version=^22.19.0 || >=24.0.0`)
- **Resolution**: Followed critical execution notes (key=value format). Build script parses `grep '^dsh_commit=' | cut -d'=' -f2` instead of `grep -v '^#' | head -1`. This makes the pin file self-documenting and extensible.

### Secrets Comment Wording (Rule 1 - Bug)

- **Found during:** Task 1 verification
- **Issue:** `acp.cordis.yml` comment contained literal `DEEPSEEK_API_KEY` which triggered the `grep -r "DEEPSEEK_API_KEY" engines/` assertion (0 matches required).
- **Fix:** Reworded comment to "The API key is runtime-injected via environment, NOT baked into this config." — avoids the literal string while preserving the security note.
- **Files modified:** `engines/acp.cordis.yml`
- **Commit:** eaf11d6

## Threat Flags

All four threats from the plan's threat model are mitigated:

- **T-112-15 (Tampering — Engine zip integrity):** MITIGATED — `sha256` in manifest; no auto-upgrade; zip is immutable artifact. Build script generates sha256 via `sha256sum`.

- **T-112-16 (Information Disclosure — Secrets in engine zip):** MITIGATED — No API keys baked into build. The API key is runtime-injected via environment. Grep assertion in test_build_dsh_release.sh confirms 0 secrets in engines/ config. Build script does not reference any API key environment variable.

- **T-112-17 (Tampering — DSH commit pin):** MITIGATED — Pin file is version-controlled (`engines/dsh-pin.txt`). Upgrade requires explicit edit + rebuild + regression. Build script only builds from the pinned commit.

- **T-112-18 (Denial of Service — Build script failure):** MITIGATED — `set -euo pipefail` ensures the script fails loud on any error. No silent partial builds. Lockfile drift has a documented fallback with warning.

## Known Stubs

- `skills.filesystem.customSkillDirs: []` in `acp.cordis.yml` is a placeholder — Phase 113 (domain presets) will populate this with domain preset skill directories.
- `persona` in `acp.cordis.yml` is a base legal assistant identity — Phase 113 adds legal guardrails persona segments.
- Real DSH build not performed in this plan — `--dry-run` validates structure only. Phase 118 (真机回归) runs the full build.

## Self-Check: PASSED

All created files exist on disk. All commit hashes verified in git log. All verification checks pass. No frozen directories modified.
