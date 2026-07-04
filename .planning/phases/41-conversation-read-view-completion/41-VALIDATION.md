---
phase: 41
slug: conversation-read-view-completion
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-04
---

# Phase 41 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | unittest (existing — `services/conversation-read-view/tests/`) |
| **Config file** | `services/conversation-read-view/pyproject.toml` (exists, `dependencies = []`) |
| **Quick run command** | `PYTHONPATH=services/conversation-read-view/src:packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src:services/feedback-service/src python -m unittest discover -s services/conversation-read-view/tests` |
| **Full suite command** | `python scripts/run_v2_gates.py` |
| **Estimated runtime** | ~60 seconds (13 gates; no new gate added in Phase 41) |

---

## Sampling Rate

- **After every task commit:** Run quick command (conversation-read-view tests only)
- **After every plan wave:** Run `python scripts/run_v2_gates.py` (all 13 gates)
- **Before `/gsd-verify-work`:** Full suite must be green (all 13 gates)
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 41-01-01 | 41-01 | 1 | READVIEW-01 | unbounded-scan | `pagination.py` clamps `limit` to `MAX_RESULT_LIMIT` (default 100); env override `CONVERSATION_READ_VIEW_MAX_LIMIT` clamped to `[10,1000]` | unit | quick | no | pending |
| 41-01-02 | 41-01 | 1 | READVIEW-01 | pagination-drift | Opaque base64url cursor encodes last sort key; `next_cursor` is null when no more results; same cursor replays same page boundary | unit | quick | no | pending |
| 41-01-03 | 41-01 | 1 | READVIEW-01 | filter-bypass | `/conversations` and `/tasks` list endpoints apply `from`/`to` (ISO-8601, inclusive), `user_id`, `channel`, `status` filters with AND semantics; unknown filter → 400 | unit | quick | no | pending |
| 41-01-04 | 41-01 | 1 | READVIEW-01 | shape-regression | New list response shape (`items`, `count`, `next_cursor`, `has_more`, `metadata`) does NOT alter existing `/conversations/{id}` or `/tasks/{id}` shapes | unit | quick | no | pending |
| 41-02-01 | 41-02 | 2 | READVIEW-02 | trace-incomplete | `/traces/{trace_id}` returns all 5 event types (AgentTurn, RouteDecision, ExecutionTrace, AgentResult, FeedbackEvent) in `(occurred_at, seq)` order; `reconstruction_complete=True` when ExecutionTrace present | unit | quick | no | pending |
| 41-02-02 | 41-02 | 2 | READVIEW-02 | trace-missing | Unknown `trace_id` → 404 `not_found`; partial trace (turn_id fallback only) → `reconstruction_complete=False` | unit | quick | no | pending |
| 41-02-03 | 41-02 | 2 | READVIEW-03 | export-leak | `/export?format=json` returns scrubbed items; `/export?format=csv` uses stdlib `csv` with flat projection; unknown `resource`/`format` → 400 | unit | quick | no | pending |
| 41-03-01 | 41-03 | 3 | READVIEW-03 | privacy-scrub-gap | All 4 new endpoints (`/conversations`, `/tasks`, `/traces/{trace_id}`, `/export`) raise `ValueError` when response contains any `ALL_FORBIDDEN_KEYS` key | unit | quick | no | pending |
| 41-03-02 | 41-03 | 3 | READVIEW-01/02/03 | backward-compat | `test_backward_compat.py` snapshots top-level keys of existing `/conversations/{id}`, `/tasks/{id}`, `/feedback` responses and asserts unchanged | unit | quick | no | pending |
| 41-03-03 | 41-03 | 3 | SAFETY-02/06 | contract-drift | `python scripts/run_v2_gates.py` exits 0 (13 gates); `test_contract_count_freeze.py` green; no edits to `platform-contract/` or `protocols.py` | gate | full | yes | pending |

---

## Wave Gates

| Wave | Plans | Gate | Entry Condition | Exit Condition |
|------|-------|------|-----------------|----------------|
| 1 | 41-01 | conversation-read-view | Phase 40 complete (13 gates green) | All Wave 1 tests green; existing tests unchanged; full suite green |
| 2 | 41-02 | conversation-read-view | Wave 1 complete | Trace reconstruction + export tests green; full suite green |
| 3 | 41-03 | conversation-read-view + contract-test-suite | Wave 2 complete | Privacy scrub on new endpoints; backward-compat snapshot; full 13-gate suite green; contract freeze verified |

---

## Acceptance Criteria Traceability

| Success Criterion | Verified By |
|-------------------|-------------|
| SC1: cursor pagination + time-range/dimension filters + max limits | Tasks 41-01-01, 41-01-02, 41-01-03, 41-01-04 |
| SC2: trace reconstruction by trace_id in occurrence order | Tasks 41-02-01, 41-02-02 |
| SC3: CSV/JSON export + read-time privacy scrubbing on new endpoints | Tasks 41-02-03, 41-03-01 |
| SC4: backward-compat tests proving existing shapes unchanged | Task 41-03-02 (+ 41-01-04) |

---

## Privacy Scan Coverage

- New fixtures (if any) added under `packages/contract-test-suite/fixtures/` are covered by `default_privacy_data_paths()` in `contract_test_suite.privacy_scan`.
- The `phase7-privacy-boundary` gate runs `test_privacy_gates.py` which asserts `default_privacy_data_paths()` is clean — any new fixture must be reference-first and secret-free.
- New endpoint scrub behavior is unit-tested in `test_privacy_scrub.py` (Wave 3 extension).
