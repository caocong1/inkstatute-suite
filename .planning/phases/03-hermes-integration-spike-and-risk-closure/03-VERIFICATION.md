---
phase: 03-hermes-integration-spike-and-risk-closure
verified: 2026-06-28T01:42:55Z
status: passed
score: "13/13 must-haves verified"
overrides_applied: 0
deferred:
  - truth: "Template-card callback payload field names and feedback.jsonl row shape"
    addressed_in: "Phase 5 and Phase 6"
    evidence: "03-IDENTIFIER-STATE-PRIVACY-RULES.md defines association/idempotency rules and requires sanitized runtime samples before feedback-service implementation."
  - truth: "Full long-task runtime signal source for every AsyncTaskState value"
    addressed_in: "Phase 4 and Phase 5"
    evidence: "03-IDENTIFIER-STATE-PRIVACY-RULES.md defines exact enum mapping and requires real Hermes source/log evidence before mapper claims unavailable states."
  - truth: "Full outbound response capture beyond the capped agent:end hook context"
    addressed_in: "Phase 4"
    evidence: "03-HOOK-AND-TURN-DECISIONS.md records the 500-character agent:end response cap and requires a full-response source before claiming complete capture."
  - truth: "Raw payload storage owner, retention duration, and redaction enforcement"
    addressed_in: "Phase 4 and Phase 7"
    evidence: "03-IDENTIFIER-STATE-PRIVACY-RULES.md sets reference-first policy and blocks contract logs from becoming raw payload storage."
---

# Phase 3: Hermes Integration Spike and Risk Closure Verification Report

**Phase Goal:** Production Hermes hook work is unblocked by documented, tested decisions for V2's known integration risks.
**Verified:** 2026-06-28T01:42:55Z
**Status:** passed
**Re-verification:** Yes - after Plan 03-02 hook-order evidence closure and Plan 03-04 fixture/test completion

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | All four Phase 3 plans have completion summaries. | VERIFIED | `03-01-SUMMARY.md`, `03-02-SUMMARY.md`, `03-03-SUMMARY.md`, and `03-04-SUMMARY.md` exist; roadmap marks 4/4 plans complete. |
| 2 | Hermes hook ordering is confirmed enough to decide whether a recorder can run after `response_filter`. | VERIFIED | `03-HOOK-ORDER-EVIDENCE.md` contains `EVIDENCE_OUTCOME: source_confirmed` and `HOOK_ORDER_DECISION: can_run_after_response_filter`; the blocking gap marker is absent. |
| 3 | The after-filter recorder rule is operationally constrained, not hand-waved. | VERIFIED | Decision docs state same-event order is lexicographic hook directory order; `contract_result_recorder/` sorts before `response_filter`, so Phase 4 must use a directory sorted after `response_filter` or an inline/adjacent fallback. |
| 4 | AgentTurn input strategy is chosen with explicit reverse-inference limits. | VERIFIED | `03-HOOK-AND-TURN-DECISIONS.md` prefers source-confirmed `agent:start` fields and limits `agent:end` reverse inference to stable identifiers/capped message context. |
| 5 | AgentTurn field coverage is status-tagged. | VERIFIED | The field table marks `conversation_id`, `channel`, `user_id`, and capped `content` as source-confirmed or partial, while `turn_id`, `message_type`, `attachments`, `received_at`, and raw payload references remain source/runtime gated. |
| 6 | Message, feedback target, template card, callback, and feedback row association rules are traceable. | VERIFIED | `03-IDENTIFIER-STATE-PRIVACY-RULES.md` defines the contract-side graph and Hermes-side candidates: `message_id`, `pending_previews.jsonl`, `template_card_id`, `callback_event_id`, and `feedback.jsonl`. |
| 7 | Async task states map only to the platform vocabulary. | VERIFIED | The rules doc lists exact enum values `queued`, `running`, `waiting_for_user`, `succeeded`, `failed`, and `cancelled`, and forbids aliases such as `pending`, `processing`, `done`, `error`, or `canceled`. |
| 8 | Feedback idempotency and legal safety rules are explicit. | VERIFIED | The idempotency ladder uses native callback id if available, then `feedback_target + action + user_id + created_at_bucket`, then payload fingerprint metadata by reference; skill candidates require human review and must not auto-modify legal skills. |
| 9 | Raw payload references, retention assumptions, and redaction minimums are defined. | VERIFIED | The rules doc defines `raw_payload_ref` namespaces, runtime-owned storage assumptions, and forbidden inline data classes including raw legal text, full callback payloads, secrets, complete ID numbers, phone numbers, bank accounts, and addresses. |
| 10 | Non-happy-path fixtures exist for all Phase 3 required cases. | VERIFIED | Four fixtures cover route error, long-task failure, repeated feedback clicks, and a non-legal wild/simple-QA task under `packages/contract-test-suite/fixtures/`. |
| 11 | Phase 3 fixtures validate and preserve relationships through the existing contract-test-suite harness. | VERIFIED | Full suite passed 28 tests; targeted replay checked 4 Phase 3 fixtures and 52 relationship checks with zero broken relationships. |
| 12 | Code review found no Phase 3 fixture/test quality, security, or privacy issues. | VERIFIED | `03-REVIEW.md` reports `status: clean`, 6 files reviewed, and 0 findings. |
| 13 | Phase 3 stayed within spike scope. | VERIFIED | Review and diff checks found no production Hermes hooks, services, queues, databases, `.github` workflows, WeCom gateway changes, or automatic legal skill modification code. |

**Score:** 13/13 truths verified

### Deferred Items

Items not yet runtime-proven but explicitly assigned to later implementation or validation phases.

| # | Item | Addressed In | Evidence |
|---|---|---|---|
| 1 | Sanitized template-card callback payload fields and `feedback.jsonl` row shape | Phase 5 / Phase 6 | Phase 3 defines association and idempotency rules, but Phase 5/6 own real callback/feedback normalization. |
| 2 | Full long-task runtime signal source for each async state | Phase 4 / Phase 5 | Phase 3 defines exact state mapping and unavailable-state behavior; Phase 4/5 own real Hermes mapper/runtime evidence. |
| 3 | Full outbound response capture beyond capped `agent:end` context | Phase 4 | Phase 3 source evidence explicitly records the 500-character hook context cap. |
| 4 | Raw payload storage owner, retention duration, and redaction enforcement | Phase 4 / Phase 7 | Phase 3 establishes reference-first policy and privacy boundaries; implementation/enforcement belongs to hook writer and CI/privacy gates. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `03-HERMES-SOURCE-INVENTORY.md` | Source/runtime evidence ledger | VERIFIED | Exists and records repo-local evidence gaps plus later-mounted Hermes source implications. |
| `03-INTEGRATION-RISK-MATRIX.md` | PRD section 13 risk matrix | VERIFIED | Exists and maps hook ordering, inbound turn, message id, long-task state, idempotency, raw payload, redaction, fixtures, and skill candidate safety risks. |
| `03-HOOK-ORDER-EVIDENCE.md` | Blocking hook-order evidence gate | VERIFIED | Source-confirmed and contains a concrete hook-order decision. |
| `03-HOOK-AND-TURN-DECISIONS.md` | Hook ordering and AgentTurn input strategy | VERIFIED | Cites the evidence gate and records Phase 4 constraints. |
| `03-IDENTIFIER-STATE-PRIVACY-RULES.md` | Identifier, idempotency, async state, raw payload, retention, redaction, and safety rules | VERIFIED | Contains status-tagged tables and downstream gates. |
| `03-REVIEW.md` | Phase code review | VERIFIED | Clean review of 6 source/test fixture files. |
| Phase 3 fixture JSON files | Route error, long-task failure, repeated feedback clicks, non-legal task | VERIFIED | Four schema-valid fixtures exist in `packages/contract-test-suite/fixtures/`. |
| `test_phase3_non_happy_paths.py` | Focused fixture behavior tests | VERIFIED | Seven focused tests pass. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Risk evidence scan | `rg -n "response_filter|template_card|wecom_template_card_shim|message_id|feedback|long_task|agent:end" -S .` | 258 matches captured for review | PASS |
| Hook-order gate | Python assertion over `03-HOOK-ORDER-EVIDENCE.md` and `03-HOOK-AND-TURN-DECISIONS.md` | `03-02 hook order gate OK` | PASS |
| Identifier/privacy rules | Python assertion over required association, idempotency, raw payload, redaction, and safety terms | `03-03 identifier/privacy rules OK` | PASS |
| Fixture relationship replay | Python replay over four Phase 3 fixtures | `4 fixtures, 52 checks`, 0 broken | PASS |
| Full contract suite | `python -m compileall ... && cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py` | Ran 28 tests, OK | PASS |
| Phase review | `03-REVIEW.md` | 0 findings | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| REQ-implementation-risk-resolution | 03-01, 03-02, 03-03, 03-04 | Resolve Hermes hook order, inbound turn strategy, message id stability boundaries, long-task states, feedback targets, idempotency, raw payload retention/redaction, non-happy-path fixtures, and skill-candidate safety before production hook work. | SATISFIED FOR PHASE 3 | Hook order is source-confirmed; AgentTurn strategy and reverse-inference limits are documented; identifier/state/privacy/safety rules are status-tagged; non-happy-path fixtures validate through the contract-test-suite. Runtime-only payload samples and storage policies are downstream gates, not Phase 3 blockers. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| None | - | No production Hermes hook/service/database/queue/CI files were added. | INFO | Phase 3 stayed within spike, docs, fixtures, and tests. |
| None | - | No exact `raw_payload` keys, boundary-matched secret-like strings, TODO/FIXME/debug markers, or forbidden top-level legal fields were found in reviewed Phase 3 fixture/test scope. | INFO | Privacy and maintainability scans passed. |

### Human Verification Required

None for Phase 3. Real lawyer trial acceptance remains Phase 8. Real callback samples, long-task runtime logs, and storage/retention policy confirmation are downstream implementation gates for Phases 4-7.

### Gaps Summary

No blocking Phase 3 gaps remain. The prior hook-order blocker is closed by source-confirmed Hermes hook loader/order evidence and a sanitized probe. Remaining source/runtime-only details are documented as explicit Phase 4/5/6/7 gates rather than hidden assumptions.

### Disconfirmation Pass

- Checked whether a canonical `contract_result_recorder/` hook directory can run after `response_filter`; it cannot. The verified implementation rule requires a directory sorted after `response_filter`.
- Checked whether `agent:end` can be treated as full outbound response capture; it cannot because gateway source caps the response in hook context.
- Checked whether repeated feedback clicks create multiple contract feedback records; the fixture models one canonical `FeedbackEvent` with idempotency metadata.
- Checked whether legal-specific data leaked into platform top-level fixture fields; focused tests and scans passed.

---

_Verified: 2026-06-28T01:42:55Z_
_Verifier: the agent (inline gsd-verifier fallback)_
