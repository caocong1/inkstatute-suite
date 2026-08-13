---
phase: 112-dsh-engine-integration-acp-over-stdio
plan: 06
subsystem: gates (v4 quality + coverage enforcement)
tags: [gates, dart-analyze, flutter-test, meta-test, engine-manifest, mock-e2e, ci, gsd]
requires:
  - "112-01: Flutter skeleton + Dart ACP client tracer"
  - "112-02: Full ACP v1 client method coverage"
  - "112-03: Approval policy (terminal default deny)"
  - "112-04: DSH subprocess manager"
  - "112-05: DSH engine release pipeline (pin + cordis + build script)"
provides:
  - "scripts/run_v4_gates.py: V4 gate runner — dart analyze + flutter test + engine manifest + mock E2E + meta-test (GATE-01, GATE-02)"
  - "scripts/test_run_v4_gates.py: 36 self-tests for gate runner logic (meta-test, manifest validation, --check parsing, integration, negative)"
  - ".github/workflows/v4-gates.yml: CI workflow running v4 gates on push/PR with Flutter + Node + Python"
affects:
  - "All subsequent V4 phases (113-120): must pass python3 scripts/run_v4_gates.py before /gsd:verify-work"
  - "CI: every push/PR touching apps/flutter_app/, engines/, scripts/, presets/ triggers v4 gates"
tech-stack:
  added: []
  patterns:
    - "Gate runner uses subprocess.run with capture_output for real command execution — no auto-pass, no faked results"
    - "GateResult NamedTuple (name, passed, skipped, message, details) — uniform result type across all gates"
    - "Meta-test walks lib/ dirs via os.walk, maps lib/<subpath> -> test/<subpath>, asserts >=1 _test.dart with content"
    - "Engine-manifest gate validates pin file (dsh_commit + node_version) + cordis config (policy: ask) as required; engine-manifest.json is optional (skip if absent)"
    - "docx-golden gate is a placeholder that skips in Phase 112 (active in Phase 118)"
    - "--check <name> runs a single gate; no --check runs all 6 gates sequentially"
    - "Gate runner uses stdlib only (subprocess, json, pathlib, argparse, os, sys, re, shutil) — no external deps"
    - "Frozen directories (LEG-01) listed as FROZEN_DIRS constant — never in gate scope"
key-files:
  created:
    - scripts/run_v4_gates.py
    - scripts/test_run_v4_gates.py
    - .github/workflows/v4-gates.yml
  modified: []
decisions:
  - "Engine-manifest gate combines pin file + cordis config validation (required) with engine-manifest.json validation (optional/skip). This satisfies both the plan's manifest JSON check and the critical execution notes' pin+cordis requirement."
  - "docx-golden gate included as 6th gate that always skips in Phase 112. Listed in --list output but not in --check choices (active in Phase 118). This provides forward compatibility without false failures."
  - "Meta-test checks directory-level coverage: for each directory containing .dart files under lib/, the corresponding test/ directory must exist with at least one *_test.dart file that has non-zero content (T-112-20 mitigation against empty test dirs)."
  - "Gate runner finds Flutter/Dart via shutil.which() — fails with clear message if not on PATH rather than crashing."
  - "CI workflow uses path filters to only trigger on V4-relevant paths (apps/flutter_app/, engines/, scripts/, presets/) — avoids running on v3.x frozen directory changes."
  - "TDD: test file committed first (RED — ModuleNotFoundError), then implementation (GREEN — 36/36 pass). Two commits per TDD protocol."
metrics:
  duration: "~3 minutes"
  completed: "2026-08-13T16:55:00Z"
  tasks: 2
  files_created: 3
  files_modified: 0
  tests_passing: 36
  tests_skipped: 0
  flutter_analyze_issues: 0
  gate_suite_exit_code: 0
---

# Phase 112 Plan 06: V4 Gates Runner Summary

Implemented the v4 gates runner (GATE-01, GATE-02) — the Phase 112 capstone that enforces code quality and test coverage for all V4 product code. The runner executes 6 gates: dart analyze, flutter test, engine manifest validation, mock E2E, meta-test (lib/ dir coverage), and docx-golden (placeholder for Phase 118). CI integration via GitHub Actions.

## What Was Built

### Task 1: scripts/run_v4_gates.py + scripts/test_run_v4_gates.py (TDD)

**scripts/run_v4_gates.py** — V4 gate runner (624 lines):
- `#!/usr/bin/env python3` with docstring listing all gates
- `GateResult` NamedTuple: `(name, passed, skipped, message, details)` — uniform result type
- `argparse` with `--check` (choices: dart-analyze, flutter-test, engine-manifest, mock-e2e, meta-test) and `--list`
- Gate 1 (dart-analyze): `dart analyze apps/flutter_app` — exit 0 required
- Gate 2 (flutter-test): `flutter test` (from `apps/flutter_app/`) — exit 0 required
- Gate 3 (engine-manifest): validates `engines/dsh-pin.txt` (dsh_commit + node_version fields) + `engines/acp.cordis.yml` (policy: ask) as required; validates `engines/engine-manifest.json` (5 fields: engine_version, dsh_commit, node_version, sha256, built_at) if it exists, skips with warning if not
- Gate 4 (mock-e2e): `flutter test packages/acp_client` (from `apps/flutter_app/`) — exit 0 required
- Gate 5 (meta-test): walks `apps/flutter_app/lib/` and `apps/flutter_app/packages/*/lib/` recursively; for each directory containing .dart files, maps to corresponding `test/` directory and asserts at least one `*_test.dart` file with non-zero content exists
- Gate 6 (docx-golden): placeholder — always skips in Phase 112 (active in Phase 118)
- Summary table: `[PASS]` / `[FAIL]` / `[SKIP]` per gate with message and details
- Exit code: 0 = all gates passed/skipped, 1 = any gate failed
- `FROZEN_DIRS` constant lists LEG-01 frozen directories — never in gate scope
- Stdlib only: `subprocess`, `json`, `pathlib`, `argparse`, `os`, `sys`, `re`, `shutil`

**scripts/test_run_v4_gates.py** — 36 self-tests (458 lines):
- `TestFindLibDirs` (5 tests): root lib dir, subdirectory lib dirs, package lib dirs, empty dir exclusion, lib→test mapping
- `TestRunMetaTest` (6 tests): covered dir passes, uncovered dir fails, empty test dir fails, subdirectory coverage, subdirectory missing coverage, package lib coverage
- `TestValidatePinFile` (4 tests): valid pin, missing dsh_commit, missing node_version, nonexistent
- `TestValidateCordisConfig` (3 tests): valid cordis, missing policy: ask, nonexistent
- `TestValidateManifestJson` (4 tests): valid manifest, missing field, empty field, nonexistent (skip)
- `TestGateEngineManifest` (4 tests): all present no manifest (skip), all present with valid manifest, missing pin fails, missing cordis fails
- `TestCheckSubcommandParsing` (7 tests): no --check, each --check choice, invalid choice
- `TestIntegrationMetaTest` (3 tests): meta-test exits 0 on codebase, engine-manifest exits 0, negative meta-test exits 1 with temp uncovered dir

### Task 2: .github/workflows/v4-gates.yml

**CI workflow** (46 lines):
- Name: `V4 Gates`
- Triggers: `push` and `pull_request` with path filters for `apps/flutter_app/**`, `engines/**`, `scripts/run_v4_gates.py`, `scripts/test_run_v4_gates.py`, `scripts/build_dsh_release.sh`, `scripts/test_build_dsh_release.sh`, `presets/**`, `.github/workflows/v4-gates.yml`
- Job: `v4-gates` on `ubuntu-latest`
- Steps: checkout → setup Python 3.14 → setup Node.js 24 → install Flutter (stable, `subosito/flutter-action@v2`) → `flutter doctor -v` → `flutter pub get` (in `apps/flutter_app/`) → `python3 scripts/run_v4_gates.py`
- Fails if any gate fails (exit 1)

## Verification Results

| Check | Result |
|-------|--------|
| `python3 -c "import py_compile; py_compile.compile('scripts/run_v4_gates.py', doraise=True)"` | exit 0 — compiles clean |
| `python3 scripts/test_run_v4_gates.py` | 36/36 tests passed (0.124s) |
| `python3 scripts/run_v4_gates.py --check meta-test` | exit 0 — PASS |
| `python3 scripts/run_v4_gates.py --check dart-analyze` | exit 0 — PASS |
| `python3 scripts/run_v4_gates.py --check flutter-test` | exit 0 — PASS (28 tests, 1 skip) |
| `python3 scripts/run_v4_gates.py --check engine-manifest` | exit 0 — SKIP (manifest.json absent) |
| `python3 scripts/run_v4_gates.py --check mock-e2e` | exit 0 — PASS (38 tests) |
| `python3 scripts/run_v4_gates.py` (all gates) | exit 0 — all green |
| `test -f .github/workflows/v4-gates.yml` | pass |
| `grep -q "run_v4_gates.py" .github/workflows/v4-gates.yml` | pass |
| Frozen directories modified | None |

### Full Gate Suite Output

```
======================================================================
V4 Gates Summary
======================================================================
Gate                 Status   Message
----------------------------------------------------------------------
dart-analyze         PASS     No issues found
flutter-test         PASS     All tests passed
engine-manifest      SKIP     Pin + cordis valid; engine-manifest.json not found (build engine first)
mock-e2e             PASS     All mock E2E tests passed
meta-test            PASS     All lib/ directories have test coverage
docx-golden          SKIP     SKIP: docx golden not active until Phase 118
----------------------------------------------------------------------
All V4 gates passed.
```

## TDD Gate Compliance

Task 1 is marked `tdd="true"`. The TDD cycle was followed:

1. **RED** (commit `771f40e`): Created `scripts/test_run_v4_gates.py` with 36 tests. Ran it — failed with `ModuleNotFoundError: No module named 'run_v4_gates'` (exit 1). Committed as `test(112-06): add failing tests for v4 gates runner`.
2. **GREEN** (commit `93cd342`): Created `scripts/run_v4_gates.py` implementing all gates. Ran tests — 36/36 passed (exit 0). Committed as `feat(112-06): implement v4 gates runner`.

Both RED and GREEN gate commits are present in git log.

## Deviations from Plan

### Engine-Manifest Gate Scope (per critical execution notes)

- **Plan's `<action>`**: Gate 3 validates `engine-manifest.json` fields only; skips if file doesn't exist.
- **Critical execution notes**: Engine manifest validation should also check `engines/dsh-pin.txt` (dsh_commit + node_version) and `engines/acp.cordis.yml` (approval.policy: ask).
- **Resolution**: Combined both — the engine-manifest gate validates pin file + cordis config as required checks, plus engine-manifest.json as an optional check (skip if absent). This provides stronger validation in Phase 112 where the manifest JSON doesn't exist yet.

### docx-golden Placeholder Gate (per critical execution notes)

- **Plan**: Lists 5 gates (dart-analyze, flutter-test, engine-manifest, mock-e2e, meta-test).
- **Critical execution notes**: docx golden is NOT in Phase 112 (that's Phase 118); gates runner should have a placeholder/skip.
- **Resolution**: Added `docx-golden` as a 6th gate that always skips in Phase 112. Listed in `--list` output and included in the full run summary table, but not in `--check` choices (no reason to run a placeholder individually). This provides forward compatibility for Phase 118.

## Threat Flags

All three threats from the plan's threat model are mitigated:

- **T-112-19 (Elevation of Privilege — Gate bypass):** MITIGATED — Every gate runs the real command via `subprocess.run` and checks the actual return code. No auto-pass logic. `--check` runs individual gates but the full run (CI default) executes all gates. A gate that cannot find its binary (Flutter/Dart) reports FAIL with a clear message, not a silent pass.

- **T-112-20 (Tampering — Meta-test coverage):** MITIGATED — Meta-test walks the actual filesystem via `os.walk`. It checks for `*_test.dart` files with non-zero content (not just directory existence). An empty test directory or a directory with only empty test files is reported as uncovered. The negative integration test confirms the meta-test catches uncovered dirs.

- **T-112-21 (Denial of Service — Gate runner crash):** MITIGATED — Each gate function is self-contained with try/except-free design that relies on subprocess return codes. Binary-not-found returns a GateResult with `passed=False` rather than crashing. Invalid JSON in manifest is caught with `json.JSONDecodeError` handler. The gate runner itself is covered by 36 self-tests including edge cases.

## Known Stubs

- `gate_docx_golden` is a placeholder that always returns `SKIP` — Phase 118 will implement the real docx golden standard check (model produces JSON change list → portable Python executes track-changes script → output docx compared against golden).
- `engine-manifest.json` validation is a skip-only path in Phase 112 — the manifest is a build artifact produced by `scripts/build_dsh_release.sh` during a real build (Phase 118 真机回归). Once built, the gate will validate all 5 fields.

## Self-Check: PASSED

All created files exist on disk. All commit hashes verified in git log. All verification checks pass. Full gate suite exits 0. No frozen directories modified.
