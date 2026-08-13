---
phase: 112
slug: dsh-engine-integration-acp-over-stdio
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-13
---

# Phase 112 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Synced to actual PLAN.md task structure (plan-checker warning 3 resolved).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Flutter test (Dart) — `flutter test` for unit/widget tests; Python `unittest` for `scripts/run_v4_gates.py` self-tests |
| **Config file** | `apps/flutter_app/pubspec.yaml` (dev_dependencies: flutter_test) — none yet, Wave 0 creates |
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
| 112-01-01 | 01 | 1 | DSH-01 | — | N/A | smoke | `flutter --version` exits 0 | ❌ W0 | ⬜ pending |
| 112-01-02 | 01 | 1 | DSH-01 | — | N/A | unit | `flutter test packages/acp_client/test/acp_client_test.dart` | ❌ W0 | ⬜ pending |
| 112-02-01 | 02 | 2 | DSH-01 | — | Single in-flight rejection (DP-4) | unit | `flutter test packages/acp_client/test/session_new_test.dart` | ❌ W0 | ⬜ pending |
| 112-02-02 | 02 | 2 | DSH-01 | — | N/A | unit | `flutter test packages/acp_client/test/acp_client_test.dart` | ❌ W0 | ⬜ pending |
| 112-03-01 | 03 | 2 | DSH-04 | T-112-01 | Unknown kind → deny | unit | `flutter test packages/acp_client/test/approval_policy_test.dart` | ❌ W0 | ⬜ pending |
| 112-04-01 | 04 | 2 | DSH-02 | — | DSH_HOME points to LOCALAPPDATA | unit | `flutter test test/engine/dsh_config_test.dart` | ❌ W0 | ⬜ pending |
| 112-04-02 | 04 | 2 | DSH-02 | T-112-02 | Zero orphan processes after shutdown | integration | `flutter test test/engine/dsh_process_test.dart` | ❌ W0 | ⬜ pending |
| 112-05-01 | 05 | 3 | DSH-03 | — | sha256 reproducible | smoke | `bash scripts/build_dsh_release.sh --dry-run` exits 0 | ❌ W0 | ⬜ pending |
| 112-05-02 | 05 | 3 | DSH-03 | — | manifest fields complete (dsh_commit/node_version/sha256/built_at) | unit | `bash scripts/test_build_dsh_release.sh` exits 0 | ❌ W0 | ⬜ pending |
| 112-06-01 | 06 | 3 | GATE-01 | — | dart analyze green | smoke | `dart analyze apps/flutter_app/` exits 0 | ❌ W0 | ⬜ pending |
| 112-06-02 | 06 | 3 | GATE-02 | — | meta-test: every lib/ dir has tests | unit | `python3 scripts/run_v4_gates.py --check meta-test` exits 0 | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Install Flutter SDK (≥3.19 stable) — blocking, no Flutter on this machine
- [ ] `apps/flutter_app/` — `flutter create --platforms=windows` scaffold
- [ ] `apps/flutter_app/packages/acp_client/` — Dart package skeleton (`dart create`)
- [ ] `apps/flutter_app/packages/acp_client/test/` — test directory with mock ACP server fixtures
- [ ] `apps/flutter_app/test/engine/` — test directory for subprocess manager
- [ ] `scripts/run_v4_gates.py` — gates runner skeleton with `--check` subcommands
- [ ] `engines/dsh-pin.txt` — pin file with commit `47f943859b` + node version
- [ ] `engines/acp.cordis.yml` — ACP composition with terminal-default-deny approval stack

*Existing infrastructure does NOT cover phase requirements — everything is greenfield (no Flutter project exists).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| V1-V5 live evidence | DSH-01..04 | Already closed in RESEARCH.md with live DSH tests | See `112-RESEARCH.md` § V1-V5 Verification Evidence — CLOSED, no manual re-verification needed |
| Windows zero-orphan assertion | DSH-02 | Windows process tree kill behavior cannot be verified on WSL/Linux CI | Run `flutter test test/engine/dsh_process_test.dart` on a real Windows machine post-build; record PID assertions |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
