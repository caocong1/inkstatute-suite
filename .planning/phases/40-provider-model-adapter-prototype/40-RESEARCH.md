---
phase: 40
slug: provider-model-adapter-prototype
status: planning
researcher: gsd-planner
created: 2026-07-04
---

# Phase 40 Research — Provider Model Adapter Prototype

> Requirements: **ADAPTER-02** — Operator can configure `agent_backend.mode=provider_model` and the runtime selector routes to a direct provider_model adapter prototype that returns a valid `AgentBackendManifest`, passes capability probe, and completes a minimal `submit_run → AgentResult` flow via `AsyncOpenAI` lazy SDK import.
> **ADAPTER-03** — Operator can run output boundary fixture tests proving Codex and provider_model backend noise (function call traces, model names, API errors, rate-limit notices) is blocked or rewritten before delivery to any channel.

## 1. Summary

Phase 40 builds the second non-Hermes concrete `BackendAdapter` implementation: a direct provider_model adapter that proves the v1.5 contract surface is backend-portable for a direct-LLM invocation lane. The work is **additive and isolated** — a new package `packages/backends/provider_model/` mirroring the existing `packages/backends/codex/` structure, plus one PYTHONPATH entry and one gate in `scripts/run_v2_gates.py`. No changes to `platform-contract`, `platform-runtime` Protocols, or the runtime selector logic are required.

Phase 40 also delivers **output boundary fixture tests** (ADAPTER-03) proving that backend noise from both new backends (Codex and provider_model) — function call traces, model names like "gpt-4", API errors, rate-limit notices — is blocked or rewritten before delivery to any channel. These tests live in `packages/contract-test-suite/tests/` and exercise the existing `DefaultAssistantOutputBoundary` and `apply_output_policy` noise rules.

Key findings:

- The `BackendAdapter` Protocol (9 methods) is frozen at `packages/platform-runtime/src/platform_runtime/protocols.py:222-239`. The provider_model adapter must implement exactly these 9 methods — no more, no less.
- `AdapterCapabilitySet` (14 fields) is frozen at `packages/platform-contract/src/platform_contract/agent_adapter.py:18-33`. The provider_model adapter must populate all 14 fields truthfully (prototype = reduced capabilities).
- `AgentBackendMode.PROVIDER_MODEL` already exists (`packages/platform-contract/src/platform_contract/agent_adapter.py:15`) — no enum change needed.
- The runtime selector `select_agent_backend` (`services/wecom-service/src/wecom_service/agent_backend.py:23-56`) already routes by `mode` and validates manifests. The SAFETY-01 fix (Phase 36) guarantees `live_acceptance_allowed=False` for all non-Hermes modes regardless of `production_ready` metadata — so the provider_model prototype with `production_ready: false` and `no_channel_io: true` is contract-compatible but never live-eligible.
- `provider_model_backend_enabled` feature flag already exists and defaults to `False` (`packages/platform-runtime/src/platform_runtime/feature_flags.py:25`). The adapter should gate its `submit_run` on this flag (or document that the host gates it).
- The `AsyncOpenAI` import must be **lazy** (via `importlib.import_module("openai").AsyncOpenAI` inside the runner function) so the package imports cleanly without the `openai` SDK installed. Tests must use mock/fake transports, not real API calls.
- `AgentResult` schema is at `packages/platform-contract/src/platform_contract/events.py:140-155`. The adapter maps the OpenAI chat completion response `choices[0].message.content` to `AgentResult.content`, and API errors / rate-limit responses to `AgentResult.error` with `ErrorInfo` normalization.
- Error normalization on first failure: the adapter must produce a single `AgentResult` with `status=FAILED` and a normalized `ErrorInfo` on the **first** failure event encountered, and not emit a second contradictory success result.
- The existing `DefaultAssistantOutputBoundary` at `packages/platform-runtime/src/platform_runtime/output_boundary.py:82-113` already has hard-block rules for `provider_leak` (model/provider names, api_key, quota, token_usage), `api_error` (api key invalid, quota exceeded, rate limit retry, insufficient quota), and `function_trace` (function call, tool output, token usage report, function_call_result). It also has rewrite rules for `rate_limit_notice` and `context_window`. These are the noise patterns ADAPTER-03 tests must exercise.
- The existing `apply_output_policy` at `services/wecom-service/src/wecom_service/output_policy.py:54-85` has block patterns for stack traces, tokens, secrets, internal paths, and rewrite patterns for gateway lifecycle notices.
- Current V2 gate count is 12 (Phase 39 added the `codex-backend` gate). Phase 40 adds a 13th `provider-model-backend` gate.

## 2. Existing Backend Adapter Pattern

### 2.1 BackendAdapter Protocol (9 methods, frozen)

**File:** `packages/platform-runtime/src/platform_runtime/protocols.py:222-239`

```python
class BackendAdapter(Protocol):
    def backend_id(self) -> str: ...                                   # 1
    def capabilities(self) -> AdapterCapabilitySet: ...                # 2
    async def bootstrap_check(self) -> BootstrapStatus: ...            # 3
    async def submit_run(self, req: RunRequest) -> RunHandle: ...      # 4
    async def get_run(self, run_id: str) -> Run: ...                   # 5
    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]: ...  # 6
    async def cancel_run(self, run_id: str) -> Run: ...                # 7
    async def submit_approval(self, run_id: str, approval: Approval) -> Run: ...  # 8
    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]: ...  # 9
```

The method count is frozen by `packages/contract-test-suite/tests/test_contract_count_freeze.py:23-35` (`BACKEND_ADAPTER_METHOD_COUNT = 9`). The provider_model adapter must implement exactly these 9 callable methods (verified by the same `dir()`-introspection test pattern used in `packages/backends/codex/tests/test_adapter.py:110-124`).

### 2.2 AgentBackendManifest

**File:** `packages/platform-contract/src/platform_contract/agent_adapter.py:36-45`

```python
@dataclass(frozen=True, slots=True)
class AgentBackendManifest:
    adapter_name: str
    adapter_version: str
    mode: AgentBackendMode | str
    backend_version: str
    capabilities: AdapterCapabilitySet
    profile_name: str | None = None
    bundle_id: str | None = None
    metadata: JsonObject = field(default_factory=dict)
```

Validation is performed by `validate_agent_backend_manifest` (`agent_adapter.py:48-106`), which checks: `adapter_name`, `adapter_version`, `mode` (must be in `AgentBackendMode`), `backend_version`, `capabilities.invocation_mode` (non-blank), and `capabilities.no_channel_io` (must be a bool). The provider_model manifest must pass this validator with zero issues.

### 2.3 AdapterCapabilitySet (14 fields, frozen)

**File:** `packages/platform-contract/src/platform_contract/agent_adapter.py:18-33`

```python
@dataclass(frozen=True, slots=True)
class AdapterCapabilitySet:
    hook_event_support: list[str] = field(default_factory=list)        # 1
    invocation_mode: str | None = None                                 # 2
    feedback_target_support: str | None = None                         # 3
    session_read_support: bool = False                                 # 4
    artifact_return_support: bool = False                              # 5
    trace_support: bool = False                                        # 6
    no_channel_io: bool | None = None                                  # 7
    run_invocation_modes: list[str] = field(default_factory=list)      # 8
    stream_event_support: bool = False                                 # 9
    cancel_support: bool = False                                       # 10
    approval_support: bool = False                                     # 11
    live_update_support: bool = False                                  # 12
    parallel_task_support: bool = False                                # 13
    session_memory_support: bool = False                               # 14
```

Field count is frozen by `test_contract_count_freeze.py:37-45` (`ADAPTER_CAPABILITY_SET_FIELD_COUNT = 14`). Success Criterion 1 requires the provider_model capability probe to return an `AdapterCapabilitySet` consistent with this 14-field baseline.

### 2.4 Runtime Selector

**File:** `services/wecom-service/src/wecom_service/agent_backend.py:23-56`

The selector `select_agent_backend(config, manifests)`:
1. Reads `config["agent_backend"]["mode"]` or `config["agent_backend.mode"]` (line 59-67).
2. Validates the mode is a known `AgentBackendMode` value (line 30-31).
3. Finds the matching manifest by mode (line 33, `_find_manifest` line 70-79).
4. Validates the manifest via `validate_agent_backend_manifest` (line 37-40).
5. Asserts `capabilities.no_channel_io is True` (line 42-45) — **any adapter without `no_channel_io=True` is rejected**.
6. Computes `live_acceptance_allowed = production_ready and requested_mode == AgentBackendMode.HERMES.value` (line 48-49).

The provider_model adapter is selected when `agent_backend.mode=provider_model` and a provider_model manifest is present in the `manifests` sequence. The selector returns `AgentBackendSelection(mode="provider_model", manifest=<provider_model manifest>, live_acceptance_allowed=False, contract_compatible=True)`.

**Existing test coverage** (`services/wecom-service/tests/test_agent_backend.py`): existing tests prove non-Hermes modes with `production_ready=False` select with `live_acceptance_allowed=False`, and even `production_ready=True` non-Hermes modes stay non-live. Phase 40 should add a contract-test-suite test that feeds the **real** `build_provider_model_manifest()` output through `select_agent_backend` (mirroring `test_codex_backend_contract.py`).

## 3. Codex Adapter Implementation (Reference Pattern)

The Codex adapter at `packages/backends/codex/` is the exact structural template for the provider_model adapter. Phase 39 shipped it complete with 9-method adapter, manifest factory, capability probe, JSONL runner, error normalization, and V2 gate integration.

### 3.1 Package structure

```
packages/backends/codex/
├── pyproject.toml                          # dependencies = []
├── README.md
├── src/inkstatute_backends_codex/
│   ├── __init__.py                         # public re-exports
│   ├── adapter.py                          # CodexBackendAdapter (9 methods)
│   ├── config.py                           # CodexBackendConfig dataclass
│   ├── manifest.py                         # build_codex_manifest()
│   ├── probe.py                            # CodexCapabilityProbe
│   └── exec_runner.py                      # SubprocessCodexExecRunner + parse_codex_jsonl
├── tests/
│   ├── __init__.py
│   ├── test_adapter.py
│   ├── test_probe.py
│   ├── test_runner.py
│   ├── test_error_normalization.py
│   └── fixtures/
│       ├── codex_exec_success.jsonl
│       ├── codex_exec_failure.jsonl
│       └── codex_exec_field_alias.jsonl
```

The provider_model adapter mirrors this exactly, replacing `exec_runner.py` with `openai_runner.py` (AsyncOpenAI lazy import + fake transport for tests).

### 3.2 CodexBackendAdapter (9 methods)

**File:** `packages/backends/codex/src/inkstatute_backends_codex/adapter.py:44-167`

The adapter delegates `submit_run` to an injectable `CodexExecRunner` Protocol (`adapter.py:26-29`). When no runner is injected, `submit_run` raises `RuntimeError("codex exec runner not configured")`. The runner is wired in Plan 39-02 via `SubprocessCodexExecRunner`.

Key helpers copied from the Hermes adapter and reused in the provider_model adapter:
- `_raw_payload_ref(req)` — extract `raw_payload_ref` from turn metadata (reference-first).
- `_content_sha256(content)` — hash the request content for audit without storing it.
- `_coerce_task_state(status)` — coerce string/enum to `AsyncTaskState`.
- `_default_result(req, status)` — build a minimal `AgentResult` when the runner returns none.
- `_sanitize_metadata(metadata)` — strip `raw_payload`, `content`, `transcript`, `prompt`, `response_body` keys and any key containing `secret`, `token`, or `profile_path`.
- `_sanitize_value(value)` — recursive sanitization for nested dicts/lists.
- `_sanitize_text(text)` — strip URLs (`https?://\S+` → `[url_redacted]`) and token patterns (`token=\S+` → `token=[redacted]`).

### 3.3 CodexExecResult (reference-first result dataclass)

**File:** `packages/backends/codex/src/inkstatute_backends_codex/adapter.py:32-41`

```python
@dataclass(frozen=True, slots=True)
class CodexExecResult:
    status: AsyncTaskState | str = AsyncTaskState.SUCCEEDED
    result: AgentResult | None = None
    thread_id: str | None = None
    artifact_refs: list[str] = field(default_factory=list)
    raw_payload_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)
```

The provider_model adapter defines an analogous `ProviderModelExecResult` with `completion_id` instead of `thread_id`, and `model_name` in metadata (sanitized before delivery).

### 3.4 Codex manifest factory

**File:** `packages/backends/codex/src/inkstatute_backends_codex/manifest.py:14-54`

`build_codex_manifest()` returns a manifest with `mode=AgentBackendMode.CODEX`, `production_ready=False`, `no_channel_io=True`, `invocation_mode="sync"`, `run_invocation_modes=["oneshot"]`. The provider_model manifest factory mirrors this with `mode=AgentBackendMode.PROVIDER_MODEL`, `invocation_mode="direct_llm"`, `run_invocation_modes=["oneshot"]`.

### 3.5 Codex capability probe

**File:** `packages/backends/codex/src/inkstatute_backends_codex/probe.py:40-66`

`CodexCapabilityProbe` calls `codex --version` via an injectable `CodexProbeTransport` Protocol (NOT a real subprocess in tests) and returns a `CodexProbeReport` with a 14-field `AdapterCapabilitySet`. The probe must never invoke the execution subcommand with a prompt — it is non-mutating.

The provider_model probe mirrors this: it checks whether the `openai` SDK is importable (via `importlib.util.find_spec("openai")`) without actually importing it, and returns a `ProviderModelProbeReport` with a 14-field capability set. The probe must never make a real API call.

## 4. AsyncOpenAI Lazy SDK Import Pattern

### 4.1 Why lazy import

The `openai` Python SDK is an optional runtime dependency. The provider_model package must import cleanly **without** the SDK installed — the same way the Codex adapter imports cleanly without the `codex` binary on PATH. This is verified by the `compileall` gate and by a dedicated test that imports the package with `openai` absent from `sys.modules`.

### 4.2 importlib pattern

The runner module (`openai_runner.py`) uses `importlib.import_module` inside the `invoke` method, never at module top level:

```python
import importlib

class SubprocessProviderModelRunner:  # actually OpenAIClientRunner
    async def invoke(self, req: RunRequest) -> ProviderModelExecResult:
        openai_module = importlib.import_module("openai")
        AsyncOpenAI = openai_module.AsyncOpenAI
        client = AsyncOpenAI(api_key=self.config.api_key_ref, base_url=self.config.api_base_url)
        # ... call client.chat.completions.create(...)
```

Module top level imports only stdlib (`importlib`, `json`, `re`) and platform-contract/runtime types — never `openai`. This guarantees `import inkstatute_backends_provider_model` succeeds without the SDK.

### 4.3 Fake transport for tests

Tests inject a `FakeOpenAITransport` that implements the same interface as `AsyncOpenAI.chat.completions.create()` but returns fixture-driven responses. No real API calls are made. The transport is injected via the runner constructor, mirroring the `SubprocessTransport` Protocol pattern in the Codex adapter (`exec_runner.py:44-54`).

### 4.4 OpenAI chat completion response mapping

A successful OpenAI chat completion response has this shape (simplified):

```json
{
  "id": "chatcmpl-...",
  "model": "gpt-4",
  "choices": [
    {"index": 0, "message": {"role": "assistant", "content": "..."}, "finish_reason": "stop"}
  ],
  "usage": {"prompt_tokens": 123, "completion_tokens": 456, "total_tokens": 579}
}
```

The runner maps:
- `choices[0].message.content` → `AgentResult.content`
- `choices[0].finish_reason == "stop"` → `AsyncTaskState.SUCCEEDED`
- `usage` → `result.metadata["provider_usage"]` (sanitized — no model name in visible output)
- `id` → `result.metadata["provider_completion_id"]`

### 4.5 Error response mapping

OpenAI API errors raise exceptions (`openai.RateLimitError`, `openai.AuthenticationError`, `openai.APIConnectionError`, `openai.APIStatusError`). The runner catches these and maps them to normalized `ErrorInfo`:

| Exception | ErrorInfo.code | ErrorInfo.retryable | ErrorInfo.category |
|-----------|---------------|---------------------|-------------------|
| `RateLimitError` | `provider_model_rate_limit` | `True` | `RUNTIME_ERROR` |
| `AuthenticationError` | `provider_model_auth_error` | `False` | `RUNTIME_ERROR` |
| `APIConnectionError` | `provider_model_connection_error` | `True` | `RUNTIME_ERROR` |
| `APIStatusError` (other) | `provider_model_api_error` | `None` | `RUNTIME_ERROR` |
| Generic `Exception` | `provider_model_unknown_error` | `None` | `RUNTIME_ERROR` |

Error messages are sanitized: URLs, tokens, file paths, and model names are stripped before being placed in `ErrorInfo.message`. The `model` field from the response is **never** placed in `AgentResult.content` or `ErrorInfo.message` — it goes only into sanitized metadata.

## 5. Output Boundary Noise Patterns to Test (ADAPTER-03)

### 5.1 DefaultAssistantOutputBoundary rules

**File:** `packages/platform-runtime/src/platform_runtime/output_boundary.py:82-113`

The existing `DefaultAssistantOutputBoundary` already has rules that block or rewrite backend noise. ADAPTER-03 tests must prove these rules catch the specific noise patterns emitted by Codex and provider_model backends:

**Hard-block rules** (action=BLOCK, visible_text=None):
- `provider_leak` — `model[:\s]`, `provider[:\s]`, `api[_-]?key`, `quota`, `token[_\s-]?usage` — catches model name leakage ("gpt-4", "model: gpt-4") and API key references.
- `api_error` — `api key invalid`, `quota exceeded`, `rate limit retry`, `insufficient quota` — catches raw API error messages.
- `function_trace` — `function call`, `tool output`, `token usage report`, `function_call_result` — catches function call traces and tool output dumps.
- `secret_like` — `access_token`, `api_key`, `client_secret`, `token=`, `secret=` — catches secret-like values.
- `debug_trace` — `admin_notice`, `stack trace`, `traceback`, `delivery debug`, `runtime detail` — catches debug traces.

**Rewrite rules** (action=REWRITE, visible_text=owned notice):
- `rate_limit_notice` — `rate[_ ]?limit`, `too many requests`, `retrying after \d+` — rewrites rate-limit notices to an InkStatute-owned service notice.
- `context_window` — `context window exceeded`, `maximum context`, `token limit` — rewrites context-window notices.
- `tool_progress` — `tool progress`, `internal retrieval`, `memory sync`, `tool call` — rewrites tool progress noise.
- `backend_lifecycle` — `self-update`, `restart`, `reconnect`, `disconnect`, `shutting down` — rewrites backend lifecycle noise.

### 5.2 apply_output_policy rules (WeCom delivery boundary)

**File:** `services/wecom-service/src/wecom_service/output_policy.py:54-85`

The WeCom-specific `apply_output_policy` has additional block/rewrite patterns. ADAPTER-03 tests should also verify that the WeCom output policy catches backend noise before delivery.

### 5.3 Noise patterns to cover in fixture tests

ADAPTER-03 requires fixture tests proving both Codex and provider_model backend noise is blocked or rewritten. The test matrix:

| Noise Category | Example Input | Expected Action | Rule |
|---------------|--------------|-----------------|------|
| Model name leakage | `"model: gpt-4 generated this response"` | BLOCK | `provider_leak` |
| Model name in error | `"Error from gpt-4: rate limit"` | BLOCK | `provider_leak` |
| API error message | `"api key invalid for provider"` | BLOCK | `api_error` |
| Rate-limit notice | `"rate limit exceeded, retrying after 30s"` | REWRITE | `rate_limit_notice` |
| Rate-limit (variant) | `"too many requests, please slow down"` | REWRITE | `rate_limit_notice` |
| Function call trace | `"function call: get_weather(args=...)"` | BLOCK | `function_trace` |
| Tool output dump | `"tool output: {\"result\": ...}"` | BLOCK | `function_trace` |
| Token usage report | `"token usage report: 1234 tokens"` | BLOCK | `function_trace` |
| Context window | `"context window length exceeded"` | REWRITE | `context_window` |
| Codex thread trace | `"codex thread started, turn.completed"` | ALLOW (business) | — (if it's legal content) |
| Secret-like value | `"api_key=REDACTED"` | BLOCK | `secret_like` |
| Stack trace | `"traceback: RuntimeError at line 42"` | BLOCK | `debug_trace` |

These tests go in `packages/contract-test-suite/tests/test_output_boundary_backend_noise.py` and exercise `DefaultAssistantOutputBoundary.apply()` with fixture inputs representing both Codex and provider_model backend noise.

## 6. V2 Gate Integration Approach

### 6.1 Current gate structure

**File:** `scripts/run_v2_gates.py:49-149`

Current gate count: 12 (Phase 39 added `codex-backend`). The gates are defined in `_gates()` returning a tuple of `Gate` namedtuples.

### 6.2 Phase 40 gate changes

1. Add `provider_model_backend_src` variable (after `codex_backend_src` at line 64):
   ```python
   provider_model_backend_src = repo_root / "packages" / "backends" / "provider_model" / "src"
   ```
2. Add a new `provider-model-backend` gate (after `codex-backend`, before `feedback-service`):
   ```python
   Gate(
       "provider-model-backend",
       (py, "-m", "unittest", "discover", "-s", "packages/backends/provider_model/tests"),
       (provider_model_backend_src, platform_src, platform_runtime_src, wecom_src),
   ),
   ```
3. Add `provider_model_backend_src` to the `contract-test-suite` gate PYTHONPATH (line 121) so contract tests can import `inkstatute_backends_provider_model`.
4. Add `"packages/backends/provider_model/src"` to the `compileall` gate path list (after `"packages/backends/codex/src"` at line 138).

Gate count: 12 → 13.

### 6.3 Contract-test-suite additions

- `test_provider_model_backend_contract.py` — mirrors `test_codex_backend_contract.py`: verifies real `build_provider_model_manifest()` passes `validate_agent_backend_manifest`, selects via `select_agent_backend` with `live_acceptance_allowed=False`, has 14 capability fields, exposes 9 BackendAdapter methods, and `mode == AgentBackendMode.PROVIDER_MODEL`.
- `test_output_boundary_backend_noise.py` — ADAPTER-03 fixture tests proving Codex and provider_model backend noise is blocked or rewritten by `DefaultAssistantOutputBoundary` and `apply_output_policy`.

## 7. Contract Freeze Invariants to Preserve

Phase 40 must NOT modify any frozen contract surface. The following invariants are verified by existing tests and must remain green:

| Invariant | Test File | Assertion |
|-----------|-----------|-----------|
| BackendAdapter has 9 methods | `test_contract_count_freeze.py:27-35` | `BACKEND_ADAPTER_METHOD_COUNT = 9` |
| AdapterCapabilitySet has 14 fields | `test_contract_count_freeze.py:37-45` | `ADAPTER_CAPABILITY_SET_FIELD_COUNT = 14` |
| ChannelAdapter has 6 methods | `test_contract_count_freeze.py:47-55` | `CHANNEL_ADAPTER_METHOD_COUNT = 6` |
| AgentBackendMode has 3 values | `agent_adapter.py:12-15` | HERMES, CODEX, PROVIDER_MODEL |
| Manifest validator checks no_channel_io | `agent_adapter.py:88-104` | must be a bool |
| Runtime selector rejects no_channel_io != True | `agent_backend.py:42-45` | selector assertion |
| SAFETY-01: non-Hermes never live | `agent_backend.py:48-49` | `live_acceptance_allowed = production_ready and mode == HERMES` |

Phase 40 must NOT modify:
- `packages/platform-contract/` — no schema, enum, or dataclass changes.
- `packages/platform-runtime/src/platform_runtime/protocols.py` — no Protocol changes.
- `services/wecom-service/src/wecom_service/agent_backend.py` — no selector logic changes.

## 8. Privacy Constraints

- **No literal secret-like values** in plan files or fixtures. Use `REDACTED` or short placeholders. The privacy scanner scans `.planning/phases/**/*.md`.
- The `api_key` for AsyncOpenAI is referenced by name (`api_key_ref`), never stored in config or committed. The config holds a reference name, not the value.
- Error messages from the provider API are sanitized before being placed in `ErrorInfo.message` — URLs, tokens, file paths, and model names are stripped.
- The `model` field from OpenAI responses goes into sanitized metadata only, never into `AgentResult.content` or visible output.
- `raw_payload_ref` pattern is used for request content references — no raw payloads stored.
- `_sanitize_metadata` strips `raw_payload`, `content`, `transcript`, `prompt`, `response_body`, and any key containing `secret`, `token`, or `profile_path`.

## 9. ProviderModelBackendConfig Design

The config dataclass mirrors `CodexBackendConfig` but with provider_model-specific fields:

```python
@dataclass(frozen=True, slots=True)
class ProviderModelBackendConfig:
    backend_id: str = "provider-model-prototype"
    backend_version: str = "unknown"
    adapter_version: str = "0.1.0"
    model_name: str = "unknown"           # referenced in metadata only, never in visible output
    api_key_ref: str | None = None        # reference name, not the actual key
    api_base_url: str | None = None       # base URL reference
    timeout: float = 30.0
    metadata: JsonObject = field(default_factory=dict)
```

The `api_key_ref` is a **reference name** (e.g., `"OPENAI_API_KEY"`), not the actual key value. The runner resolves the actual key from the environment at invocation time, never storing it in config or metadata.

## 10. Capability Set for provider_model Prototype

The provider_model prototype declares truthful reduced capabilities:

```python
AdapterCapabilitySet(
    hook_event_support=[],
    invocation_mode="direct_llm",
    feedback_target_support="generated",
    session_read_support=False,
    artifact_return_support=False,
    trace_support=False,
    no_channel_io=True,
    run_invocation_modes=["oneshot"],
    stream_event_support=False,
    cancel_support=False,
    approval_support=False,
    live_update_support=False,
    parallel_task_support=False,
    session_memory_support=False,
)
```

Key differences from Codex:
- `invocation_mode="direct_llm"` (Codex uses `"sync"` — the provider_model adapter invokes a direct LLM API call, not a subprocess).
- `trace_support=False` (Codex has `True` because `codex exec --json` emits structured trace events; the provider_model adapter does not emit structured traces in the prototype).

## 11. Implementation Wave Structure

| Wave | Plan | Scope | Depends On |
|------|------|-------|------------|
| 1 | 40-01 | Package structure + ProviderModelBackendAdapter + manifest + capability probe | — |
| 2 | 40-02 | AsyncOpenAI lazy SDK import + fixture-driven submit_run → AgentResult flow | 40-01 |
| 3 | 40-03 | Output boundary fixture tests (Codex + provider_model noise blocking) + V2 gate integration | 40-01, 40-02 |

Each wave is committed atomically. Wave 1 creates the package skeleton with a stub `submit_run` (raises `RuntimeError` when no runner is injected). Wave 2 wires the real `OpenAIClientRunner` with lazy import and fixture-driven tests. Wave 3 adds output boundary fixture tests and the V2 gate.
