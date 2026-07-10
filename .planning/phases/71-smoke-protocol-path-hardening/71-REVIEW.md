---
phase: 71-smoke-protocol-path-hardening
reviewed: 2026-07-10T05:20:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - scripts/smoke_test.py
  - packages/channels/qqbot/tests/test_smoke_toolkit.py
  - runbook/SMOKE_TEST_RUNBOOK.md
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
fix_recommended: true
---

# Phase 71: Code Review Report

**Reviewed:** 2026-07-10T05:20:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Phase 71 correctly wires dry-run through Phase 70 host helpers (`build_qqbot_wired_runtime` + `handle_qqbot_webhook_request`) with Fake-only DI, mandatory Protocol step gates, RESEARCH allowlist keys under `smoke_evidence.v1`, and forced `not_live_acceptance=true`. No live acceptance claim and no Urllib construction on the dry-run path. Remaining issues are evidence-field honesty (inferred/hardcoded Protocol fields), a weak fail-closed unit proof, and runbook wording that over-applies Protocol steps to `--live`. `--fix` recommended; no blockers.

## Warnings

### WR-01: Protocol evidence fields are inferred, not read from composition

**File:** `scripts/smoke_test.py:471-609`
**Issue:** `_RecordingScheduler.run_all` discards the dict returned by the host thunk (`asyncio.run(run_post_ack_composition(...))`), which already carries real `ingress_action`, `run_id`, `boundary_action`, and `deliver_accepted`. Smoke instead rebuilds Protocol steps from side effects and hardcodes values:

```python
ingress_ok = len(submitted) >= 1
deliver_ok = deliver_count >= 1 and len(deliveries) >= 1
session_ingress = {
    "ok": ingress_ok,
    "ingress_action": "accepted" if ingress_ok else None,  # hardcoded
    "run_id_present": ingress_ok,  # not bool(outcome.run_id)
    "branch": "message",
}
adapter_deliver = {
    "ok": deliver_ok,
    "deliver_accepted": deliver_ok,
    "boundary_action": "allow" if deliver_ok else None,  # hardcoded
}
```

Happy-path Fake side effects make this green, but evidence can mis-stamp allowlisted fields if composition returns a non-`accepted` ingress action, a missing `run_id`, or a non-`allow` boundary while still producing partial side effects. RESEARCH Pattern 2 expects these fields to come from post-ACK composition evidence.
**Fix:** Capture thunk results in `_RecordingScheduler` (e.g. `self.results`), then map allowlisted fields from the composition dict:

```python
class _RecordingScheduler:
    def __init__(self) -> None:
        self.thunks: list[Callable[[], Any]] = []
        self.results: list[Any] = []

    def run_all(self) -> None:
        self.results.clear()
        for thunk in list(self.thunks):
            result = thunk()
            if asyncio.iscoroutine(result):
                result = asyncio.run(result)
            self.results.append(result)

# after scheduler.run_all():
comp = scheduler.results[0] if scheduler.results else {}
run_id = comp.get("run_id")
session_ingress = {
    "ok": bool(run_id) and comp.get("branch") == "message",
    "ingress_action": comp.get("ingress_action"),
    "run_id_present": bool(run_id),
    "branch": comp.get("branch") or "message",
}
adapter_deliver = {
    "ok": bool(comp.get("deliver_accepted")),
    "deliver_accepted": bool(comp.get("deliver_accepted")),
    "boundary_action": comp.get("boundary_action"),
}
# Keep Fake side-effect asserts as secondary fail-closed checks.
```

### WR-02: Fail-closed Protocol gate is untested (false confidence)

**File:** `packages/channels/qqbot/tests/test_smoke_toolkit.py:342-355`
**Issue:** `test_protocol_path_required_for_success` only runs the happy path and asserts Protocol steps are `ok`. It does **not** patch `_step_protocol_path_dry_run` (or otherwise force a Protocol failure) and assert `SystemExit("protocol path step failed: …")`. Leaf-only insufficiency is therefore claimed by the test name but not proven. Runtime fail-closed exists in `run_smoke` (lines 735–738) and works when patched manually, but CI will not catch a regression that removes that gate while leaving Protocol steps present on success.
**Fix:**

```python
def test_protocol_path_required_for_success(self) -> None:
    smoke = _load_smoke_module()
    def failing_protocol():
        return {
            "adapter_ack": {"ok": True, "http_status": 200, "op": 12, "accepted": True},
            "session_ingress": {
                "ok": False,
                "ingress_action": None,
                "run_id_present": False,
                "branch": "message",
            },
            "adapter_deliver": {
                "ok": False,
                "deliver_accepted": False,
                "boundary_action": None,
            },
        }
    with unittest.mock.patch.object(
        smoke, "_step_protocol_path_dry_run", failing_protocol
    ):
        with self.assertRaises(SystemExit) as ctx:
            smoke.run_smoke(mode="dry-run")
    self.assertIn("session_ingress", str(ctx.exception))
```

### WR-03: Runbook Expected outputs over-applies Protocol steps to live

**File:** `runbook/SMOKE_TEST_RUNBOOK.md:92-99`
**Issue:** The “Expected outputs” table correctly separates dry-run vs live transports, but the following sentence lists Protocol steps (`adapter_ack`, `session_ingress`, `adapter_deliver`) as general per-step flags without scoping them to `--dry-run`. `_run_smoke_live` (smoke_test.py:821–831) still emits only leaf steps. Operators can read this as live also proving host Protocol composition — conflicting with Phase 71’s “no live claim” / Phase 72 HUMAN GATE boundary.
**Fix:** Scope the Protocol step list explicitly:

```markdown
Per-step `ok` flags under `steps` (dry-run): `signature`, `send_text`, …
plus Protocol-path `adapter_ack`, `session_ingress`, `adapter_deliver`.
Live (`--live`) currently records leaf steps only; host Protocol live coverage is Phase 72.
```

## Info

### IN-01: `PROTOCOL_FIXED_NOW` is computed at import time

**File:** `scripts/smoke_test.py:91-93`
**Issue:** `PROTOCOL_FIXED_NOW = (datetime.now(...) - timedelta(seconds=30))` is fixed when the module loads. A long-lived process that imports the module and later calls dry-run after the C2C 1h passive-reply window would fail `adapter_deliver` even though CLI/unittest re-exec paths are fine (mirrors Phase 70 host tests).
**Fix:** Compute `received_at` inside `_step_protocol_path_dry_run()` at call time.

### IN-02: Dry-run outcome metadata ignores Protocol Fake transport activity

**File:** `scripts/smoke_test.py:756-764`
**Issue:** `fake_send_count` / `transport_class` reflect the leaf egress Fake transport only. Protocol path constructs a separate `FakeMessageTransport` whose `call_count` is not surfaced in the return dict (evidence steps still record deliver ok). Minor observability gap for debugging.
**Fix:** Optionally add `protocol_fake_deliver_count` from the Protocol transport, or reuse one Fake transport across leaf + Protocol stages.

---

_Reviewed: 2026-07-10T05:20:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
