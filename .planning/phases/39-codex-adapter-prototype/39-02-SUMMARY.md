---
phase: 39
plan: 39-02
title: "CodexExecRunner JSONL Parsing, submit_run → AgentResult Flow, and Error Normalization"
wave: 2
requirements:
  - ADAPTER-01
status: complete
commits:
  - 4e6c171
  - fc094ed
---

# Plan 39-02 — Summary

## Tasks Completed

### Task 39-02-01 — CodexExecRunner + JSONL parsing + fixtures + submit_run wiring (commit 4e6c171)

Created `exec_runner.py` with the full Codex exec runner implementation:

- **`SubprocessTransport` Protocol** — transport abstraction with `run(command, input_text, timeout) -> (returncode, stdout, stderr)`.
- **`_SystemSubprocessTransport`** — default transport using `subprocess.run`.
- **`parse_codex_jsonl(lines, run_id, turn_id) -> CodexExecResult`** — JSONL parser that:
  - Extracts `thread_id` from `thread.started` events.
  - Extracts `agent_message`/`assistant_message` item text as `AgentResult.content` (handles both `item.type` and `item.item_type` field aliases).
  - Maps `turn.completed` → `SUCCEEDED`, first `turn.failed`/`error` → `FAILED` (terminal, no success flip).
  - Returns `codex_empty_stream` contract error when no terminal event is found.
  - Builds a schema-valid `AgentResult` with `result_id`, `turn_id`, `status`, `reply_type`, `content`, `error`, and `metadata`.
- **`_normalize_error(event, stage) -> ErrorInfo`** — maps Codex error kinds to stable `ErrorInfo.code` values:
  - `rate_limit` → `codex_rate_limit` (retryable=True)
  - `auth` → `codex_auth_error` (retryable=False)
  - generic `turn.failed` → `codex_turn_failed` (retryable=None)
  - `error` event → `codex_stream_error` (retryable=None, stage="stream")
- **`_sanitize_message(msg)`** — strips URLs (`https?://\S+` → `[url_redacted]`), tokens (`token=\S+` → `token=[redacted]`), and file paths.
- **`_sanitize_error_details(details)`** — strips `raw_payload`, `content`, `transcript`, `prompt`, `response_body` keys and keys containing `secret`, `token`, `profile_path`.
- **`SubprocessCodexExecRunner`** — concrete runner with injectable transport:
  - `invoke(req)` runs the Codex subprocess, parses JSONL, and handles nonzero exit (`codex_exec_nonzero_exit`) and timeout (`codex_exec_timeout`, retryable=True).
  - Nonzero exit override only triggers when no real failure event was found (detected via `codex_empty_stream` check).

Created JSONL fixture files:
- **`codex_exec_success.jsonl`** — `thread.started` → `turn.started` → `item.completed` (agent_message) → `turn.completed`.
- **`codex_exec_failure.jsonl`** — `turn.failed` (rate_limit) followed by `turn.completed` (tests first-failure-wins).
- **`codex_exec_field_alias.jsonl`** — uses `item.item_type` and `assistant_message` aliases.

Updated `__init__.py` with re-exports for `SubprocessCodexExecRunner`, `SubprocessTransport`, `parse_codex_jsonl`.

Updated `adapter.py` `submit_run` to include `"codex_usage"` in `run_metadata`.

Created `test_runner.py` with 8 tests:
- `CodexJsonlParserTests` (4): success stream, failure first-failure-wins, field alias, empty stream.
- `SubprocessCodexExecRunnerTests` (3): success via fake transport, nonzero exit, timeout.
- `CodexAdapterSubmitRunIntegrationTests` (1): submit_run maps codex success to AgentResult.

### Task 39-02-02 — Error normalization tests + adapter error sanitization (commit fc094ed)

Created `test_error_normalization.py` with 10 tests:

- **`ErrorNormalizationTests`** (6):
  - `test_rate_limit_error_maps_to_codex_rate_limit_retryable`
  - `test_auth_error_maps_to_codex_auth_error_not_retryable`
  - `test_generic_turn_failed_maps_to_codex_turn_failed`
  - `test_stream_error_maps_to_codex_stream_error`
  - `test_first_failure_is_terminal_no_success_flip` (uses `codex_exec_failure.jsonl` fixture)
  - `test_multiple_failures_first_one_wins` (first `turn.failed` code wins over subsequent `error` event)

- **`ErrorSanitizationTests`** (2):
  - `test_error_message_strips_urls_and_tokens` — URLs and `token=...` patterns stripped from `ErrorInfo.message`.
  - `test_error_details_strip_raw_payload_and_secrets` — `raw_payload`, `token`, `profile_path` keys stripped; `safe_field` preserved.

- **`AdapterErrorNormalizationTests`** (2):
  - `test_submit_run_normalizes_first_failure` — adapter `submit_run` with failed `CodexExecResult` produces `Run.result.status == FAILED` with correct `ErrorInfo.code`.
  - `test_submit_run_failed_result_does_not_leak_raw_content` — adapter sanitizes `ErrorInfo.message` (URLs/tokens stripped) even when runner returns unsanitized error.

Updated `adapter.py` with defense-in-depth error sanitization:
- `_sanitize_text(text)` — strips URLs and token patterns from text strings.
- `_sanitize_error_info(error)` — returns new `ErrorInfo` with sanitized `message` and `details`.
- `_sanitize_result(result)` — returns new `AgentResult` with sanitized `ErrorInfo`.
- `submit_run` now calls `_sanitize_result(result.result)` before storing the run.

## Test Results

| Test File | Tests | Passed | Failed |
|-----------|-------|--------|--------|
| test_adapter.py (39-01) | 10 | 10 | 0 |
| test_probe.py (39-01) | 4 | 4 | 0 |
| test_runner.py (39-02-01) | 8 | 8 | 0 |
| test_error_normalization.py (39-02-02) | 10 | 10 | 0 |
| **Total** | **32** | **32** | **0** |

Verification commands used:
- `PYTHONPATH=packages/backends/codex/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/backends/codex/tests -p "test_runner.py" -v` — 8/8 passed
- `PYTHONPATH=packages/backends/codex/src:packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/backends/codex/tests -p "test_error_normalization.py" -v` — 10/10 passed
- `PYTHONPATH=... python -m pytest packages/backends/codex/tests/ -q` — 32/32 passed
- `python -m compileall packages/backends/codex/src -q` — no syntax errors

## Files Modified/Created

| File | Action |
|------|--------|
| `packages/backends/codex/src/inkstatute_backends_codex/exec_runner.py` | Created |
| `packages/backends/codex/src/inkstatute_backends_codex/__init__.py` | Modified (added re-exports) |
| `packages/backends/codex/src/inkstatute_backends_codex/adapter.py` | Modified (codex_usage in metadata, error sanitization) |
| `packages/backends/codex/tests/test_runner.py` | Created |
| `packages/backends/codex/tests/test_error_normalization.py` | Created |
| `packages/backends/codex/tests/fixtures/codex_exec_success.jsonl` | Created |
| `packages/backends/codex/tests/fixtures/codex_exec_failure.jsonl` | Created |
| `packages/backends/codex/tests/fixtures/codex_exec_field_alias.jsonl` | Created |

## Deviations from Plan

1. **Empty stream logic simplified**: The plan specified that `parse_codex_jsonl` should return `SUCCEEDED` when there are no unparsed lines and no terminal event (default if content was found). However, the acceptance criteria and test `test_parse_jsonl_empty_stream_returns_contract_error` expect `parse_codex_jsonl([], ...)` to return `FAILED` with `codex_empty_stream`. The logic was simplified to always return `FAILED` with `codex_empty_stream` when no terminal event is found, regardless of unparsed lines. This is consistent with the acceptance criteria and is safer (no false success on incomplete streams).

2. **Nonzero exit override condition expanded**: The plan specified `if returncode != 0 and result.status != AsyncTaskState.FAILED` for the nonzero exit override. With the empty-stream fix, `parse_codex_jsonl` returns `FAILED` even without a real failure event (when no terminal event is found). The condition was expanded to also override when the error code is `codex_empty_stream` (meaning no real `turn.failed`/`error` event was found), ensuring the more specific `codex_exec_nonzero_exit` code takes precedence over the generic `codex_empty_stream` code.

3. **Adapter error sanitization added (defense-in-depth)**: The plan stated "no structural changes needed" to `adapter.py` beyond adding `codex_usage` to metadata. However, the test `test_submit_run_failed_result_does_not_leak_raw_content` requires the adapter to sanitize `ErrorInfo.message` even when a `FakeCodexExecRunner` returns an unsanitized error. The `_sanitize_text`, `_sanitize_error_info`, and `_sanitize_result` functions were added to `adapter.py` to provide defense-in-depth sanitization at the adapter boundary, ensuring raw URLs and tokens never leak into stored `Run` results regardless of the runner implementation.

## Acceptance Criteria Verification

- [x] `test_runner.py` passes with 0 failures (8/8)
- [x] `parse_codex_jsonl` on success fixture returns `SUCCEEDED`, `content="Here is the legal analysis you requested."`, `error is None`
- [x] `parse_codex_jsonl` on failure fixture returns `FAILED`, `error.code="codex_rate_limit"`, `error.retryable is True`; `turn.completed` after `turn.failed` does NOT flip status
- [x] `parse_codex_jsonl` on field-alias fixture returns `SUCCEEDED`, `content="Response via alias fields."` (proves `item.item_type` and `assistant_message` aliases work)
- [x] `parse_codex_jsonl([], ...)` returns `FAILED`, `error.code="codex_empty_stream"`, `error.category=CONTRACT_ERROR`
- [x] `SubprocessCodexExecRunner` with `FakeSubprocessTransport(returncode=1)` returns `error.code="codex_exec_nonzero_exit"`
- [x] `SubprocessCodexExecRunner` with timeout transport returns `error.code="codex_exec_timeout"`, `error.retryable is True`
- [x] `CodexBackendAdapter.submit_run` with injected `FakeCodexExecRunner` produces `Run.result.content` matching the runner's `AgentResult.content`
- [x] Raw error messages do not leak URLs or tokens into `ErrorInfo.message` or `ErrorInfo.details`
- [x] `test_error_normalization.py` passes with 0 failures (10/10)
- [x] Rate-limit error maps to `ErrorInfo(code="codex_rate_limit", retryable=True, category=RUNTIME_ERROR)`
- [x] Auth error maps to `ErrorInfo(code="codex_auth_error", retryable=False)`
- [x] Generic `turn.failed` maps to `ErrorInfo(code="codex_turn_failed", retryable=None)`
- [x] Stream `error` event maps to `ErrorInfo(code="codex_stream_error", stage="stream")`
- [x] First failure is terminal (no success flip)
- [x] Multiple failures: first failure's error code wins
- [x] Error messages do not contain URLs or tokens
- [x] Error details do not contain `raw_payload`, `token`, `profile_path`, or `secret` keys
- [x] `CodexBackendAdapter.submit_run` with failed `CodexExecResult` produces `Run.result.status == FAILED` with correct `ErrorInfo.code`
- [x] All 39-01 tests still pass (14/14)
- [x] `compileall` on `packages/backends/codex/src` succeeds
- [x] No real `codex` binary required in CI (all tests use fixtures and fake transports)

## EXECUTION COMPLETE
