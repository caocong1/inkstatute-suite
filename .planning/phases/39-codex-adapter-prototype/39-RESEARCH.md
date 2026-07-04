---
phase: 39
slug: codex-adapter-prototype
status: planning
researcher: gsd-phase-researcher
created: 2026-07-04
---

# Phase 39 Research — Codex Adapter Prototype

> Requirement: **ADAPTER-01** — Operator can configure `agent_backend.mode=codex` and the runtime selector routes to a Codex adapter prototype that returns a valid `AgentBackendManifest`, passes capability probe, and completes a minimal `submit_run → AgentResult` flow via `codex exec --json` subprocess.

## 1. Summary

Phase 39 builds the first non-Hermes concrete `BackendAdapter` implementation: a Codex adapter that proves the v1.5 contract surface is backend-portable. The work is **additive and isolated** — a new package `packages/backends/codex/` mirroring the existing `packages/backends/hermes/` structure, plus one PYTHONPATH entry in `scripts/run_v2_gates.py`. No changes to `platform-contract`, `platform-runtime` Protocols, or the runtime selector logic are required.

Key findings:

- The `BackendAdapter` Protocol (9 methods) is frozen at `packages/platform-runtime/src/platform_runtime/protocols.py:222-239`. The Codex adapter must implement exactly these 9 methods — no more, no less.
- `AdapterCapabilitySet` (14 fields) is frozen at `packages/platform-contract/src/platform_contract/agent_adapter.py:18-33`. The Codex adapter must populate all 14 fields truthfully (prototype = reduced capabilities).
- `AgentBackendMode.CODEX` already exists (`packages/platform-contract/src/platform_contract/agent_adapter.py:14`) — no enum change needed.
- The runtime selector `select_agent_backend` (`services/wecom-service/src/wecom_service/agent_backend.py:23-56`) already routes by `mode` and validates manifests. The SAFETY-01 fix (Phase 36) guarantees `live_acceptance_allowed=False` for all non-Hermes modes regardless of `production_ready` metadata — so the Codex prototype with `production_ready: false` and `no_channel_io: true` is contract-compatible but never live-eligible.
- `codex_backend_enabled` feature flag already exists and defaults to `False` (`packages/platform-runtime/src/platform_runtime/feature_flags.py:24`). The adapter should gate its `submit_run` on this flag (or document that the host gates it).
- `codex exec --json` emits JSONL events to stdout (`thread.started`, `turn.started`, `item.*`, `turn.completed`, `turn.failed`, `error`). The adapter parses these via stdlib `subprocess` + `json` — **no new Python dependencies** (`dependencies = []`).
- `AgentResult` schema is at `packages/platform-contract/src/platform_contract/events.py:140-155`. The adapter maps the final `item.completed` with `item.type = "assistant_message"` (or `agent_message`) to `AgentResult.content`, and `turn.failed`/`error` events to `AgentResult.error` with `ErrorInfo` normalization.
- Error normalization on first failure: the adapter must produce a single `AgentResult` with `status=FAILED` and a normalized `ErrorInfo` on the **first** failure event encountered, and not emit a second contradictory success result.

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

The method count is frozen by `packages/contract-test-suite/tests/test_contract_count_freeze.py:23-35` (`BACKEND_ADAPTER_METHOD_COUNT = 9`). The Codex adapter must implement exactly these 9 callable methods (verified by the same `dir()`-introspection test pattern used in `packages/backends/hermes/tests/test_hermes_backend_adapter.py:95-109`).

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

Validation is performed by `validate_agent_backend_manifest` (`agent_adapter.py:48-106`), which checks: `adapter_name`, `adapter_version`, `mode` (must be in `AgentBackendMode`), `backend_version`, `capabilities.invocation_mode` (non-blank), and `capabilities.no_channel_io` (must be a bool). The Codex manifest must pass this validator with zero issues.

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

Field count is frozen by `test_contract_count_freeze.py:37-45` (`ADAPTER_CAPABILITY_SET_FIELD_COUNT = 14`). Success Criterion 2 requires the Codex capability probe to return an `AdapterCapabilitySet` consistent with this 14-field baseline.

### 2.4 Runtime Selector

**File:** `services/wecom-service/src/wecom_service/agent_backend.py:23-56`

The selector `select_agent_backend(config, manifests)`:
1. Reads `config["agent_backend"]["mode"]` or `config["agent_backend.mode"]` (line 59-67).
2. Validates the mode is a known `AgentBackendMode` value (line 30-31).
3. Finds the matching manifest by mode (line 33, `_find_manifest` line 70-79).
4. Validates the manifest via `validate_agent_backend_manifest` (line 37-40).
5. Asserts `capabilities.no_channel_io is True` (line 42-45) — **any adapter without `no_channel_io=True` is rejected**.
6. Computes `live_acceptance_allowed = production_ready and requested_mode == AgentBackendMode.HERMES.value` (line 48-49).

The Codex adapter is selected when `agent_backend.mode=codex` and a Codex manifest is present in the `manifests` sequence. The selector returns `AgentBackendSelection(mode="codex", manifest=<codex manifest>, live_acceptance_allowed=False, contract_compatible=True)`.

**Existing test coverage** (`services/wecom-service/tests/test_agent_backend.py:30-48`): `test_codex_future_manifest_is_contract_compatible_not_live_ready` already proves a Codex manifest with `production_ready=False` selects with `live_acceptance_allowed=False`. `test_non_hermes_manifest_production_ready_bypass_is_blocked` (line 39-48) proves even `production_ready=True` non-Hermes modes stay non-live. These tests use synthetic manifest fixtures — Phase 39 should add a test that feeds the **real** `build_codex_manifest()` output through `select_agent_backend`.

## 3. Hermes Adapter Implementation (Reference Pattern)

The Hermes adapter at `packages/backends/hermes/` is the exact structural template for the Codex adapter.

### 3.1 Package structure

```
packages/backends/hermes/
├── pyproject.toml                          # dependencies = []
├── README.md
├── src/inkstatute_backends_hermes/
│   ├── __init__.py                         # public re-exports
│   ├── adapter.py                          # HermesBackendAdapter (9 methods)
│   ├── config.py                           # HermesBackendConfig dataclass
│   ├── manifest.py                         # build_hermes_oneshot_manifest()
│   ├── probe.py                            # HermesCapabilityProbe
│   ├── parity.py                           # parity evaluation (optional)
│   └── runs_api.py                         # opt-in /v1/runs client seam
└── tests/
    ├── test_hermes_backend_adapter.py
    ├── test_capability_probe.py
    ├── test_parity_report.py
    └── test_runs_lane.py
```

The Codex adapter should mirror this exactly:

```
packages/backends/codex/
├── pyproject.toml                          # dependencies = []
├── README.md
├── src/inkstatute_backends_codex/
│   ├── __init__.py
│   ├── adapter.py                          # CodexBackendAdapter (9 methods)
│   ├── config.py                           # CodexBackendConfig
│   ├── manifest.py                         # build_codex_manifest()
│   ├── probe.py                            # CodexCapabilityProbe
│   └── exec_runner.py                      # codex exec subprocess wrapper
└── tests/
    ├── test_codex_backend_adapter.py
    ├── test_capability_probe.py
    └── test_exec_runner.py
```

### 3.2 Manifest builder

**File:** `packages/backends/hermes/src/inkstatute_backends_hermes/manifest.py:17-58`

```python
def build_hermes_oneshot_manifest(config: HermesBackendConfig | None = None) -> AgentBackendManifest:
    resolved = config or HermesBackendConfig()
    return AgentBackendManifest(
        adapter_name="hermes-lawfirm-backend-adapter",
        adapter_version=resolved.adapter_version,
        mode=AgentBackendMode.HERMES,
        backend_version=resolved.backend_version,
        profile_name=resolved.profile_name,
        bundle_id=f"{resolved.profile_name}-profile-bundle",
        capabilities=hermes_oneshot_capabilities(),
        metadata={
            "default_lane": "oneshot",
            "ordinary_wecom_channel_owner": "inkstatute_wecom_service",
            ...
        },
    )

def hermes_oneshot_capabilities() -> AdapterCapabilitySet:
    return AdapterCapabilitySet(
        hook_event_support=[],
        invocation_mode="sync",
        feedback_target_support="message_id",
        session_read_support=False,
        artifact_return_support=True,
        trace_support=True,
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

The Codex equivalent (`build_codex_manifest`) must set `mode=AgentBackendMode.CODEX`, `metadata["production_ready"]=False`, and reduced capabilities. The `metadata["production_ready"]: False` is what Success Criterion 1 verifies.

### 3.3 Adapter submit_run flow

**File:** `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py:96-138`

The Hermes `submit_run`:
1. Requires an injected `HermesOneShotRunner` (Protocol at `adapter.py:27-30`: `async def invoke(self, req: RunRequest) -> HermesOneShotResult`).
2. Calls `await self._runner.invoke(req)` → returns `HermesOneShotResult` (status, result, artifact_refs, trace_refs, raw_payload_ref, metadata).
3. Coerces status to `AsyncTaskState` via `_coerce_task_state` (line 317-325).
4. Builds a `Run` with reference-first metadata (`raw_payload_ref`, `request_content_sha256`, sanitized `runner_metadata`).
5. Stores the run in `self._runs[run_id]` and returns a `RunHandle`.

The Codex adapter follows the same pattern but the "runner" is a subprocess invoker (`CodexExecRunner` Protocol: `async def invoke(self, req) -> CodexExecResult`) that shells out to `codex exec --json`.

### 3.4 Capability probe

**File:** `packages/backends/hermes/src/inkstatute_backends_hermes/probe.py:39-78`

`HermesCapabilityProbe` uses an injected `HermesProbeTransport` Protocol (`get_json(path) -> Mapping`) to call safe read-only endpoints (`/health`, `/v1/capabilities`, `/v1/models`). It returns a `HermesProbeReport` with `ok`, `capabilities` (an `AdapterCapabilitySet`), `models`, `issues`, `fallback_reason`.

For Codex, the probe is simpler: `codex --version` (or `codex exec --help`) via subprocess confirms the CLI is installed. No network endpoints. The probe returns a `CodexProbeReport` with `ok`, `capabilities` (the 14-field `AdapterCapabilitySet`), `codex_version`, `issues`. The capabilities come from the static `codex_prototype_capabilities()` builder (the prototype does not advertise dynamic capabilities).

### 3.5 Key test patterns

**File:** `packages/backends/hermes/tests/test_hermes_backend_adapter.py`

- `test_adapter_exposes_backend_adapter_methods` (line 95-109): asserts all 9 methods are callable.
- `test_submit_and_get_run_use_injected_runner_and_reference_first_metadata` (line 111-128): injects a `FakeRunner`, submits, gets run, asserts reference-first metadata and that raw request content never leaks into `repr(run)`.
- `test_platform_runtime_does_not_import_concrete_hermes_backend` (line 187-191): asserts `platform-runtime` source contains no `inkstatute_backends_hermes` import — **the Codex adapter must add an equivalent test** to preserve thin-layer boundaries.

**File:** `packages/backends/hermes/tests/test_capability_probe.py`

- `test_probe_calls_only_safe_non_mutating_paths` (line 30-45): asserts probe only touches safe paths.
- `test_probe_module_has_no_network_or_run_state_probe_dependency` (line 47-54): source-level assertion that `probe.py` contains no `requests`, `httpx`, `aiohttp`, `subprocess`, `socket(` — **the Codex probe WILL use `subprocess`** (for `codex --version`), so this exact assertion must be adapted: the Codex probe test should assert it only invokes `codex --version` / `codex exec --help` and never `codex exec` with a real prompt (no run-state mutation during probe).

## 4. Codex CLI and `codex exec --json`

### 4.1 Subprocess invocation

The Codex CLI is a host-installed binary (Node.js 22+), **not** a Python package. The adapter invokes it via `subprocess` exactly like Hermes `oneshot_command` (`packages/backends/hermes/src/inkstatute_backends_hermes/config.py:23`).

Recommended default command (`packages/backends/codex/src/inkstatute_backends_codex/config.py`):

```python
@dataclass(frozen=True, slots=True)
class CodexBackendConfig:
    backend_id: str = "codex-prototype"
    backend_version: str = "unknown"
    adapter_version: str = "0.1.0"
    exec_command: tuple[str, ...] = (
        "codex", "exec", "--json",
        "--sandbox", "read-only",
        "--skip-git-repo-check",
    )
    output_last_message_path: str | None = None
    codex_binary: str = "codex"
    metadata: JsonObject = field(default_factory=dict)
```

Flags (from `.planning/research/STACK.md:30`):
- `--json` — emit JSONL event stream to stdout.
- `--sandbox read-only` — safest sandbox for a prototype (no filesystem writes).
- `--skip-git-repo-check` — allow invocation outside a git repo (needed for fixture-driven tests).
- `--ephemeral` — no session persistence (optional, recommended for prototype).
- `-o <file>` / `--output-last-message <file>` — write final assistant message to a file.
- `--output-schema <schema.json>` — JSON Schema draft 2020-12 validated final output (optional for prototype; the adapter can parse JSONL directly).

### 4.2 JSONL event format

`codex exec --json` writes one JSON object per line to stdout. Each line has a top-level `type` field. The event types (from OpenAI Codex `codex-rs/exec/src/exec_events.rs` and `sdk/typescript/src/events.ts`):

| Event type | Fields | Meaning |
|------------|--------|---------|
| `thread.started` | `thread_id` | New thread started (first event) |
| `turn.started` | — | Turn started (prompt sent to model) |
| `item.started` | `item` | New item added (in-progress state) |
| `item.updated` | `item` | Item updated |
| `item.completed` | `item` | Item reached terminal state |
| `turn.completed` | `usage` | Turn completed (typically after assistant response) |
| `turn.failed` | error fields | Turn failed with an error |
| `error` | error fields | Unrecoverable stream error |

`item` is a `ThreadItem` with `id`, `type` (a.k.a. `item_type`), and type-specific fields. Item types: `assistant_message` (a.k.a. `agent_message`), `reasoning`, `command_execution`, `file_change`, `mcp_tool_call`, `web_search`, `todo_list`, `error`.

**Sample success stream:**
```jsonl
{"type":"thread.started","thread_id":"01999ce5-f229-7661-8570-53312bd47ea3"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"OK"}}
{"type":"turn.completed","usage":{"input_tokens":1234,"cached_input_tokens":1024,"output_tokens":12,"reasoning_output_tokens":0}}
```

**Sample failure stream:**
```jsonl
{"type":"thread.started","thread_id":"..."}
{"type":"turn.started"}
{"type":"turn.failed","message":"rate limit exceeded","error":{"kind":"rate_limit","message":"..."}}
```
or a fatal stream error:
```jsonl
{"type":"error","message":"connection refused"}
```

> **Note on field-name drift:** Codex versions use both `item.type` and `item.item_type` for the item discriminator, and both `assistant_message` and `agent_message` for the final message type. The adapter parser must handle both (`item.get("type") or item.get("item_type")`).

### 4.3 Error handling

- Non-zero subprocess exit code → `FAILED` with `ErrorInfo(category=RUNTIME_ERROR, code="codex_exec_nonzero_exit", stage="exec")`.
- `turn.failed` event → `FAILED` with `ErrorInfo` mapped from the event's error fields.
- `error` event (fatal stream error) → `FAILED` with `ErrorInfo`.
- Unparseable stdout line → skip the line but record it in `metadata["codex_unparsed_lines"]` (do not fail the whole run on a single malformed line, unless no `turn.completed`/`turn.failed` is ever seen).
- Subprocess timeout → `FAILED` with `ErrorInfo(code="codex_exec_timeout", retryable=True)`.

### 4.4 Subprocess wrapper design

The adapter should NOT call `subprocess` directly inside `submit_run`. Instead, define a `CodexExecRunner` Protocol (mirroring `HermesOneShotRunner` at `adapter.py:27-30`) so tests can inject a fake runner:

```python
class CodexExecRunner(Protocol):
    async def invoke(self, req: RunRequest) -> "CodexExecResult": ...

@dataclass(frozen=True, slots=True)
class CodexExecResult:
    status: AsyncTaskState | str
    result: AgentResult | None
    thread_id: str | None
    artifact_refs: list[str] = field(default_factory=list)
    raw_payload_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)
```

A concrete `SubprocessCodexExecRunner` implements `invoke` by calling `subprocess.run` (or `asyncio.create_subprocess_exec`) and parsing JSONL. Tests use a `FakeCodexExecRunner` that returns canned `CodexExecResult` instances — **no real `codex` binary is required in CI**.

## 5. AgentResult Schema and Field Mapping

### 5.1 AgentResult definition

**File:** `packages/platform-contract/src/platform_contract/events.py:140-155`

```python
@dataclass(frozen=True, slots=True)
class AgentResult:
    result_id: str
    turn_id: str
    status: AgentResultStatus | str
    reply_type: ReplyType | str
    content: str | None = None
    artifacts: list[Artifact] = field(default_factory=list)
    clarifying_questions: list[str] = field(default_factory=list)
    execution_trace: ExecutionTrace | None = None
    feedback_target: str | None = None
    route_mismatch: bool | None = None
    skill_candidate: SkillCandidate | None = None
    error: ErrorInfo | None = None
    industry_context: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)
```

`AgentResultStatus` (`enums.py:73-78`): `SUCCESS`, `PARTIAL`, `FAILED`, `BLOCKED`, `NEEDS_CLARIFICATION`.
`ReplyType` (`enums.py:81-86`): `TEXT`, `MARKDOWN`, `FILE`, `CARD`, `STATUS_UPDATE`.
`ErrorInfo` (`events.py:84-92`): `category` (`ErrorCategory`: `CONTRACT_ERROR`, `RUNTIME_ERROR`, `CHANNEL_ERROR`), `code`, `message`, `stage`, `retryable`, `details`, `metadata`.

### 5.2 Mapping codex output → AgentResult

| Codex event | AgentResult field |
|-------------|-------------------|
| `item.completed` with `item.type in {"assistant_message","agent_message"}` → `item.text` | `content` |
| `turn.completed` | `status = AgentResultStatus.SUCCESS` |
| `turn.failed` / `error` (first failure) | `status = AgentResultStatus.FAILED`, `error = ErrorInfo(...)` |
| `thread.started` → `thread_id` | `metadata["codex_thread_id"]` |
| `turn.completed` → `usage` | `metadata["codex_usage"]` (input_tokens, output_tokens) |
| `item.completed` with `item.type = "file_change"` | `artifacts` (list of `Artifact`) |
| `item.completed` with `item.type = "command_execution"` | `execution_trace.tool_calls` |
| `item.completed` with `item.type = "reasoning"` | `execution_trace.steps` |

`reply_type` defaults to `ReplyType.TEXT` (or `MARKDOWN` if the content contains markdown fences — keep it simple: `TEXT` for the prototype).
`result_id` = `f"codex-result-{run_id}"`.
`turn_id` = `req.turn.turn_id`.

### 5.3 ExecutionTrace (optional for prototype)

**File:** `packages/platform-contract/src/platform_contract/events.py:183-203`

The prototype can set `execution_trace=None` or build a minimal `ExecutionTrace` with `trace_id=codex_thread_id`, `started_at`/`ended_at` from event timestamps, `steps` from reasoning items, `tool_calls` from command_execution items. Keep it minimal — the success criterion only requires `AgentResult` schema mapping, not a full trace.

## 6. Feature Flag Integration

**File:** `packages/platform-runtime/src/platform_runtime/feature_flags.py:12-32`

```python
@dataclass(frozen=True, slots=True)
class RuntimeFeatureFlags:
    ...
    codex_backend_enabled: bool = False      # line 24
    provider_model_backend_enabled: bool = False  # line 25

    def require_enabled(self, flag_name: str) -> None:
        known_flags = {field.name for field in fields(self)}
        if flag_name not in known_flags:
            raise RuntimeFeatureDisabledError(f"unknown runtime feature flag: {flag_name}")
        if not getattr(self, flag_name):
            raise RuntimeFeatureDisabledError(f"runtime feature flag disabled: {flag_name}")
```

The flag already exists and defaults to `False` (verified by `packages/platform-runtime/tests/test_feature_flags.py:23` and the introspection test at line 26-31). The `require_enabled` method uses `dataclasses.fields` introspection, so it automatically recognizes `codex_backend_enabled` — no changes needed.

**Integration approach:** The Codex adapter's `submit_run` (or the host wiring that constructs the adapter) should call `flags.require_enabled("codex_backend_enabled")` before invoking `codex exec`. Since the adapter package must not import `platform_runtime` (to preserve the thin-layer boundary — see `test_platform_runtime_does_not_import_concrete_hermes_backend`), the flag check belongs in the **host wiring layer** (e.g., `services/wecom-service` or a future composition root), not in `packages/backends/codex/`. The adapter itself can accept an `enabled: bool` constructor param or document that the host gates it. For the prototype, the simplest approach: the adapter's `bootstrap_check` reports `ok=False` with `issues=["codex_backend_disabled"]` when not enabled, and `submit_run` raises `RuntimeError("codex backend disabled")` — mirroring how `HermesRunsClient._require_enabled` works (`runs_api.py:72-74`).

## 7. Selection Gate Impact (SAFETY-01)

The SAFETY-01 fix (Phase 36) is already in place at `services/wecom-service/src/wecom_service/agent_backend.py:48-49`:

```python
production_ready = bool(metadata.get("production_ready", requested_mode == AgentBackendMode.HERMES.value))
live_acceptance_allowed = production_ready and requested_mode == AgentBackendMode.HERMES.value
```

The bypass lines (former line 50-51) were **removed**. Now `live_acceptance_allowed` is `True` only when BOTH (a) `production_ready` is truthy AND (b) `mode == "hermes"`. For the Codex adapter:

- `metadata["production_ready"] = False` → `production_ready = False` → `live_acceptance_allowed = False`. ✅
- Even if someone accidentally sets `production_ready = True`, `mode != "hermes"` → `live_acceptance_allowed = False`. ✅ (verified by `test_non_hermes_manifest_production_ready_bypass_is_blocked` at `test_agent_backend.py:39-48`).

**Conclusion:** The Codex adapter with `production_ready: false` and `no_channel_io: true` is **contract-compatible** (`contract_compatible=True`) but **never live-acceptance-eligible** (`live_acceptance_allowed=False`). This is the intended behavior — the prototype cannot serve live WeCom turns during the parallel V2 human gates. No selection-gate code changes are required in Phase 39.

## 8. Error Normalization on First Failure

"Error normalization on first failure" (Success Criterion 3) means:

1. The adapter scans the JSONL event stream in order.
2. On the **first** failure-bearing event (`turn.failed` or `error`), the adapter constructs a single `AgentResult` with `status=AgentResultStatus.FAILED` and a normalized `ErrorInfo`.
3. No subsequent event can flip the result back to `SUCCESS` — the first failure is terminal for the result status.
4. The `ErrorInfo` is **normalized**: the raw codex error message (which may contain tokens, URLs, file paths) is sanitized into `ErrorInfo.code` (a stable short code), `ErrorInfo.message` (a safe human-readable string), and `ErrorInfo.details` (structured, sanitized fields). Raw payloads must not leak (AGENTS.md safety rule).

**Normalization mapping:**

| Codex failure | `ErrorInfo.category` | `ErrorInfo.code` | `retryable` |
|---------------|----------------------|------------------|-------------|
| `turn.failed` with rate-limit | `RUNTIME_ERROR` | `codex_rate_limit` | `True` |
| `turn.failed` with auth error | `RUNTIME_ERROR` | `codex_auth_error` | `False` |
| `turn.failed` (generic) | `RUNTIME_ERROR` | `codex_turn_failed` | `None` |
| `error` event (stream) | `RUNTIME_ERROR` | `codex_stream_error` | `None` |
| non-zero exit, no failure event | `RUNTIME_ERROR` | `codex_exec_nonzero_exit` | `None` |
| subprocess timeout | `RUNTIME_ERROR` | `codex_exec_timeout` | `True` |
| unparseable / empty stream | `CONTRACT_ERROR` | `codex_empty_stream` | `None` |

The adapter should reuse the `_sanitize_metadata` / `_sanitize_value` pattern from `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py:354-371` to strip `raw_payload`, `content`, `transcript`, `prompt`, `response_body`, `secret`, `token`, `profile_path` keys from any error details before constructing `ErrorInfo`.

## 9. Implementation Plan Guidance (ADAPTER-01)

### Task A: Create Codex adapter package skeleton

**Files to create:**
- `packages/backends/codex/pyproject.toml` — copy from `packages/backends/hermes/pyproject.toml`, change `name = "inkstatute-backends-codex"`, keep `dependencies = []`.
- `packages/backends/codex/README.md` — describe the prototype.
- `packages/backends/codex/src/inkstatute_backends_codex/__init__.py` — public re-exports.
- `packages/backends/codex/src/inkstatute_backends_codex/config.py` — `CodexBackendConfig` dataclass.

### Task B: Manifest + capabilities

**File:** `packages/backends/codex/src/inkstatute_backends_codex/manifest.py`

```python
def build_codex_manifest(config: CodexBackendConfig | None = None) -> AgentBackendManifest:
    resolved = config or CodexBackendConfig()
    return AgentBackendManifest(
        adapter_name="codex-prototype-backend-adapter",
        adapter_version=resolved.adapter_version,
        mode=AgentBackendMode.CODEX,
        backend_version=resolved.backend_version,
        profile_name=None,
        bundle_id=None,
        capabilities=codex_prototype_capabilities(),
        metadata={
            "default_lane": "oneshot",
            "production_ready": False,          # Success Criterion 1
            "no_channel_io_evidence": "Codex adapter returns platform objects only.",
            "ordinary_wecom_channel_owner": "inkstatute_wecom_service",
            "prototype": True,
        },
    )

def codex_prototype_capabilities() -> AdapterCapabilitySet:
    return AdapterCapabilitySet(
        hook_event_support=[],
        invocation_mode="sync",
        feedback_target_support="generated",
        session_read_support=False,
        artifact_return_support=False,         # prototype: reduced
        trace_support=True,
        no_channel_io=True,                    # Success Criterion 1
        run_invocation_modes=["oneshot"],
        stream_event_support=False,
        cancel_support=False,
        approval_support=False,
        live_update_support=False,
        parallel_task_support=False,
        session_memory_support=False,
    )
```

**Test:** `packages/backends/codex/tests/test_codex_manifest.py` — assert `validate_agent_backend_manifest(build_codex_manifest()) == []`, `metadata["production_ready"] is False`, `capabilities.no_channel_io is True`, all 14 capability fields present, and that `select_agent_backend({"agent_backend":{"mode":"codex"}}, [build_codex_manifest()])` returns `live_acceptance_allowed=False`.

### Task C: Capability probe

**File:** `packages/backends/codex/src/inkstatute_backends_codex/probe.py`

```python
class CodexProbeTransport(Protocol):
    def run_version(self) -> str: ...  # returns `codex --version` stdout

@dataclass(frozen=True, slots=True)
class CodexProbeReport:
    ok: bool
    capabilities: AdapterCapabilitySet
    codex_version: str | None = None
    issues: list[CodexProbeIssue] = field(default_factory=list)

class CodexCapabilityProbe:
    def __init__(self, transport: CodexProbeTransport, config: CodexBackendConfig | None = None) -> None: ...
    def probe(self) -> CodexProbeReport: ...
```

The probe calls `codex --version` (via the injected transport — NOT a real subprocess in tests). On success, returns `CodexProbeReport(ok=True, capabilities=codex_prototype_capabilities(), codex_version=...)`. On failure, `ok=False` with an issue. **The probe must never invoke `codex exec` with a prompt** — it is non-mutating.

**Test:** `packages/backends/codex/tests/test_capability_probe.py` — assert probe returns 14-field `AdapterCapabilitySet`, `no_channel_io=True`, and that `build_codex_manifest` validates after probe. Assert probe module source contains no `codex exec` invocation (only `codex --version` / `codex --help`).

### Task D: Exec runner + adapter (submit_run → AgentResult)

**Files:**
- `packages/backends/codex/src/inkstatute_backends_codex/exec_runner.py` — `CodexExecRunner` Protocol, `CodexExecResult`, `SubprocessCodexExecRunner`, `parse_codex_jsonl(lines) -> CodexExecResult`.
- `packages/backends/codex/src/inkstatute_backends_codex/adapter.py` — `CodexBackendAdapter` implementing all 9 `BackendAdapter` methods.

The adapter's `submit_run`:
1. Call `await self._runner.invoke(req)` → `CodexExecResult`.
2. Map to `AgentResult` (per §5.2).
3. Apply error normalization on first failure (per §8).
4. Build `Run` with reference-first metadata (`raw_payload_ref`, `request_content_sha256`, `codex_thread_id`, sanitized `runner_metadata`).
5. Store run, return `RunHandle`.

The other 8 methods mirror Hermes:
- `backend_id()` → `self.config.backend_id`.
- `capabilities()` → `build_codex_manifest(self.config).capabilities`.
- `bootstrap_check()` → `BootstrapStatus(ok=..., backend_id=..., metadata={"invocation_mode":"oneshot","no_channel_io":True,"codex_binary":...})`.
- `get_run(run_id)` → return stored run (raise `KeyError` if unknown).
- `stream_events(run_id)` → yield nothing (prototype: `stream_event_support=False`), like Hermes one-shot (`adapter.py:148-156`).
- `cancel_run(run_id)` → return run with `metadata["reason"]="unsupported_by_codex_prototype"` (like `adapter.py:158-168`).
- `submit_approval(run_id, approval)` → return run with `metadata["reason"]="approval_unsupported_by_codex_prototype"` (like `adapter.py:170-204`).
- `collect_artifacts(run_id)` → return stored artifacts (empty list for prototype if `artifact_return_support=False`).

### Task E: V2 gate wiring

**File:** `scripts/run_v2_gates.py`

Add `codex_backend_src = repo_root / "packages" / "backends" / "codex" / "src"` (after line 57) and add it to:
1. The `contract-test-suite` gate's PYTHONPATH tuple (line 115).
2. A new dedicated gate `codex-backend` (recommended, mirroring how `skill-registry` and `router-service` have their own gates):
   ```python
   Gate(
       "codex-backend",
       (py, "-m", "unittest", "discover", "-s", "packages/backends/codex/tests"),
       (codex_backend_src, platform_src, platform_runtime_src),
   ),
   ```
3. The `compileall` paths (line 122-140): add `"packages/backends/codex/src"`.

### Task F: Tests

**Files:**
- `packages/backends/codex/tests/test_codex_backend_adapter.py` — mirror `test_hermes_backend_adapter.py`.
- `packages/backends/codex/tests/test_capability_probe.py` — mirror `test_capability_probe.py`.
- `packages/backends/codex/tests/test_exec_runner.py` — JSONL parsing, error normalization, first-failure semantics.
- `packages/backends/codex/tests/fixtures/codex_exec_success.jsonl` — sample success stream.
- `packages/backends/codex/tests/fixtures/codex_exec_failure.jsonl` — sample failure stream.

## 10. Test Strategy

### 10.1 Test cases (minimum)

| Test | File | Asserts |
|------|------|---------|
| `test_codex_manifest_validates_with_production_ready_false` | `test_codex_manifest.py` | `validate_agent_backend_manifest == []`, `metadata["production_ready"] is False`, `no_channel_io is True` |
| `test_codex_manifest_selects_as_contract_compatible_not_live` | `test_codex_manifest.py` | `select_agent_backend` returns `live_acceptance_allowed=False`, `contract_compatible=True` |
| `test_codex_capabilities_has_14_fields` | `test_codex_manifest.py` | `len(fields(AdapterCapabilitySet)) == 14` (or count the built capability's set fields) |
| `test_adapter_exposes_backend_adapter_methods` | `test_codex_backend_adapter.py` | all 9 methods callable |
| `test_submit_run_maps_codex_success_to_agent_result` | `test_codex_backend_adapter.py` | inject `FakeCodexExecRunner` returning success → `Run.result.status == SUCCESS`, `content` from `agent_message` item |
| `test_submit_run_normalizes_first_failure` | `test_codex_backend_adapter.py` | inject runner returning `turn.failed` → `Run.result.status == FAILED`, `ErrorInfo.code` set, no success flip |
| `test_submit_run_reference_first_metadata_no_raw_leak` | `test_codex_backend_adapter.py` | `raw_payload_ref` present, raw request content not in `repr(run)` |
| `test_stream_cancel_approval_are_deterministic_non_runner_paths` | `test_codex_backend_adapter.py` | mirror Hermes test |
| `test_bootstrap_reports_codex_binary_and_channel_boundary` | `test_codex_backend_adapter.py` | `BootstrapStatus.metadata["no_channel_io"] is True` |
| `test_platform_runtime_does_not_import_concrete_codex_backend` | `test_codex_backend_adapter.py` | `platform-runtime` source has no `inkstatute_backends_codex` import |
| `test_probe_returns_14_field_capability_set` | `test_capability_probe.py` | probe returns `AdapterCapabilitySet` with 14 fields, `no_channel_io=True` |
| `test_probe_does_not_invoke_codex_exec` | `test_capability_probe.py` | probe module source contains no `codex exec` (only `codex --version`) |
| `test_parse_jsonl_success_stream` | `test_exec_runner.py` | parse `codex_exec_success.jsonl` → `CodexExecResult(status=SUCCEEDED, result.content=...)` |
| `test_parse_jsonl_failure_stream_first_failure_wins` | `test_exec_runner.py` | parse `codex_exec_failure.jsonl` → `FAILED`, first error normalized, no success override |
| `test_parse_jsonl_handles_item_type_alias` | `test_exec_runner.py` | handles both `item.type` and `item.item_type`, both `assistant_message` and `agent_message` |

### 10.2 Fixture-driven approach

All tests use **fixtures** (JSONL files + `FakeCodexExecRunner`), never the real `codex` binary. This matches the AGENTS rule ("Add tests before or with behavior changes, especially for ... fixture replay") and the existing Hermes pattern (`FakeRunner` at `test_hermes_backend_adapter.py:65-71`). CI does not require `codex` to be installed.

### 10.3 Subprocess test isolation

`SubprocessCodexExecRunner` is tested separately with a fake `subprocess.run` (inject a `SubprocessTransport` Protocol: `run(cmd, input) -> (returncode, stdout, stderr)`), never a real shell call. This mirrors `HermesRunsTransport` (`runs_api.py:21-28`).

## 11. V2 Gate Integration

**Approach:** Add a **new dedicated gate** `codex-backend` to `scripts/run_v2_gates.py`, plus add `codex_backend_src` to the `contract-test-suite` gate's PYTHONPATH and `compileall` paths.

This follows the precedent of `skill-registry` and `router-service` gates (each new M2 package gets its own gate, per `.planning/research/PITFALLS.md:463`). The gate count rises from 11 to 12. The `--list` and `--json-summary` modes automatically pick up the new gate.

**No changes** to the `wecom-service` gate are needed — the existing `test_agent_backend.py` tests already cover Codex manifest selection with synthetic fixtures. Phase 39 may optionally add a test there that uses the real `build_codex_manifest()`, but the contract-test-suite gate (which has `codex_backend_src` in its PYTHONPATH) is the better home for that assertion.

## 12. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Codex JSONL field-name drift (`item.type` vs `item.item_type`, `assistant_message` vs `agent_message`) | High | Medium | Parser handles both aliases; fixture tests cover both shapes |
| Adapter accidentally imports `platform_runtime` (breaking thin-layer boundary) | Medium | High | Add `test_platform_runtime_does_not_import_concrete_codex_backend` mirroring Hermes test |
| `production_ready` accidentally set to `True` in Codex manifest | Low | High (live-eligibility) | SAFETY-01 fix already prevents this; add explicit `test_codex_manifest_production_ready_is_false` |
| Real `codex` binary required in CI | Medium | Medium | All tests use fixtures + fake runners; `SubprocessCodexExecRunner` tested via injected transport |
| `subprocess` import in `probe.py` triggers the Hermes-style "no subprocess" source assertion | Medium | Low | Codex probe test asserts only `codex exec` is absent (not `subprocess` itself); `codex --version` is allowed |
| New gate PYTHONPATH missing `platform_runtime_src` → `ModuleNotFoundError` for `RunRequest`/`RunHandle` imports | Medium | High | Include `platform_runtime_src` in the `codex-backend` gate PYTHONPATH (Task E) |
| Codex adapter overclaims capabilities (e.g. `stream_event_support=True`) | Low | Medium | Reuse the Hermes reduced-capability template; test asserts all unsupported flags are `False` |
| Raw codex error messages leak tokens/URLs into `ErrorInfo` | Medium | High (privacy) | Apply `_sanitize_metadata`/`_sanitize_value` to all error details before constructing `ErrorInfo` |
| `compileall` gate fails because `packages/backends/codex/src` not listed | High | Low | Add path to `compileall` in Task E |

## 13. Validation Architecture (Per-Task Verification Map Stub)

| Task | Verification | Gate |
|------|--------------|------|
| A: Package skeleton | `compileall` on `packages/backends/codex/src` passes; `import inkstatute_backends_codex` succeeds | `compileall`, `codex-backend` |
| B: Manifest + capabilities | `validate_agent_backend_manifest(build_codex_manifest()) == []`; `select_agent_backend` returns `live_acceptance_allowed=False`; 14-field capability set | `codex-backend`, `contract-test-suite` |
| C: Capability probe | Probe returns 14-field `AdapterCapabilitySet` with `no_channel_io=True`; probe never invokes `codex exec` | `codex-backend` |
| D: Exec runner + adapter | `submit_run` with fake runner → `AgentResult` schema-valid; first-failure normalization; 9 methods callable; no raw payload leak; `platform-runtime` does not import codex backend | `codex-backend`, `contract-test-suite` |
| E: V2 gate wiring | `scripts/run_v2_gates.py --list` includes `codex-backend`; all 12 gates pass | `run_v2_gates.py` |
| F: Tests | All new tests pass; fixture replay covers success + failure JSONL | `codex-backend` |

### Success Criteria → Verification Map

| Success Criterion | Verification |
|-------------------|--------------|
| SC1: `mode=codex` routes to Codex adapter with `production_ready: false`, `no_channel_io: true` | `test_codex_manifest_validates_with_production_ready_false` + `test_codex_manifest_selects_as_contract_compatible_not_live` in `codex-backend` gate; existing `test_codex_future_manifest_is_contract_compatible_not_live_ready` in `wecom-service` gate |
| SC2: Capability probe passes, returns 14-field `AdapterCapabilitySet` | `test_probe_returns_14_field_capability_set` + `test_codex_capabilities_has_14_fields` in `codex-backend` gate; `test_adapter_capability_set_field_count_unchanged` in `contract-test-suite` gate (frozen baseline) |
| SC3: Fixture-driven `submit_run → AgentResult` with error normalization on first failure | `test_submit_run_maps_codex_success_to_agent_result` + `test_submit_run_normalizes_first_failure` + `test_parse_jsonl_failure_stream_first_failure_wins` in `codex-backend` gate |

---

## References

- `packages/platform-runtime/src/platform_runtime/protocols.py:222-239` — `BackendAdapter` Protocol (9 methods)
- `packages/platform-contract/src/platform_contract/agent_adapter.py:18-33` — `AdapterCapabilitySet` (14 fields)
- `packages/platform-contract/src/platform_contract/agent_adapter.py:36-45` — `AgentBackendManifest`
- `packages/platform-contract/src/platform_contract/agent_adapter.py:48-106` — `validate_agent_backend_manifest`
- `packages/platform-contract/src/platform_contract/events.py:140-155` — `AgentResult`
- `packages/platform-contract/src/platform_contract/events.py:84-92` — `ErrorInfo`
- `packages/platform-contract/src/platform_contract/enums.py:73-78` — `AgentResultStatus`
- `services/wecom-service/src/wecom_service/agent_backend.py:23-56` — `select_agent_backend` runtime selector
- `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py:45-208` — `HermesBackendAdapter` (reference)
- `packages/backends/hermes/src/inkstatute_backends_hermes/manifest.py:17-58` — `build_hermes_oneshot_manifest` (reference)
- `packages/backends/hermes/src/inkstatute_backends_hermes/probe.py:39-78` — `HermesCapabilityProbe` (reference)
- `packages/platform-runtime/src/platform_runtime/feature_flags.py:12-32` — `RuntimeFeatureFlags` (`codex_backend_enabled`)
- `packages/contract-test-suite/tests/test_contract_count_freeze.py:23-45` — contract count freeze (9 methods, 14 fields)
- `services/wecom-service/tests/test_agent_backend.py:30-48` — existing Codex selection tests
- `scripts/run_v2_gates.py:49-142` — V2 gate runner
- `.planning/research/STACK.md:109-129` — M2-01 Codex adapter stack pattern
- `.planning/research/PITFALLS.md:34-50` — selection gate bypass pitfall (closed by SAFETY-01)
- OpenAI Codex CLI: `codex exec --json` JSONL event reference (`sdk/typescript/src/events.ts`, `codex-rs/exec/src/exec_events.rs`)
