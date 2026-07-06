---
phase: 46-streaming-events-a1
reviewed: 2026-07-06T05:04:24Z
fixed: 2026-07-06T05:50:00Z
findings_total: 9
findings_fixed: 6
findings_skipped: 3
status: fixed
---

# Phase 46: Code Review Fix Report

**Source:** 46-REVIEW.md
**Fixed:** 2026-07-06
**Status:** fixed (6 of 9 findings addressed — 3 Critical + 3 Warning; 3 Info skipped)

## Summary

All 3 Critical findings and all 3 Warning findings were fixed. The 3 Info findings were skipped as non-blocking cosmetic issues that do not affect correctness or safety.

## Fixes Applied

### CR-01: Codex adapter appends SUCCEEDED terminal after runner yields FAILED — FIXED

**Commit:** `ec1024d` — `fix(46): dedup terminal event and propagate aclose to codex streaming runner`
**File:** `packages/backends/codex/src/inkstatute_backends_codex/adapter.py`

**Fix:** Added `terminal_status` tracking. The adapter now tracks whether the streaming runner already yielded a `STATE_CHANGED` event with `SUCCEEDED`/`FAILED`/`CANCELLED` status. If the runner already emitted a terminal event, the adapter does NOT append another `SUCCEEDED` terminal. Only appends a terminal `SUCCEEDED` if the runner did not emit one (`terminal_status` remains at its initial `SUCCEEDED` default).

### CR-02: Adapter stream_events does not propagate aclose() to inner streaming runner — FIXED

**Commit:** `ec1024d` (codex) + `c733189` (provider_model)
**Files:** `packages/backends/codex/src/inkstatute_backends_codex/adapter.py`, `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py`

**Fix:** Both adapters now assign the inner streaming runner's generator to a variable (`inner = self._streaming_runner.stream(...)`) and wrap the `async for` loop in `try/finally` with `await inner.aclose()` in the `finally` block. This propagates `GeneratorExit` to the inner streaming runner when the runtime calls `aclose()` on the adapter's generator, ensuring provider connection cleanup on client cancellation.

### CR-03: parse_codex_jsonl_stream embeds ErrorInfo dataclass in payload — FIXED

**Commit:** `337ca20` — `fix(46): convert ErrorInfo to dict in stream payload and clarify SSE parse precedence`
**File:** `packages/backends/codex/src/inkstatute_backends_codex/exec_runner.py`

**Fix:** Added `_error_info_to_dict(error: ErrorInfo) -> dict[str, Any]` helper that converts an `ErrorInfo` dataclass to a plain dict with keys: `category`, `code`, `message`, `stage`, `retryable`, `details`. The `parse_codex_jsonl_stream` function now wraps `_normalize_error()` calls with `_error_info_to_dict()` before placing the error in `CodexStreamEvent.payload["error"]`, ensuring JSON serializability for SSE delivery.

### WR-01: provider_model adapter ignores finish_reason — FIXED

**Commit:** `c733189` — `fix(46): propagate aclose to provider_model runner and emit FAILED on truncated finish_reason`
**File:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py`

**Fix:** The adapter now tracks `finish_reason` from each delta. After the stream completes, if `finish_reason` is not `None` and not `"stop"` (e.g., `"length"` for truncated streams), the adapter emits a `FAILED` terminal event instead of `SUCCEEDED`.

### WR-02: Codex adapter duplicate terminal events — FIXED

**Commit:** `ec1024d` (same fix as CR-01)
**File:** `packages/backends/codex/src/inkstatute_backends_codex/adapter.py`

**Fix:** Same root cause as CR-01. The `terminal_status` tracking prevents duplicate terminal events — if the runner already yielded a terminal `STATE_CHANGED`, the adapter does not append another.

### WR-03: parse_sse_deltas operator precedence — FIXED

**Commit:** `337ca20` — `fix(46): convert ErrorInfo to dict in stream payload and clarify SSE parse precedence`
**File:** `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py`

**Fix:** Added explicit parentheses to the choices extraction line: `(parsed.get("choices", []) or []) if isinstance(parsed, dict) else []`. This clarifies that the ternary applies to the entire `or` expression, not just the fallback `[]`.

## Findings Skipped (Info — non-blocking)

### IN-01: Stale `__all__` exports — SKIPPED

Both adapter modules don't list new streaming types in `__all__`. This is cosmetic — the types are exported via `__init__.py` and importable. No functional impact.

### IN-02: Unused `Iterator` import — SKIPPED

Both adapter modules import `Iterator` but never use it directly (the Protocol uses `AsyncIterator`). This is a minor lint issue with no functional impact. Removing it risks breaking the import chain if future code needs it.

### IN-03: provider_model injects `"status": "running"` into MESSAGE_DELTA — SKIPPED

The provider_model adapter puts `"status": "running"` in MESSAGE_DELTA payloads, while the Codex adapter does not. This is an inconsistency but not a bug — the `status` field in MESSAGE_DELTA is informational and does not affect terminal event handling. Consumers read terminal status from STATE_CHANGED events.

## Test Results

After all fixes applied:

- **Codex package:** 42 tests pass
- **provider_model package:** 49 tests pass
- **platform-runtime package:** 262 of 265 tests pass (3 pre-existing failures unrelated to Phase 46):
  - `test_retain_recall_reflect` — Hindsight API rate limit (429 quota exceeded) — external network dependency
  - `test_multi_turn_preference_retention_and_cross_task_recall` — same Hindsight API rate limit
  - `test_runtime_source_does_not_embed_concrete_leak_examples` (forbidden='gateway') — pre-existing from Phase 45 `model_gateway_enabled` in feature_flags.py
- **V2 gate suite:** 19 gates green (exit 0)
- **Contract freeze tests:** pass (no frozen surfaces modified)

## Commits

| Commit | Description |
|--------|-------------|
| `ec1024d` | fix(46): dedup terminal event and propagate aclose to codex streaming runner |
| `c733189` | fix(46): propagate aclose to provider_model runner and emit FAILED on truncated finish_reason |
| `337ca20` | fix(46): convert ErrorInfo to dict in stream payload and clarify SSE parse precedence |
