---
phase: 112
slug: dsh-engine-integration-acp-over-stdio
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-13
validated: 2026-08-14
---

# Phase 112 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Synced to actual PLAN.md task structure (plan-checker warning 3 resolved).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Flutter test (Dart) — `flutter test` for unit/widget tests; Python `unittest` for `scripts/run_v4_gates.py` self-tests |
| **Config file** | `apps/flutter_app/pubspec.yaml` (dev_dependencies: flutter_test) |
| **Quick run command** | `flutter test` (from `apps/flutter_app/`) |
| **Full suite command** | `scripts/run_v4_gates.py` (dart analyze + flutter test + engine manifest + mock E2E + meta-test) |
| **Estimated runtime** | ~30-60 seconds (Flutter unit tests + gates runner) |

---

## Sampling Rate

- **After every task commit:** Run `flutter test` (from `apps/flutter_app/`)
- **After every plan wave:** Run `scripts/run_v4_gates.py`
- **Before `/gsd-verify-work`:** Full v4 gates must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 112-01-01 | 01 | 1 | DSH-01 | — | N/A | smoke | `flutter --version` exits 0 | ✅ | ✅ green |
| 112-01-02 | 01 | 1 | DSH-01 | — | N/A | unit | `flutter test packages/acp_client/test/acp_client_test.dart` | ✅ | ✅ green |
| 112-02-01 | 02 | 2 | DSH-01 | — | Single in-flight rejection (DP-4) | unit | `flutter test packages/acp_client/test/session_new_test.dart` | ✅ | ✅ green |
| 112-02-02 | 02 | 2 | DSH-01 | — | N/A | unit | `flutter test packages/acp_client/test/acp_client_test.dart` | ✅ | ✅ green |
| 112-03-01 | 03 | 2 | DSH-04 | T-112-01 | Unknown kind → deny | unit | `flutter test packages/acp_client/test/approval_policy_test.dart` | ✅ | ✅ green |
| 112-04-01 | 04 | 2 | DSH-02 | — | DSH_HOME points to LOCALAPPDATA | unit | `flutter test test/engine/dsh_config_test.dart` | ✅ | ✅ green |
| 112-04-02 | 04 | 2 | DSH-02 | T-112-02 | Zero orphan processes after shutdown | integration | `flutter test test/engine/dsh_process_test.dart` | ✅ | ✅ green |
| 112-05-01 | 05 | 3 | DSH-03 | — | sha256 reproducible | smoke | `bash scripts/build_dsh_release.sh --dry-run` exits 0 | ✅ | ✅ green |
| 112-05-02 | 05 | 3 | DSH-03 | — | manifest fields complete (dsh_commit/node_version/sha256/built_at) | unit | `bash scripts/test_build_dsh_release.sh` exits 0 | ✅ | ✅ green |
| 112-06-01 | 06 | 3 | GATE-01 | — | dart analyze green | smoke | `dart analyze apps/flutter_app/` exits 0 | ✅ | ✅ green |
| 112-06-02 | 06 | 3 | GATE-02 | — | meta-test: every lib/ dir has tests | unit | `python3 scripts/run_v4_gates.py --check meta-test` exits 0 | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Install Flutter SDK (≥3.19 stable) — Flutter 3.47.0 at `/home/sorawatcher/flutter/bin/flutter`
- [x] `apps/flutter_app/` — `flutter create --platforms=windows` scaffold
- [x] `apps/flutter_app/packages/acp_client/` — Dart package skeleton (`dart create`)
- [x] `apps/flutter_app/packages/acp_client/test/` — test directory with mock ACP server fixtures
- [x] `apps/flutter_app/test/engine/` — test directory for subprocess manager
- [x] `scripts/run_v4_gates.py` — gates runner skeleton with `--check` subcommands
- [x] `engines/dsh-pin.txt` — pin file with commit `47f943859b` + node version
- [x] `engines/acp.cordis.yml` — ACP composition with terminal-default-deny approval stack

*All Wave 0 requirements satisfied during Phase 112 execution.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Status |
|----------|-------------|------------|-------------------|--------|
| V1-V5 live evidence | DSH-01..04 | Already closed in RESEARCH.md with live DSH tests | See `112-RESEARCH.md` § V1-V5 Verification Evidence — CLOSED, no manual re-verification needed | ✅ CLOSED |
| Windows zero-orphan assertion | DSH-02 | Windows process tree kill behavior cannot be verified on WSL/Linux CI | Run `flutter test test/engine/dsh_process_test.dart` on a real Windows machine post-build; record PID assertions | ⬜ deferred to Phase 119 Windows packaging |
| Code review remediation | All | CR-01/CR-02/WR-01..WR-06 fixed in commit d2f7b64; wire_boundary_test.dart covers CR-01/CR-02/WR-02/WR-03 | See `112-REVIEW.md` § Remediation | ✅ clean |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated (2026-08-14)

**V4 gates final run (post-remediation):**
- dart-analyze: PASS
- flutter-test: PASS (52 tests, including 7 new wire-boundary tests)
- engine-manifest: SKIP (no manifest built — engine build is Phase 119)
- mock-e2e: PASS
- meta-test: PASS
- docx-golden: SKIP (active from Phase 118)

**Phase 112 technical risk gate: PASSED.** V1-V5 all CLOSED with live evidence
from the DSH repo. No falsification, no rollback trigger (PRD §12.1 RB1/RB2
not invoked). Phase 112 is cleared to transition; Phase 113 may begin.
