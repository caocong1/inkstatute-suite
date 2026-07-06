---
phase: 46-streaming-events-a1
reviewed: 2026-07-06T05:04:24Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - packages/backends/codex/src/inkstatute_backends_codex/__init__.py
  - packages/backends/codex/src/inkstatute_backends_codex/adapter.py
  - packages/backends/codex/src/inkstatute_backends_codex/exec_runner.py
  - packages/backends/codex/src/inkstatute_backends_codex/manifest.py
  - packages/backends/codex/tests/fixtures/codex_exec_stream.jsonl
  - packages/backends/codex/tests/test_adapter.py
  - packages/backends/codex/tests/test_stream_events.py
  - packages/backends/codex/tests/test_streaming_runner.py
  - packages/backends/provider_model/src/inkstatute_backends_provider_model/__init__.py
  - packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py
  - packages/backends/provider_model/src/inkstatute_backends_provider_model/manifest.py
  - packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py
  - packages/backends/provider_model/tests/test_adapter.py
  - packages/backends/provider_model/tests/test_stream_events.py
  - packages/backends/provider_model/tests/test_streaming_runner.py
  - packages/platform-runtime/src/platform_runtime/output_boundary.py
  - packages/platform-runtime/src/platform_runtime/ports.py
  - packages/platform-runtime/src/platform_runtime/runtime.py
  - packages/platform-runtime/tests/test_output_boundary.py
  - packages/platform-runtime/tests/test_stream_cancellation.py
findings:
  critical: 3
  warning: 3
  info: 3
  total: 9
status: findings_found
---

# Phase 46: Code Review Report

**Reviewed:** 2026-07-06T05:04:24Z
**Depth:** standard
**Files Reviewed:** 20
**Status:** findings_found

## Summary

Phase 46 implements streaming events for the Codex and provider_model adapters, including `stream_events()` async generators, `try/finally` + `aclose()` cancellation in the runtime, an event-type allowlist in `DefaultAssistantOutputBoundary`, and injected streaming runner protocols.

The FROZEN contract surfaces are intact: `BackendAdapter` (9 methods), `AdapterCapabilitySet` (14 fields), `RunEventType` enum, and `RunEvent` dataclass were not modified. The `dependencies = []` invariant holds — no new external imports were added at module top level. Terminal events correctly use `SUCCEEDED`/`FAILED`/`CANCELLED` (never "completed"). Error messages in stream events use `type(exc).__name__` (class name only) — no stack traces or raw exception messages leak.

However, three Critical issues were found: (1) the Codex adapter unconditionally appends a `SUCCEEDED` terminal event after the streaming runner may have already yielded a `FAILED` terminal, producing an incorrect final status; (2) neither adapter propagates `aclose()` to the inner streaming runner generator, causing resource leaks on client cancellation; (3) `parse_codex_jsonl_stream` embeds `ErrorInfo` dataclass objects directly in `CodexStreamEvent.payload`, making the payload non-JSON-serializable.

## Critical Issues

### CR-01: Codex adapter appends SUCCEEDED terminal after runner yields FAILED — final status is incorrect

**File:** `packages/backends/codex/src/inkstatute_backends_codex/adapter.py:179-187`
**Issue:** The `stream_events()` method unconditionally appends a `STATE_CHANGED/SUCCEEDED` terminal event after the streaming runner completes. If the streaming runner already yielded a `STATE_CHANGED/FAILED` terminal event (which `parse_codex_jsonl_stream` does for `turn.failed` and `error` events), the adapter yields `FAILED` followed by `SUCCEEDED`. A consumer that reads the last terminal event will see `SUCCEEDED` — incorrectly reporting a failed run as successful.

This was verified empirically: a `FakeStreamingCodexRunner` yielding a single `STATE_CHANGED/FAILED` event produces two events: `failed` (seq=0) then `succeeded` (seq=1).

**Fix:**
```python
async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]:
    run = self._require_run(run_id)
    if self._streaming_runner is None:
        yield RunEvent(
            event_id=f"event-{run_id}-000",
            run_id=run_id,
            event_type=RunEventType.STATE_CHANGED.value,
            occurred_at=self._clock.now(),
            seq=0,
            payload={"status": _status_value(run.status)},
            metadata={"source": "codex_stream_terminal"},
        )
        return

    seq = 0
    terminal_status = AsyncTaskState.SUCCEEDED.value
    try:
        async for delta in self._streaming_runner.stream(self._run_requests[run_id]):
            yield RunEvent(
                event_id=f"event-{run_id}-{seq:03d}",
                run_id=run_id,
                event_type=delta.event_type,
                occurred_at=self._clock.now(),
                seq=seq,
                payload=delta.payload,
                metadata={"source": "codex_stream"},
            )
            seq += 1
            # Track terminal status from runner-emitted STATE_CHANGED events
            if delta.event_type == RunEventType.STATE_CHANGED.value:
                status = delta.payload.get("status")
                if status in (AsyncTaskState.SUCCEEDED.value, AsyncTaskState.FAILED.value, AsyncTaskState.CANCELLED.value):
                    terminal_status = status
        # Only append terminal if the runner did not already emit one
        if terminal_status == AsyncTaskState.SUCCEEDED.value:
            yield RunEvent(
                event_id=f"event-{run_id}-{seq:03d}",
                run_id=run_id,
                event_type=RunEventType.STATE_CHANGED.value,
                occurred_at=self._clock.now(),
                seq=seq,
                payload={"status": AsyncTaskState.SUCCEEDED.value},
                metadata={"source": "codex_stream_terminal"},
            )
    except Exception as exc:
        yield RunEvent(
            event_id=f"event-{run_id}-{seq:03d}",
            run_id=run_id,
            event_type=RunEventType.STATE_CHANGED.value,
            occurred_at=self._clock.now(),
            seq=seq,
            payload={
                "status": AsyncTaskState.FAILED.value,
                "error": {"code": "codex_stream_error", "message": type(exc).__name__},
            },
            metadata={"source": "codex_stream_error"},
        )
```

### CR-02: Adapter stream_events does not propagate aclose() to inner streaming runner — resource leak on cancellation

**File:** `packages/backends/codex/src/inkstatute_backends_codex/adapter.py:167-200`
**File:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py:165-201`
**Issue:** Both adapters' `stream_events()` async generators iterate over `self._streaming_runner.stream(...)` using `async for` without a `try/finally` block that calls `aclose()` on the inner generator. When the runtime calls `aclose()` on the adapter's generator (e.g., on client cancellation), `GeneratorExit` is thrown into the `async for` loop. The `async for` protocol does NOT automatically call `aclose()` on the inner async iterator — the caller is responsible for cleanup. This means the inner streaming runner's generator is never closed, and its `finally` blocks (if any) never run.

This was verified empirically: after `aclose()` on the adapter generator, the inner streaming runner's `finally` block did not execute (`cleaned=False`). The runtime's `stream()` method correctly calls `aclose()` on the backend's generator, but the backend adapter does not propagate that cleanup to the injected streaming runner.

The phase constraint explicitly requires: "aclose() must propagate GeneratorExit properly."

**Fix (codex adapter):**
```python
    seq = 0
    inner = self._streaming_runner.stream(self._run_requests[run_id])
    try:
        async for delta in inner:
            yield RunEvent(
                event_id=f"event-{run_id}-{seq:03d}",
                run_id=run_id,
                event_type=delta.event_type,
                occurred_at=self._clock.now(),
                seq=seq,
                payload=delta.payload,
                metadata={"source": "codex_stream"},
            )
            seq += 1
        yield RunEvent(
            event_id=f"event-{run_id}-{seq:03d}",
            run_id=run_id,
            event_type=RunEventType.STATE_CHANGED.value,
            occurred_at=self._clock.now(),
            seq=seq,
            payload={"status": AsyncTaskState.SUCCEEDED.value},
            metadata={"source": "codex_stream_terminal"},
        )
    except Exception as exc:
        yield RunEvent(
            event_id=f"event-{run_id}-{seq:03d}",
            run_id=run_id,
            event_type=RunEventType.STATE_CHANGED.value,
            occurred_at=self._clock.now(),
            seq=seq,
            payload={
                "status": AsyncTaskState.FAILED.value,
                "error": {"code": "codex_stream_error", "message": type(exc).__name__},
            },
            metadata={"source": "codex_stream_error"},
        )
    finally:
        await inner.aclose()
```

Apply the same pattern to the provider_model adapter.

### CR-03: parse_codex_jsonl_stream embeds ErrorInfo dataclass in payload — non-JSON-serializable

**File:** `packages/backends/codex/src/inkstatute_backends_codex/exec_runner.py:240-256`
**Issue:** `parse_codex_jsonl_stream` places an `ErrorInfo` dataclass object directly into `CodexStreamEvent.payload["error"]`. The `CodexStreamEvent.payload` is typed as `JsonObject` (i.e., `dict[str, Any]`), but the `ErrorInfo` object is not a dict. When this payload flows through the adapter into `RunEvent.payload`, any downstream JSON serialization (e.g., SSE delivery to WeCom) will fail with `TypeError: Object of type ErrorInfo is not JSON serializable`.

This was verified empirically: `json.dumps(events[0].payload)` raises `TypeError`.

The non-streaming `parse_codex_jsonl` correctly stores the `ErrorInfo` as a field on `CodexExecResult.result.error` (an `AgentResult` field), not as a raw payload value. The streaming path should convert `ErrorInfo` to a dict before placing it in the payload.

**Fix:**
```python
def _error_info_to_dict(error: ErrorInfo) -> dict[str, Any]:
    return {
        "category": str(error.category),
        "code": error.code,
        "message": error.message,
        "stage": error.stage,
        "retryable": error.retryable,
    }

# In parse_codex_jsonl_stream, replace:
#   payload={"status": AsyncTaskState.FAILED.value, "error": _normalize_error(event, stage="turn")},
# with:
    payload={
        "status": AsyncTaskState.FAILED.value,
        "error": _error_info_to_dict(_normalize_error(event, stage="turn")),
    },
```

## Warnings

### WR-01: provider_model adapter ignores finish_reason — truncated streams report SUCCEEDED

**File:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py:164-185`
**Issue:** The `stream_events()` method always appends a `SUCCEEDED` terminal event regardless of the `finish_reason` from the last `ProviderModelStreamDelta`. The non-streaming `parse_openai_response` correctly maps `finish_reason` values `"length"` and `"content_filter"` to `FAILED` (via `_TRUNCATED_FINISH_REASONS`), but the streaming path ignores `finish_reason` entirely. A truncated completion (`finish_reason="length"`) will be reported as `SUCCEEDED` to the consumer.

This was verified empirically: a stream ending with `finish_reason="length"` produces a terminal `SUCCEEDED` event.

**Fix:**
```python
    seq = 0
    terminal_status = AsyncTaskState.SUCCEEDED.value
    try:
        async for delta in self._streaming_runner.stream(self._run_requests[run_id]):
            yield RunEvent(
                event_id=f"event-{run_id}-{seq:03d}",
                run_id=run_id,
                event_type=RunEventType.MESSAGE_DELTA.value,
                occurred_at=self._clock.now(),
                seq=seq,
                payload={"message_delta": delta.content, "status": "running"},
                metadata={"source": "provider_model_sse"},
            )
            seq += 1
            if delta.finish_reason in _TRUNCATED_FINISH_REASONS:
                terminal_status = AsyncTaskState.FAILED.value
        yield RunEvent(
            event_id=f"event-{run_id}-terminal",
            run_id=run_id,
            event_type=RunEventType.STATE_CHANGED.value,
            occurred_at=self._clock.now(),
            seq=seq,
            payload={"status": terminal_status},
            metadata={"source": "provider_model_sse_terminal"},
        )
    except Exception as exc:
        ...
```

Import `_TRUNCATED_FINISH_REASONS` from `openai_runner.py` or define it locally.

### WR-02: Codex adapter duplicate terminal events when runner yields its own terminal

**File:** `packages/backends/codex/src/inkstatute_backends_codex/adapter.py:179-187`
**Issue:** Even when the streaming runner correctly yields a `STATE_CHANGED/SUCCEEDED` terminal event (as `parse_codex_jsonl_stream` does for `turn.completed`), the adapter appends another `STATE_CHANGED/SUCCEEDED` terminal event. This produces duplicate terminal events. While not incorrect (both are `SUCCEEDED`), it violates the "terminal event guarantee" which implies exactly one terminal event. Consumers that count terminal events or assert on event count may break.

The test `test_stream_events_with_streaming_runner_yields_deltas_and_terminal` explicitly expects 4 events (2 deltas + 2 terminal STATE_CHANGED), confirming this is by design but still a quality concern.

**Fix:** Track whether the runner already emitted a terminal `STATE_CHANGED` event and skip the adapter's terminal append if so. (See CR-01 fix for the pattern.)

### WR-03: parse_sse_deltas operator precedence is hard to read — fragile parsing

**File:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py:196`
**Issue:** The expression:
```python
choices = parsed.get("choices", []) or [] if isinstance(parsed, dict) else []
```
relies on the conditional expression (`X if Y else Z`) having lower precedence than `or`. While the result is technically correct (`(parsed.get("choices", []) or []) if isinstance(parsed, dict) else []`), this is extremely hard to read and fragile. A future maintainer might misread the grouping and introduce a bug. Additionally, if `parsed.get("choices")` returns a non-list truthy value (e.g., a string), `choices[0]` would return a character — though this is handled by the `isinstance(choice, dict)` check on line 198.

**Fix:**
```python
if not isinstance(parsed, dict):
    continue
choices = parsed.get("choices") or []
if not isinstance(choices, list):
    choices = []
```

## Info

### IN-01: Stale __all__ exports in adapter modules — new streaming types not listed

**File:** `packages/backends/codex/src/inkstatute_backends_codex/adapter.py:341`
**File:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py:344`
**Issue:** The `__all__` lists in both adapter modules do not include the new streaming types added in this phase:
- Codex: `StreamingCodexExecRunner` and `CodexStreamEvent` are missing from `__all__`
- provider_model: `StreamingProviderModelRunner` and `ProviderModelStreamDelta` are missing from `__all__`

The `__init__.py` files import these directly (not via `__all__`), so they are still accessible. However, the stale `__all__` is inconsistent and could confuse static analysis tools.

**Fix:**
```python
# codex adapter.py
__all__ = ["CodexBackendAdapter", "CodexExecResult", "CodexExecRunner", "CodexStreamEvent", "StreamingCodexExecRunner"]

# provider_model adapter.py
__all__ = ["ProviderModelBackendAdapter", "ProviderModelExecResult", "ProviderModelRunner", "ProviderModelStreamDelta", "StreamingProviderModelRunner"]
```

### IN-02: Unused Iterator import in both adapter modules

**File:** `packages/backends/codex/src/inkstatute_backends_codex/adapter.py:8`
**File:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py:8`
**Issue:** Both adapter files import `Iterator` from `typing` but never use it. Only `AsyncIterator` is used. This is likely a leftover from an earlier draft.

**Fix:**
```python
from typing import Any, AsyncIterator, Protocol
```

### IN-03: provider_model stream_events injects "status": "running" into MESSAGE_DELTA payload

**File:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py:173`
**Issue:** The provider_model adapter injects `"status": "running"` into every `MESSAGE_DELTA` event payload alongside `message_delta`. This is inconsistent with the Codex adapter, which only puts `message_delta` in the payload. The `status` field in a `MESSAGE_DELTA` event is semantically questionable — status belongs in `STATE_CHANGED` events. The output boundary's `_event_visible_text` function checks `_VISIBLE_TEXT_KEYS = ("message_delta", "visible_text", "text", "content", "delta")`, so `status` is not stripped on BLOCK, but it's also not a visible-text key. This is a minor design inconsistency, not a bug.

**Fix:** Remove `"status": "running"` from the MESSAGE_DELTA payload for consistency with the Codex adapter. The `status` field should only appear in `STATE_CHANGED` events.

---

_Reviewed: 2026-07-06T05:04:24Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
