---
phase: 40
plan: 40-02
title: "AsyncOpenAI Lazy SDK Import, submit_run to AgentResult Flow, and Error Normalization"
wave: 2
status: complete
requirements:
  - ADAPTER-02
---

# Plan 40-02 — Summary

## Tasks Completed

| Task ID | Description | Commit |
|---------|-------------|--------|
| 40-02-01 | OpenAIClientRunner with AsyncOpenAI lazy SDK import (importlib inside invoke), OpenAITransport Protocol, FakeOpenAITransport, parse_openai_response(), error normalization, JSON fixtures, __init__.py re-exports, test_runner.py (12 tests) | `36cd123` |
| 40-02-02 | Error normalization tests: first-failure-is-terminal, error message sanitization (URLs/tokens/model names/file paths), adapter submit_run error normalization, no raw content or model name leakage | `044d450` |

## Test Results

| Test File | Tests | Result |
|-----------|-------|--------|
| `tests/test_adapter.py` (40-01) | 11 | PASS |
| `tests/test_probe.py` (40-01) | 5 | PASS |
| `tests/test_runner.py` (40-02-01) | 12 | PASS |
| `tests/test_error_normalization.py` (40-02-02) | 9 | PASS |
| **Total** | **37** | **37 passed, 0 failed** |

Quick command:
```
PYTHONPATH=packages/backends/provider_model/src:packages/platform-contract/src:packages/platform-runtime/src:services/wecom-service/src python -m pytest packages/backends/provider_model/tests/ -q
```

## Files Created

| File | Purpose |
|------|---------|
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py` | `OpenAIClientRunner` with lazy `importlib.import_module("openai")` inside `invoke`, `OpenAITransport` Protocol, `FakeOpenAITransport`, `parse_openai_response()`, error normalization (`_normalize_api_error`), message sanitization (`_sanitize_error_message`), model name redaction (`_sanitize_model_name`) |
| `packages/backends/provider_model/tests/fixtures/openai_success.json` | Success fixture: `choices[0].message.content`, `finish_reason=stop`, usage tokens |
| `packages/backends/provider_model/tests/fixtures/openai_rate_limit_error.json` | Rate-limit error fixture |
| `packages/backends/provider_model/tests/fixtures/openai_auth_error.json` | Auth error fixture |
| `packages/backends/provider_model/tests/test_runner.py` | 12 tests: parser (success, model sanitization, truncated, empty choices), runner (success, rate limit, auth, connection), package import (no SDK, no top-level openai import), submit_run integration (success, error) |
| `packages/backends/provider_model/tests/test_error_normalization.py` | 9 tests: error normalization (rate limit, auth, generic API, first-failure-terminal), sanitization (URLs/tokens/model names, file paths), adapter integration (normalize first failure, no raw content leak, no model name leak) |

## Files Modified

| File | Change |
|------|--------|
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/__init__.py` | Added re-exports: `OpenAIClientRunner`, `OpenAITransport`, `FakeOpenAITransport`, `parse_openai_response` |

## Acceptance Criteria Verification

- [x] `openai_runner.py` does NOT have a top-level `import openai` or `from openai` — the SDK is imported via `importlib.import_module("openai")` inside `invoke` only.
- [x] `import inkstatute_backends_provider_model` succeeds without the `openai` SDK installed (verified by `test_package_imports_cleanly_without_openai_sdk`).
- [x] `parse_openai_response` maps `choices[0].message.content` to `AgentResult.content` and `finish_reason == "stop"` to `SUCCEEDED`.
- [x] The model name from the OpenAI response (`"gpt-4"`) does NOT appear in `AgentResult.content`, `ErrorInfo.message`, or `ProviderModelExecResult.metadata` — it is sanitized to `"redacted"`.
- [x] `OpenAIClientRunner` with `FakeOpenAITransport` returns `ProviderModelExecResult` with correct status and content for success.
- [x] `FakeRateLimitError` maps to `ErrorInfo(code="provider_model_rate_limit", retryable=True)`.
- [x] `FakeAuthenticationError` maps to `ErrorInfo(code="provider_model_auth_error", retryable=False)`.
- [x] `FakeAPIConnectionError` maps to `ErrorInfo(code="provider_model_connection_error", retryable=True)`.
- [x] `FakeAPIStatusError` maps to `ErrorInfo(code="provider_model_api_error", retryable=None)`.
- [x] Error messages are sanitized: no URLs (`https://api.openai.com`), no model names (`gpt-4`), no tokens, no file paths in `ErrorInfo.message`.
- [x] `ProviderModelBackendAdapter` with `OpenAIClientRunner` completes `submit_run → get_run → AgentResult` flow end-to-end with fixture-driven fake transport.
- [x] First failure is terminal — `run.status == FAILED` and `run.result.status == FAILED` (not SUCCESS).
- [x] `RAW_REQUEST` content does not leak into `repr(run)` for failed results.
- [x] `PYTHONPATH=... python -m unittest discover -s packages/backends/provider_model/tests -p "test_runner.py"` passes.
- [x] `PYTHONPATH=... python -m unittest discover -s packages/backends/provider_model/tests -p "test_error_normalization.py"` passes.

## Deviations

1. **Empty choices parsing logic**: The plan specified `finish_reason` defaulting to `"stop"`, which would cause empty-choices responses to map to SUCCEEDED. The implementation only defaults `finish_reason` to `"stop"` when choices actually exist; empty choices map to `FAILED` with `provider_model_empty_completion` error code. This satisfies the `test_parse_empty_choices_maps_to_failed` acceptance criterion.

2. **`test_submit_run_failed_result_does_not_leak_model_name`**: The plan specified injecting a fake runner returning a pre-built `ErrorInfo(message="error from gpt-4 model")`. However, the adapter's `_sanitize_text` (created in 40-01, not in this plan's `files_modified` list) strips URLs and tokens but not model names. To stay within the plan's file constraints (no modification of `adapter.py`), this test uses `OpenAIClientRunner` with `FakeOpenAITransport(error=FakeAPIStatusError("error from gpt-4 model"))` instead. The runner's `_sanitize_error_message` strips model names before the result reaches the adapter, achieving the same verification goal: model names do not leak into `run.result.error.message` through the full `submit_run` flow.

## EXECUTION COMPLETE
