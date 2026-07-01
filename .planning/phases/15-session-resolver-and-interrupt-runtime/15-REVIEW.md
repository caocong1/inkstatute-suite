---
phase: 15-session-resolver-and-interrupt-runtime
reviewed: 2026-07-01T04:24:20Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - services/wecom-service/src/wecom_service/session_runtime.py
  - services/wecom-service/src/wecom_service/__init__.py
  - services/wecom-service/tests/test_session_interrupt_runtime.py
  - packages/contract-test-suite/fixtures/phase15_session_interrupt_runtime.json
  - packages/contract-test-suite/tests/test_phase15_session_interrupt_runtime.py
  - packages/contract-test-suite/tests/test_schema_validation.py
findings:
  critical: 3
  warning: 4
  info: 0
  total: 7
status: issues_found
---

# Phase 15: Code Review Report

**Reviewed:** 2026-07-01T04:24:20Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the WeCom session runtime, package exports, Phase 15 runtime tests, contract fixture, and schema-validation coverage. The runtime implements the intended high-level branches, but it does not defensively bind a normalized turn/run request to the supplied session scope, keeps duplicate-answer protection only in process memory, and lets historical cancelled/expired interrupts suppress normal session resolution indefinitely. The tests pass in the monorepo layout, but they do not cover these edge cases and one fixture carries inconsistent privacy evidence.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Missing Turn/Scope Validation Allows Cross-User Interrupt Resume

**Classification:** BLOCKER
**File:** `services/wecom-service/src/wecom_service/session_runtime.py:121`
**Issue:** `handle_turn` accepts `turn`, `scope`, and `run_request` independently, then looks up a pending interrupt solely by the caller-supplied `scope`. It never verifies that `turn.user_id`, `turn.conversation_id`, `turn.channel`, metadata `thread_id`, or the `run_request` tenant/workspace/bot/session belong to that same scope. If an upstream bug or replay supplies user A's normalized turn with user B's scope, user A's answer text can resume user B's pending interrupt, violating the Phase 15 scope isolation contract.
**Fix:**
```python
def _validate_turn_scope(*, turn: Any, scope: SessionScope, run_request: RunRequest) -> None:
    if str(getattr(turn, "user_id", "")) != scope.user_id:
        raise ValueError("turn user_id does not match session scope")
    if str(getattr(turn, "conversation_id", "")) != scope.conversation_id:
        raise ValueError("turn conversation_id does not match session scope")
    metadata = getattr(turn, "metadata", {}) or {}
    if scope.thread_id and isinstance(metadata, Mapping) and metadata.get("thread_id") != scope.thread_id:
        raise ValueError("turn thread_id does not match session scope")
    if run_request.tenant_id != scope.tenant_id or run_request.workspace_id != scope.workspace_id:
        raise ValueError("run_request tenant/workspace does not match session scope")
    if run_request.bot_instance_id != scope.bot_instance_id:
        raise ValueError("run_request bot_instance_id does not match session scope")
```
Call this before `_pending_record_for_scope`, and add a negative test where a pending interrupt for another user cannot be resumed with the current user's `AgentTurn`.

### CR-02: Duplicate Answer Idempotency Is Process-Local And Fails After Restart

**Classification:** BLOCKER
**File:** `services/wecom-service/src/wecom_service/session_runtime.py:112`
**Issue:** Duplicate suppression depends on `_outcome_by_idempotency_key`, a per-instance dictionary populated only after a successful resume. If the WeCom callback is retried after a process restart, worker switch, or helper re-instantiation, the cache is empty; because resolved interrupts are no longer pending and `_latest_inactive_record_for_scope` ignores `resolved`, the same answer is resolved as a new session turn instead of `duplicate_answer_ignored`. The underlying interrupt store has resolved-idempotency metadata, but this runtime path never consults it.
**Fix:**
```python
duplicate_record = _resolved_duplicate_record_for_scope(
    self.interrupt_store,
    scope,
    turn_id=turn_id,
    idempotency_key=idempotency_key,
)
if duplicate_record is not None:
    decision = _resolve_decision(
        scope=scope,
        text=turn_text,
        raw_payload_ref=raw_payload_ref,
        recent_session=recent_session,
        pending_interrupt=None,
        active_task=None,
        policy=self.policy,
        now=current,
        id_factory=self.id_factory,
        metadata=metadata,
    )
    return WeComSessionRuntimeOutcome(
        action=WeComSessionRuntimeAction.DUPLICATE_ANSWER_IGNORED,
        decision=decision,
        evidence=_base_evidence(decision) | {
            "duplicate": True,
            "resume_attempted": False,
            "runtime_resume_called": False,
        },
    )
```
Back this with a test that creates one helper to resolve the interrupt, then creates a fresh helper with the same `interrupt_store` and same idempotency key.

### CR-03: Historical Cancelled/Expired Interrupts Shadow Future Turns Forever

**Classification:** BLOCKER
**File:** `services/wecom-service/src/wecom_service/session_runtime.py:161`
**Issue:** When there is no pending interrupt, any latest cancelled or expired record for the scope forces `INTERRUPT_CANCELLED` or `INTERRUPT_EXPIRED` and bypasses active-task and recent-session resolution. Because `_latest_inactive_record_for_scope` scans all stored records without checking the current turn, idempotency key, or a recency window, every later user message in that scope will keep being classified as the old inactive interrupt instead of starting or continuing a session.
**Fix:** Remove the broad inactive-record preemption. Only report an inactive interrupt when it is tied to the current callback/idempotency key, or after an explicit pending-interrupt expiry check for the current turn. Otherwise fall through to normal `_resolve_decision` with active task and recent session context.

## Warnings

### WR-01: Duplicate Evidence Reuses The Original Resume Evidence

**Classification:** WARNING
**File:** `services/wecom-service/src/wecom_service/session_runtime.py:114`
**Issue:** The duplicate branch returns `replace(prior, action=DUPLICATE_ANSWER_IGNORED, evidence={**prior.evidence, ...})`, so duplicate events retain the original resume evidence, including `resume_attempted: True`, `runtime_resume_called: True`, and `resumed_run_id`. That makes audit output claim the duplicate was submitted to the backend even when the code suppressed it.
**Fix:** Build duplicate evidence from `_base_evidence(prior.decision)` and explicitly set `resume_attempted: False`, `runtime_resume_called: False`, `duplicate: True`, and `duplicate_backend_submit_count: 1`.

### WR-02: Phase 15 Fixture Hash/Length Evidence Does Not Match Stored Content

**Classification:** WARNING
**File:** `packages/contract-test-suite/fixtures/phase15_session_interrupt_runtime.json:77`
**Issue:** The fixture stores `content: "Synthetic clarification response."`, but its `content_sha256_16`/`text_sha256_16` values and `content_length`/`text_length` fields do not match that string. This weakens the privacy-safe evidence contract because downstream checks may trust hashes and lengths as the only stand-ins for suppressed answer text.
**Fix:** Either remove full answer content from the fixture and represent it only by refs/hashes/lengths, or update all hashes and lengths from the actual string. Add a test that recomputes `sha256[:16]` and `len()` for any fixture field that carries both content and privacy evidence.

### WR-03: Forbidden Command Regex Misses Embedded Slash Commands

**Classification:** WARNING
**File:** `packages/contract-test-suite/tests/test_phase15_session_interrupt_runtime.py:36`
**Issue:** The raw regex `r"(^|\\s)/(new|resume|help|status|debug|memory)\b"` matches a literal backslash-s, not whitespace. It catches `/help` at the beginning of a string but misses embedded command leaks such as `please /help` or `admin says /debug`, which are exactly the backend command surfaces Phase 15 is supposed to exclude from ordinary WeCom delivery evidence.
**Fix:**
```python
re.compile(r"(^|\s)/(new|resume|help|status|debug|memory)\b", re.IGNORECASE)
```
Add a negative fixture/test sample containing an embedded slash command to prove the privacy scan fails closed.

### WR-04: Test Helpers Build Mismatched Turns For Alternate Scopes

**Classification:** WARNING
**File:** `services/wecom-service/tests/test_session_interrupt_runtime.py:285`
**Issue:** `turn()` and `run_request()` always use `self.scope` internally. Tests that pass `scope=self.scope_for(user_id="expired-user")` or `cancelled-user` still send an `AgentTurn` and `RunRequest` for `user-001`, so the suite normalizes scope mismatches instead of detecting them. This masks CR-01 and makes future scope-isolation regressions easy to miss.
**Fix:** Parameterize both helpers by `scope` and default to `self.scope` only when omitted:
```python
def turn(self, turn_id: str, content: str, *, scope: SessionScope | None = None) -> AgentTurn:
    resolved_scope = scope or self.scope
    return AgentTurn(
        turn_id=turn_id,
        conversation_id=resolved_scope.conversation_id,
        user_id=resolved_scope.user_id,
        metadata={"raw_payload_ref": f"fixture://phase15/payloads/{turn_id}", "thread_id": resolved_scope.thread_id},
        ...
    )
```

---

_Reviewed: 2026-07-01T04:24:20Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
