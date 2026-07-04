---
phase: 42
slug: admin-console-api
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-04
---

# Phase 42 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | unittest (existing — `services/admin-console-api/tests/`) |
| **Config file** | `services/admin-console-api/pyproject.toml` (new, `dependencies = []`) |
| **Quick run command** | `PYTHONPATH=services/admin-console-api/src:services/conversation-read-view/src:packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src:services/feedback-service/src python -m unittest discover -s services/admin-console-api/tests` |
| **Full suite command** | `python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~70 seconds (14 gates after Wave 3 adds the admin-console-api gate) |

---

## Sampling Rate

- **After every task commit:** Run quick command (admin-console-api tests only)
- **After every plan wave:** Run `python scripts/run_v2_gates.py` (all gates)
- **Before `/gsd-verify-work`:** Full suite must be green (all 14 gates after Wave 3)
- **Max feedback latency:** 70 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 42-01-01 | 42-01 | 1 | ADMIN-01 | service-structure | `services/admin-console-api/` created with `pyproject.toml` (`dependencies = []`), `src/admin_console_api/__init__.py`, `README.md`; package imports cleanly | unit | quick | no | pending |
| 42-01-02 | 42-01 | 1 | ADMIN-01 | auth-bypass | `auth.py` resolves `ADMIN_API_TOKEN` from env; empty/missing token → all requests refused 403; `hmac.compare_digest` used for constant-time comparison | unit | quick | no | pending |
| 42-01-03 | 42-01 | 1 | ADMIN-01 | unauthorized-access | `handle_admin_get` returns 401 for missing/invalid `Authorization` header; returns 403 when token not configured; valid `Bearer` token passes auth gate | unit | quick | no | pending |
| 42-01-04 | 42-01 | 1 | ADMIN-01 | data-view-filter | `/sessions` list delegates to `list_conversations()` with `from`/`to`/`user_id`/`channel` filters + cursor pagination; `/tasks` list delegates to `list_tasks()` with `from`/`to`/`user_id`/`channel`/`status` filters; unknown filter → 400 | unit | quick | no | pending |
| 42-01-05 | 42-01 | 1 | ADMIN-01 | pagination-drift | List endpoints reuse `slice_page`/`encode_cursor`/`decode_cursor` from `conversation_read_view.pagination`; `next_cursor` is null when no more results; `ADMIN_API_MAX_LIMIT` env clamped to `[10, 1000]` | unit | quick | no | pending |
| 42-01-06 | 42-01 | 1 | ADMIN-01 | privacy-scrub | All data views (sessions, tasks, feedback) route responses through `scrub_contract_payload`; forbidden keys raise `ValueError` | unit | quick | no | pending |
| 42-01-07 | 42-01 | 1 | ADMIN-01 | read-only-violation | No POST/PUT/DELETE handlers exist; `handle_admin_get` is the only entry point; no mutation methods on any module | unit | quick | no | pending |
| 42-02-01 | 42-02 | 2 | ADMIN-02 | secret-leak | `health.py` defines `HEALTH_ALLOWED_FIELDS` allowlist; `project_health()` excludes `secret_refs_configured`, `api_base_url`, config paths, secret reference names; only `secrets_configured: bool` exposed | unit | quick | no | pending |
| 42-02-02 | 42-02 | 2 | ADMIN-02 | allowlist-bypass | `project_health()` on a raw dict containing `secret_refs_configured` map and `api_base_url` returns only allowlisted fields; `secrets_configured` boolean is preserved | unit | quick | no | pending |
| 42-02-03 | 42-02 | 2 | SC3 | gate-import-coupling | `gates.py` runs `run_v2_gates.py --json-summary` via `subprocess.run`; no import of gate internals; parsed JSON summary returned with `passed`, `gate_count`, `gates` list | unit | quick | no | pending |
| 42-02-04 | 42-02 | 2 | SC3 | gate-timeout | `run_gate_summary()` has `timeout=300` (5 min); subprocess `capture_output=True`; raw stdout/stderr not exposed in API response | unit | quick | no | pending |
| 42-02-05 | 42-02 | 2 | ADMIN-02 | health-route | `/health` endpoint returns 200 with allowlisted fields only; `/gates` endpoint returns 200 with gate summary from subprocess | unit | quick | no | pending |
| 42-03-01 | 42-03 | 3 | SC3 | flag-default-off | `handle_admin_get` with default `RuntimeFeatureFlags()` (all False) returns 403 `admin_api_disabled` even with valid token; `admin_api_enabled=True` allows routing | unit | quick | no | pending |
| 42-03-02 | 42-03 | 3 | SC3 | flag-gate-wiring | `handle_admin_get` calls `feature_flags.require_enabled("admin_api_enabled")` before auth check; `RuntimeFeatureDisabledError` caught and returned as 403 | unit | quick | no | pending |
| 42-03-03 | 42-03 | 3 | GATE-01 | gate-registration | `scripts/run_v2_gates.py` includes `admin-console-api` gate with correct PYTHONPATH; `compileall` gate includes `services/admin-console-api/src` | gate | full | yes | pending |
| 42-03-04 | 42-03 | 3 | SAFETY-02/06 | contract-drift | `python scripts/run_v2_gates.py` exits 0 (14 gates); `test_contract_count_freeze.py` green; no edits to `platform-contract/` or `protocols.py` or `feature_flags.py` | gate | full | yes | pending |

---

## Wave Gates

| Wave | Plans | Gate | Entry Condition | Exit Condition |
|------|-------|------|-----------------|----------------|
| 1 | 42-01 | admin-console-api (new) | Phase 41 complete (13 gates green) | All Wave 1 tests green; service structure + auth + data views working; full suite green (13 gates — new gate not yet registered) |
| 2 | 42-02 | admin-console-api (new) | Wave 1 complete | Health/status allowlist tests green; gate subprocess tests green; full suite green (13 gates) |
| 3 | 42-03 | admin-console-api + contract-test-suite | Wave 2 complete | Feature flag default-off verified; new gate registered in `run_v2_gates.py`; full 14-gate suite green; contract freeze verified |

---

## Acceptance Criteria Traceability

| Success Criterion | Verified By |
|-------------------|-------------|
| SC1: Authenticate via static token + query sessions/tasks/feedback/gates/health with filtering and pagination, read-only | Tasks 42-01-01, 42-01-02, 42-01-03, 42-01-04, 42-01-05, 42-01-06, 42-01-07, 42-02-05 |
| SC2: Health/status views use field allowlist excluding secret refs, config paths, `secret_refs_configured`, `api_base_url` — only `secrets_configured: true/false` | Tasks 42-02-01, 42-02-02, 42-02-05 |
| SC3: `admin_api_enabled` defaults False + gate status via subprocess `run_v2_gates.py --json-summary` without importing gate internals | Tasks 42-02-03, 42-02-04, 42-03-01, 42-03-02 |

---

## Privacy Scan Coverage

- No new fixtures are created under `packages/contract-test-suite/fixtures/` — the Admin Console API reuses existing Phase 5 fixtures for data view tests.
- Plan files (`.planning/phases/42-admin-console-api/*.md`) use `REDACTED` or short placeholders (< 12 chars) for any token-like values — the privacy scanner scans these paths.
- The `phase7-privacy-boundary` gate runs `test_privacy_gates.py` which asserts `default_privacy_data_paths()` is clean — no new fixture paths are added.
- Health/status view allowlist tests use synthetic dicts (not fixtures) with field names like `secret_refs_configured` and `api_base_url` — these are field names, not secret values, and appear only in test code (not in `.planning/` plan files).

---

## Contract Freeze Verification

| Artifact | Action | Verification |
|----------|--------|--------------|
| `packages/platform-contract/` | No modification | `test_contract_count_freeze.py` green; `git diff` shows no changes |
| `packages/platform-runtime/protocols.py` | No modification | `test_contract_count_freeze.py` green; `git diff` shows no changes |
| `packages/platform-runtime/src/platform_runtime/feature_flags.py` | No modification | `admin_api_enabled` already exists from Phase 36; `git diff` shows no changes |
| `scripts/run_v2_gates.py` | Modified in Wave 3 only (add gate entry) | Gate count increases 13 → 14; all existing gates still pass |
