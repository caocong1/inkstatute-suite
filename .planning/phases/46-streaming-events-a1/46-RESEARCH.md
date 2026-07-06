# Phase 46: Streaming Events (A1) - Research

**Researched:** 2026-07-06
**Domain:** Async streaming events, SSE/JSONL delta parsing, cancellation propagation, output boundary filtering
**Confidence:** HIGH

## Summary

Phase 46 productizes the frozen `stream_events()` method on the Codex and provider_model adapters. The contract surfaces are already in place and frozen — `BackendAdapter` has 9 methods (including `stream_events`), `AdapterCapabilitySet` has 14 fields (including `stream_event_support`), and `RunEvent` has the fields needed for streaming deltas (`message_delta`, `status`, `error`). Both adapters currently have a no-op `stream_events()` stub (`if False: yield`) and `stream_event_support=False` in their manifests. This phase replaces those stubs with real streaming implementations and wires cancellation propagation through the runtime.

The Codex adapter streams via Codex exec JSON-lines (the `SubprocessCodexExecRunner` already parses JSONL events like `turn.completed`, `item.completed`, `turn.failed`). The provider_model adapter streams via OpenAI/Anthropic SSE chat completion deltas (the `OpenAIClientRunner` currently does non-streaming `chat.completions.create`; it needs a streaming variant using `stream=True`). Both must emit `RunEvent` records with a guaranteed terminal event.

The runtime's `stream()` method already exists and already applies the `AssistantOutputBoundary` to each event. However, it lacks `try/finally` + `aclose()` cleanup for cancellation propagation. The output boundary currently filters by text-content regex matching but has no event-type allowlist. Phase 46 extends the boundary with an allowlist of permitted `RunEventType` values, filtering out raw provider tokens, model names, and error traces at the event-type level.

**Primary recommendation:** Implement `stream_events()` as async generators on both adapters using injected streaming runner protocols (mirroring the existing `CodexExecRunner`/`ProviderModelRunner` injection pattern), emit `RunEvent` records with `event_type=STATE_CHANGED` + `status=SUCCEEDED/FAILED/CANCELLED` as the terminal event, wrap the runtime's `stream()` in `try/finally` with `aclose()`, and add an event-type allowlist to the output boundary — all without modifying any frozen contract surface.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Discuss phase was skipped per `workflow.skip_discuss`. All implementation choices are at Claude's discretion. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Claude's Discretion
All implementation choices are at Claude's discretion — use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STREAM-01 | Codex + provider_model adapters yield SSE streaming events via frozen `stream_events()` with guaranteed terminal event (completed/failed/cancelled) | §Architecture Patterns (adapter streaming), §Code Examples (RunEvent terminal event), §Common Pitfalls (terminal event naming) |
| STREAM-02 | Client cancellation propagates through runtime → adapter → provider with `aclose()` cleanup (no zombie runs) | §Architecture Patterns (cancellation propagation), §Code Examples (try/finally + aclose), §Common Pitfalls (zombie runs) |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- **Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads.** Stream events must use `raw_payload_ref`-style references, not inline content. [VERIFIED: AGENTS.md §Safety And Privacy]
- **Contract logs should prefer references such as `raw_payload_ref`.** Stream event payloads must not store sensitive full text by default. [VERIFIED: AGENTS.md §Safety And Privacy]
- **Backend/gateway/system notices are not user-facing.** Streaming events pass through `AssistantOutputBoundary` before reaching channels — backend noise filtered. [VERIFIED: AGENTS.md §Safety And Privacy]
- **Add tests before or with behavior changes**, especially for schemas, mappers, event ordering, dedupe, and fixture replay. [VERIFIED: AGENTS.md §Coding Rules]
- **Prefer structured parsers and schema validators over ad hoc string parsing.** Use JSONL/SSE structured parsing, not regex on raw streams. [VERIFIED: AGENTS.md §Coding Rules]
- **Do not introduce a new service, database, queue, or runtime dependency.** `dependencies = []` invariant must be preserved on both adapter packages. [VERIFIED: AGENTS.md §Coding Rules, pyproject.toml]
- **Keep changes scoped to the active GSD phase and its plan.** [VERIFIED: AGENTS.md §Coding Rules]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Codex JSONL stream parsing | Backend adapter (codex) | — | Adapter owns provider-specific protocol parsing; runner is injected |
| OpenAI/Anthropic SSE delta parsing | Backend adapter (provider_model) | — | Adapter owns provider-specific protocol parsing; runner is injected |
| RunEvent emission (terminal event guarantee) | Backend adapter | — | Adapter is the authority for run lifecycle events |
| Cancellation propagation (aclose) | Platform runtime | Backend adapter | Runtime wraps stream in try/finally; adapter cleans up provider connection |
| Output boundary event-type allowlist | Platform runtime (output_boundary) | — | Runtime owns the boundary between backend and channels |
| Feature flag gating | Platform runtime (feature_flags) | — | `streaming_lane_enabled` gates the runtime stream lane |

## Standard Stack

### Core

No new external packages are installed. This phase uses only the existing Python standard library and existing project packages. [VERIFIED: codebase grep — `dependencies = []` in both adapter pyproject.toml files]

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `asyncio` | 3.14+ | Async generators, `aclose()`, cancellation | Already used throughout the runtime [VERIFIED: codebase] |
| Python stdlib `json` | 3.14+ | JSONL/SSE line parsing | Already used in `exec_runner.py` and `openai_runner.py` [VERIFIED: codebase] |
| `platform-contract` | existing | `RunEvent`, `RunEventType`, `AsyncTaskState`, `ErrorInfo` | Frozen contract — no modifications [VERIFIED: test_contract_freeze.py] |
| `platform-runtime` | existing | `RunEvent` (protocol), `DefaultRunRuntime`, `DefaultAssistantOutputBoundary` | Runtime owns stream() and output boundary [VERIFIED: codebase] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `inkstatute_backends_codex` | existing | Codex adapter + exec runner | Codex JSONL streaming |
| `inkstatute_backends_provider_model` | existing | provider_model adapter + OpenAI runner | OpenAI SSE streaming |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Injected runner protocol for streaming | Direct SDK calls in adapter | Rejected — breaks `dependencies = []` invariant and testability. Use injected `StreamingCodexExecRunner` / `StreamingProviderModelRunner` protocols. |
| New `RunEventType.COMPLETED` enum value | `RunEventType.STATE_CHANGED` + `status=SUCCEEDED` | Must use existing enum — `RunEventType` is frozen in `enums.py` (hash-frozen by `test_contract_freeze.py`). Terminal event = `STATE_CHANGED` with `status=SUCCEEDED/FAILED/CANCELLED`. |

**Installation:**
```bash
# No packages to install — this phase uses only existing project packages and Python stdlib
```

**Version verification:** Not applicable — no new packages installed. Python 3.14.6 confirmed on the target machine. [VERIFIED: `python3 --version`]

## Package Legitimacy Audit

> No external packages are installed in this phase. All work uses existing project packages and Python stdlib. The `dependencies = []` invariant on both adapter packages must be preserved. [VERIFIED: `packages/backends/codex/pyproject.toml:15`, `packages/backends/provider_model/pyproject.toml:15`]

## Architecture Patterns

### System Architecture Diagram

```
Client (channel)
    │
    ▼
DefaultRunRuntime.stream(run_id)
    │  [feature_flags.require_enabled("streaming_lane_enabled")]
    │
    ▼
try:
    async for event in backend.stream_events(run_id):
        │
        ▼
        _apply_output_boundary(event)
            │  [event-type allowlist filter]
            │  [text-content regex filter (existing)]
            │
            ▼
        yield bounded_event  →  ChannelAdapter
    │
    ▼
    [terminal event: STATE_CHANGED + SUCCEEDED/FAILED/CANCELLED]
finally:
    await stream_generator.aclose()  →  backend cleanup  →  provider cleanup
```

### Recommended Project Structure

```
packages/backends/codex/src/inkstatute_backends_codex/
├── adapter.py           # CodexBackendAdapter.stream_events() — real implementation
├── exec_runner.py       # Add StreamingCodexExecRunner protocol + JSONL stream parser
├── manifest.py          # stream_event_support=True (conditional on config)
└── config.py            # (no change needed — config already has exec_command)

packages/backends/provider_model/src/inkstatute_backends_provider_model/
├── adapter.py           # ProviderModelBackendAdapter.stream_events() — real implementation
├── openai_runner.py     # Add StreamingProviderModelRunner protocol + SSE delta parser
├── manifest.py          # stream_event_support=True (conditional on config)
└── config.py            # (no change needed)

packages/platform-runtime/src/platform_runtime/
├── runtime.py           # stream() — add try/finally + aclose()
├── output_boundary.py   # Add event-type allowlist to DefaultAssistantOutputBoundary
└── ports.py             # (no change — AssistantOutputBoundary Protocol is not frozen by count)
```

### Pattern 1: Injected Streaming Runner Protocol

**What:** Both adapters already use an injected runner protocol for `submit_run()` (`CodexExecRunner` / `ProviderModelRunner`). Add a parallel streaming runner protocol for `stream_events()`.

**When to use:** Always — this is the established pattern. The adapter never calls provider SDKs directly.

**Example:**
```python
# Source: existing pattern in packages/backends/codex/src/inkstatute_backends_codex/adapter.py:26-29
class StreamingCodexExecRunner(Protocol):
    """Injected streaming runner for Codex exec JSONL events."""

    async def stream(self, req: RunRequest) -> AsyncIterator[CodexStreamEvent]: ...
```
[VERIFIED: codebase — `CodexExecRunner` Protocol at adapter.py:26-29]

### Pattern 2: Terminal Event Guarantee

**What:** Every `stream_events()` call must end with a terminal `RunEvent` — `event_type=STATE_CHANGED` with `status` set to `SUCCEEDED`, `FAILED`, or `CANCELLED`.

**When to use:** Always — this is STREAM-01's core requirement.

**Example:**
```python
# Source: existing pattern in packages/platform-runtime/src/platform_runtime/fakes.py:136-137
# FakeBackendAdapter already emits STATE_CHANGED events for each status transition
async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]:
    run = self._require_run(run_id)
    # ... yield intermediate events (MESSAGE_DELTA, STEP_STARTED, etc.) ...
    # Terminal event — always emitted
    yield RunEvent(
        event_id=f"event-{run_id}-terminal",
        run_id=run_id,
        event_type=RunEventType.STATE_CHANGED.value,
        occurred_at=self._clock.now(),
        seq=next_seq,
        payload={"status": _status_value(terminal_status)},
        metadata={"source": "adapter_stream_terminal"},
    )
```
[VERIFIED: fakes.py:136-137 — FakeBackendAdapter emits STATE_CHANGED for each status; test at test_run_runtime_lifecycle.py:84-90 asserts seq and status values]

### Pattern 3: try/finally + aclose() Cancellation Propagation

**What:** The runtime's `stream()` method wraps the backend's async generator in `try/finally`, calling `aclose()` on the generator in the `finally` block. This propagates `GeneratorExit` into the adapter, which cleans up the provider connection.

**When to use:** Always — this is STREAM-02's core requirement.

**Example:**
```python
# Source: Python stdlib async generator cleanup pattern
async def stream(self, run_id: str) -> AsyncIterator[RunEvent]:
    self.feature_flags.require_enabled("run_runtime_enabled")
    self.feature_flags.require_enabled("streaming_lane_enabled")
    gen = self.backend.stream_events(run_id)
    try:
        async for event in gen:
            bounded_event = self._apply_output_boundary(event)
            if bounded_event is not None:
                yield bounded_event
    finally:
        await gen.aclose()
```
[ASSUMED — Python stdlib `aclose()` pattern; the current runtime.py:264-270 does NOT have try/finally, this is what Phase 46 adds]

### Pattern 4: Event-Type Allowlist in Output Boundary

**What:** Extend `DefaultAssistantOutputBoundary` with an allowlist of permitted `RunEventType` values. Events with non-allowlisted types are dropped (returned as `None` from the boundary) before reaching channels.

**When to use:** For all streaming events — Success Criterion 3 requires filtering out raw provider tokens, model names, and error traces.

**Example:**
```python
# Source: existing output_boundary.py pattern + RunEventType enum
_ALLOWED_EVENT_TYPES = frozenset({
    RunEventType.STATE_CHANGED.value,
    RunEventType.MESSAGE_DELTA.value,
    RunEventType.STEP_STARTED.value,
    RunEventType.STEP_COMPLETED.value,
    RunEventType.ARTIFACT_CREATED.value,
    RunEventType.APPROVAL_REQUESTED.value,
    # ERROR events are NOT in the allowlist — error traces filtered out
    # TOOL_CALL_STARTED/COMPLETED are NOT in the allowlist — raw provider internals
})
```
[VERIFIED: RunEventType enum at enums.py:100-109; existing boundary at output_boundary.py:28-76]

### Anti-Patterns to Avoid

- **Modifying frozen contract surfaces:** `BackendAdapter` (9 methods), `AdapterCapabilitySet` (14 fields), `RunEventType` enum, `RunEvent` dataclass, and all `platform-contract` schema files are hash-frozen. Do NOT add new event types, fields, or methods. [VERIFIED: test_contract_count_freeze.py, test_contract_freeze.py]
- **Calling provider SDKs directly in the adapter:** Breaks `dependencies = []` and testability. Use injected runner protocols. [VERIFIED: existing pattern in both adapters]
- **Inlining raw content in stream events:** Violates `raw_payload_ref` privacy discipline. Use references. [VERIFIED: AGENTS.md §Safety And Privacy]
- **Using "completed" as terminal status:** The contract uses `SUCCEEDED` (not "completed"). The existing test explicitly asserts `assertNotIn("completed", ...)`. [VERIFIED: test_run_runtime_lifecycle.py:90]
- **Skipping the terminal event on error/cancellation:** Every stream must end with a terminal event, even on exception. Use `try/finally` inside the adapter's `stream_events()` to emit a terminal `CANCELLED` or `FAILED` event on cleanup. [VERIFIED: STREAM-01 success criterion]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSONL line parsing | Custom line splitter | `json.loads()` per line (existing `parse_codex_jsonl` pattern) | Already handles edge cases, field aliases, unparsed lines [VERIFIED: exec_runner.py:95-191] |
| SSE delta parsing | Custom SSE parser | `openai` SDK streaming or line-by-line `data:` prefix parsing | SSE has edge cases (multi-line data, comments, keepalive pings) [ASSUMED] |
| Error normalization | New error mapping | Reuse existing `_normalize_error` / `_normalize_api_error` patterns | Already handles rate limits, auth, connection errors with sanitized messages [VERIFIED: exec_runner.py:199-238, openai_runner.py:213-247] |
| Output boundary text filtering | New regex rules | Extend existing `DefaultAssistantOutputBoundary` with event-type allowlist | Existing rules already cover provider_leak, api_error, function_trace, debug_trace [VERIFIED: output_boundary.py:82-113] |
| RunEvent construction | Custom event objects | Use frozen `RunEvent` dataclass from `platform_runtime.protocols` | Contract-frozen, already has all needed fields [VERIFIED: protocols.py:137-145] |

**Key insight:** The contract surfaces and helper patterns already exist from v1.6. This phase is implementation-only — wiring existing patterns together, not building new infrastructure.

## Common Pitfalls

### Pitfall 1: Terminal Event Naming Mismatch

**What goes wrong:** The phase description says "completed/failed/cancelled" but the contract enum `AsyncTaskState` uses `SUCCEEDED` (not "completed").
**Why it happens:** The ROADMAP phase description uses informal language; the contract uses precise enum values.
**How to avoid:** Use `AsyncTaskState.SUCCEEDED`, `AsyncTaskState.FAILED`, `AsyncTaskState.CANCELLED` for terminal events. The terminal event is `RunEvent(event_type=STATE_CHANGED, status=SUCCEEDED/FAILED/CANCELLED)`. The existing test at `test_run_runtime_lifecycle.py:90` explicitly asserts `assertNotIn("completed", ...)`.
**Warning signs:** Tests failing with "completed not in status values" or contract validation errors.

### Pitfall 2: Two RunEvent Definitions

**What goes wrong:** There are two `RunEvent` dataclasses — one in `platform_runtime/protocols.py` (simpler, with `payload`/`metadata` dicts) and one in `platform_contract/events.py` (richer, with `status`/`message_delta`/`error` fields). The adapters import from `platform_runtime` (the protocols.py version).
**Why it happens:** The protocols.py `RunEvent` is the runtime Protocol surface; the events.py `RunEvent` is the contract schema binding. The runtime's `_apply_output_boundary` works with the protocols.py version (checking `event.payload` and `event.metadata`).
**How to avoid:** Adapters must yield the `platform_runtime.RunEvent` (from `protocols.py`), which has `event_id`, `run_id`, `event_type`, `occurred_at`, `seq`, `payload`, `metadata`. Put streaming data (message deltas, status) in `payload` dict. The runtime's boundary filter checks `event.payload` and `event.metadata` for visible text using `_VISIBLE_TEXT_KEYS = ("message_delta", "visible_text", "text", "content", "delta")`.
**Warning signs:** `AttributeError: 'RunEvent' has no attribute 'message_delta'` — means you're using the wrong `RunEvent` class.

### Pitfall 3: Async Generator aclose() Not Propagating

**What goes wrong:** Client cancels the stream but the provider connection stays open (zombie run).
**Why it happens:** The runtime's `stream()` method doesn't call `aclose()` on the backend's async generator when the client disconnects.
**How to avoid:** Wrap the `async for` loop in `try/finally` and call `await gen.aclose()` in the `finally` block. The adapter's `stream_events()` must also handle `GeneratorExit` by cleaning up the provider connection (closing the subprocess stdout pipe or the HTTP streaming response).
**Warning signs:** Tests showing open file handles, subprocess processes lingering after cancellation, or provider API connections not closed.

### Pitfall 4: Modifying Frozen Contract Surfaces

**What goes wrong:** Adding a new `RunEventType.COMPLETED` or new `AdapterCapabilitySet` field breaks the contract freeze tests.
**Why it happens:** The phase description mentions "completed" which doesn't exist in the enum, tempting addition.
**How to avoid:** Do NOT modify `enums.py`, `events.py`, `agent_adapter.py`, `protocols.py` (method count), or any schema JSON. All needed types and fields already exist. `stream_event_support` is already field #9 in `AdapterCapabilitySet`. `stream_events()` is already method #6 in `BackendAdapter`. `STATE_CHANGED` + `MESSAGE_DELTA` + `ERROR` are already in `RunEventType`.
**Warning signs:** `test_contract_count_freeze.py` or `test_contract_freeze.py` failing.

### Pitfall 5: Streaming Lane Feature Flag

**What goes wrong:** `stream()` raises `RuntimeFeatureDisabledError` because `streaming_lane_enabled` defaults to `False`.
**Why it happens:** The runtime requires `streaming_lane_enabled=True` (in addition to `run_runtime_enabled=True`) before calling `backend.stream_events()`.
**How to avoid:** Tests must construct `RuntimeFeatureFlags(run_runtime_enabled=True, streaming_lane_enabled=True)`. The `streaming_lane_enabled` flag is NOT one of the 9 M3 flags — it's a v1.1 flag from Phase 10. The `web_sse_channel_enabled` flag (Phase 45) gates the Web SSE channel adapter (Phase 57), NOT streaming events.
**Warning signs:** `RuntimeFeatureDisabledError: runtime feature flag disabled: streaming_lane_enabled`

### Pitfall 6: dependencies = [] Invariant

**What goes wrong:** CI or contract tests fail because the adapter package now requires `openai` or `anthropic` SDK.
**Why it happens:** Importing provider SDKs at module top level adds a runtime dependency.
**How to avoid:** Use lazy imports (`importlib.import_module("openai")` inside the runner method) for real SDK paths. Tests inject fake transports. The existing `OpenAIClientRunner` already follows this pattern. [VERIFIED: openai_runner.py:291-334]

## Code Examples

### Codex Adapter stream_events() Implementation

```python
# Source: existing adapter pattern (adapter.py:130-133 stub) + fakes.py:157-160 reference
# The adapter yields RunEvent records from the platform_runtime.protocols module

from platform_runtime import RunEvent  # protocols.py version: payload/metadata dicts

async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]:
    run = self._require_run(run_id)
    if self._streaming_runner is None:
        # Fallback: emit a single terminal event from the stored run
        yield self._terminal_event(run_id, run.status, seq=0)
        return

    seq = 0
    try:
        async for delta in self._streaming_runner.stream(self._run_requests[run_id]):
            yield RunEvent(
                event_id=self._id_factory.new_id("run-event"),
                run_id=run_id,
                event_type=delta.event_type,
                occurred_at=self._clock.now(),
                seq=seq,
                payload=delta.payload,
                metadata={"source": "codex_stream"},
            )
            seq += 1
    except Exception as exc:
        yield RunEvent(
            event_id=self._id_factory.new_id("run-event"),
            run_id=run_id,
            event_type=RunEventType.STATE_CHANGED.value,
            occurred_at=self._clock.now(),
            seq=seq,
            payload={"status": AsyncTaskState.FAILED.value, "error": _sanitize_error(exc)},
            metadata={"source": "codex_stream_error"},
        )
        return
    # Terminal event
    yield RunEvent(
        event_id=self._id_factory.new_id("run-event"),
        run_id=run_id,
        event_type=RunEventType.STATE_CHANGED.value,
        occurred_at=self._clock.now(),
        seq=seq,
        payload={"status": _status_value(run.status)},
        metadata={"source": "codex_stream_terminal"},
    )
```
[VERIFIED: existing stub at adapter.py:130-133; FakeBackendAdapter pattern at fakes.py:157-160; RunEvent shape at protocols.py:137-145]

### Provider Model Adapter stream_events() with SSE Deltas

```python
# Source: existing OpenAIClientRunner pattern (openai_runner.py:311-342) + SSE streaming
# The streaming runner uses stream=True on chat.completions.create

async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]:
    run = self._require_run(run_id)
    if self._streaming_runner is None:
        yield self._terminal_event(run_id, run.status, seq=0)
        return

    seq = 0
    try:
        async for delta in self._streaming_runner.stream(self._run_requests[run_id]):
            # delta.message_delta contains the SSE content chunk
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
    except Exception as exc:
        # Terminal FAILED event on exception
        yield self._error_terminal_event(run_id, seq, exc)
        return
    # Terminal SUCCEEDED event
    yield RunEvent(
        event_id=f"event-{run_id}-terminal",
        run_id=run_id,
        event_type=RunEventType.STATE_CHANGED.value,
        occurred_at=self._clock.now(),
        seq=seq,
        payload={"status": AsyncTaskState.SUCCEEDED.value},
        metadata={"source": "provider_model_sse_terminal"},
    )
```
[VERIFIED: existing non-streaming pattern at openai_runner.py:311-342; RunEventType.MESSAGE_DELTA at enums.py:104]

### Runtime stream() with try/finally + aclose()

```python
# Source: existing runtime.py:264-270 + Python stdlib aclose() pattern
async def stream(self, run_id: str) -> AsyncIterator[RunEvent]:
    self.feature_flags.require_enabled("run_runtime_enabled")
    self.feature_flags.require_enabled("streaming_lane_enabled")
    gen = self.backend.stream_events(run_id)
    try:
        async for event in gen:
            bounded_event = self._apply_output_boundary(event)
            if bounded_event is not None:
                yield bounded_event
    finally:
        await gen.aclose()
```
[VERIFIED: existing stream() at runtime.py:264-270; aclose() is Python stdlib AsyncIterator cleanup]

### Output Boundary Event-Type Allowlist

```python
# Source: existing output_boundary.py:28-76 + RunEventType enum at enums.py:100-109
# Extend DefaultAssistantOutputBoundary.apply() with event-type filtering

_ALLOWED_STREAM_EVENT_TYPES = frozenset({
    RunEventType.STATE_CHANGED.value,
    RunEventType.MESSAGE_DELTA.value,
    RunEventType.STEP_STARTED.value,
    RunEventType.STEP_COMPLETED.value,
    RunEventType.ARTIFACT_CREATED.value,
    RunEventType.APPROVAL_REQUESTED.value,
})

class DefaultAssistantOutputBoundary:
    def apply(self, visibility_target, text=None, event_metadata=None, event_type=None):
        # Event-type allowlist: drop events not in the allowlist
        if event_type is not None and event_type not in _ALLOWED_STREAM_EVENT_TYPES:
            return BoundaryDecision(
                action=BoundaryAction.BLOCK,
                visible_text=None,
                audit_metadata={"rule_id": "event_type_not_allowed", "event_type": event_type},
                reason="event_type_not_allowed",
            )
        # ... existing text-content regex filtering continues ...
```
[VERIFIED: existing boundary at output_boundary.py:28-76; RunEventType values at enums.py:100-109; the `apply` method signature at ports.py:34-40 is a Protocol — adding an optional `event_type` parameter is additive and does not break the Protocol]

### Manifest Capability Update

```python
# Source: existing manifest.py:36-54
def codex_prototype_capabilities(*, stream_event_support: bool = False) -> AdapterCapabilitySet:
    return AdapterCapabilitySet(
        # ... all 14 fields unchanged ...
        stream_event_support=stream_event_support,  # was hardcoded False
        # ...
    )
```
[VERIFIED: manifest.py:36-54; AdapterCapabilitySet at agent_adapter.py:18-33 — `stream_event_support` is field #9, defaults to False]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `stream_events()` no-op stub (`if False: yield`) | Real async generator yielding RunEvent records | Phase 46 | Adapters produce streaming events |
| `stream_event_support=False` hardcoded | Configurable via manifest builder parameter | Phase 46 | Operator can enable streaming per-adapter |
| Runtime `stream()` without try/finally | Runtime `stream()` with try/finally + aclose() | Phase 46 | Cancellation propagates, no zombie runs |
| Output boundary text-only filtering | Output boundary text + event-type allowlist | Phase 46 | Raw provider tokens, model names, error traces filtered by event type |
| Non-streaming `chat.completions.create` | Streaming `chat.completions.create(stream=True)` | Phase 46 | SSE deltas for provider_model adapter |

**Deprecated/outdated:**
- `if False: yield` stub pattern in both adapters — replaced with real async generators. [VERIFIED: codex adapter.py:130-133, provider_model adapter.py:129-132]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `aclose()` on an async generator propagates `GeneratorExit` into the generator body, allowing cleanup | Architecture Patterns, Code Examples | If wrong, cancellation won't propagate — but this is Python stdlib behavior, very low risk |
| A2 | The `AssistantOutputBoundary.apply()` Protocol can accept an optional `event_type` parameter without breaking the Protocol contract | Code Examples | If wrong, need a separate event-type filter step before calling `apply()`. The Protocol is not count-frozen, only `BackendAdapter`/`ChannelAdapter`/`RouterPort`/`SkillRegistryPort` are count-frozen. |
| A3 | The OpenAI SDK supports `stream=True` returning an async iterator of SSE chunks | Architecture Patterns | If wrong, need raw HTTP SSE parsing. The `openai` SDK is lazy-imported and not installed in CI, so tests use fake transports regardless. |
| A4 | The Codex exec subprocess streams JSONL lines to stdout incrementally (not buffered until exit) | Architecture Patterns | If Codex buffers all output until process exit, streaming events would all arrive at once. The existing `SubprocessCodexExecRunner` uses `subprocess.run` (buffered). For real streaming, need `subprocess.Popen` with line-by-line stdout reading. |
| A5 | The adapter needs to store the original `RunRequest` to pass to the streaming runner | Code Examples | If wrong, the streaming runner can't reconstruct the provider request. The adapter currently doesn't store `RunRequest` — only stores `Run`. Need to add a `_run_requests: dict[str, RunRequest]` store. |

## Open Questions

1. **Should the streaming runner be a separate protocol or extend the existing runner?**
   - What we know: The existing `CodexExecRunner` has `async def invoke(req) -> CodexExecResult` (non-streaming). The existing `ProviderModelRunner` has `async def invoke(req) -> ProviderModelExecResult` (non-streaming).
   - What's unclear: Whether to add a `stream()` method to the existing protocol or create a separate `StreamingCodexExecRunner` protocol.
   - Recommendation: Create a separate streaming runner protocol. The existing `invoke()` returns a final result; streaming is a different lifecycle. The adapter can accept both runners — `submit_run()` uses the non-streaming runner, `stream_events()` uses the streaming runner. This preserves backward compatibility.

2. **Should `submit_run()` still be used when streaming is enabled, or should `stream_events()` be the primary entry point?**
   - What we know: The current flow is `submit_run()` → `RunHandle` → `stream_events(run_id)`. The adapter stores the run and then streams events for it.
   - What's unclear: Whether `submit_run()` should still complete the full run (as it does now) or just register the run for streaming.
   - Recommendation: Keep `submit_run()` as-is for non-streaming callers. For streaming, the caller still calls `submit_run()` first (to get a `run_id`), then `stream_events(run_id)`. The adapter should store the `RunRequest` so the streaming runner can use it. The streaming runner runs the provider call; `submit_run()` can either run the non-streaming runner or just register the run.

3. **Does the Codex exec subprocess stream JSONL incrementally or buffer until exit?**
   - What we know: The existing `SubprocessCodexExecRunner` uses `subprocess.run` (buffered — waits for process exit, then parses all lines).
   - What's unclear: Whether `codex exec --json` streams lines to stdout incrementally.
   - Recommendation: For real streaming, use `asyncio.create_subprocess_exec` with line-by-line stdout reading. For tests, inject a fake streaming transport that yields lines incrementally. This is an implementation detail of the streaming runner, not the adapter.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14+ | Async generators, aclose() | ✓ | 3.14.6 | — |
| `openai` SDK | provider_model real streaming | ✗ (lazy-imported) | — | Fake transport in tests; real SDK path not exercised in CI |
| `anthropic` SDK | Anthropic SSE streaming (Phase 48) | ✗ | — | Not needed for Phase 46 — Phase 48 adds AnthropicRunner |
| `codex` CLI binary | Codex real streaming | ✗ | — | Fake streaming transport in tests |

**Missing dependencies with no fallback:**
- None — all tests use injected fake transports. Real SDK/CLI paths are never exercised in CI (lazy import pattern). [VERIFIED: existing pattern in both runners]

**Missing dependencies with fallback:**
- `openai` SDK — not installed; tests inject `FakeOpenAITransport`. Real streaming uses `importlib.import_module("openai")` inside the runner method. [VERIFIED: openai_runner.py:322-324]
- `codex` CLI — not installed; tests inject fake transport. [VERIFIED: exec_runner.py:44-54]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Python `unittest` (stdlib, no external test framework) |
| Config file | None — tests use `unittest.IsolatedAsyncioTestCase` for async tests |
| Quick run command | `python3 -m unittest discover -s packages/backends/codex/tests -v` |
| Full suite command | `python3 scripts/run_v2_gates.py` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STREAM-01 | Codex adapter yields RunEvent records with terminal event | unit | `python3 -m unittest packages.backends.codex.tests.test_adapter -v` | ✅ exists (extend) |
| STREAM-01 | provider_model adapter yields RunEvent records with terminal event | unit | `python3 -m unittest packages.backends.provider_model.tests.test_adapter -v` | ✅ exists (extend) |
| STREAM-01 | Terminal event is STATE_CHANGED + SUCCEEDED/FAILED/CANCELLED | unit | `python3 -m unittest packages.backends.codex.tests.test_stream_events -v` | ❌ Wave 0 |
| STREAM-01 | Codex JSONL stream parsing yields intermediate MESSAGE_DELTA events | unit | `python3 -m unittest packages.backends.codex.tests.test_streaming_runner -v` | ❌ Wave 0 |
| STREAM-01 | provider_model SSE delta parsing yields MESSAGE_DELTA events | unit | `python3 -m unittest packages.backends.provider_model.tests.test_streaming_runner -v` | ❌ Wave 0 |
| STREAM-02 | Runtime stream() wraps in try/finally with aclose() | unit | `python3 -m unittest packages.platform_runtime.tests.test_run_runtime_lifecycle -v` | ✅ exists (extend) |
| STREAM-02 | Client cancellation propagates to adapter (GeneratorExit) | unit | `python3 -m unittest packages.platform_runtime.tests.test_stream_cancellation -v` | ❌ Wave 0 |
| STREAM-02 | No zombie runs after cancellation | unit | `python3 -m unittest packages.platform_runtime.tests.test_stream_cancellation -v` | ❌ Wave 0 |
| SC-3 | Output boundary event-type allowlist filters non-allowed types | unit | `python3 -m unittest packages.platform_runtime.tests.test_output_boundary -v` | ✅ exists (extend) |
| SC-3 | ERROR and TOOL_CALL events filtered by allowlist | unit | `python3 -m unittest packages.platform_runtime.tests.test_output_boundary -v` | ✅ exists (extend) |
| SAFETY-02 | BackendAdapter still has 9 methods, AdapterCapabilitySet still has 14 fields | contract | `python3 -m unittest packages.contract_test_suite.tests.test_contract_count_freeze -v` | ✅ exists (must stay green) |
| SAFETY-02 | platform-contract schema hash baseline unchanged | contract | `python3 -m unittest packages.contract_test_suite.tests.test_contract_freeze -v` | ✅ exists (must stay green) |

### Sampling Rate

- **Per task commit:** `python3 -m unittest discover -s packages/backends/codex/tests -v && python3 -m unittest discover -s packages/backends/provider_model/tests -v && python3 -m unittest discover -s packages/platform-runtime/tests -v`
- **Per wave merge:** `python3 scripts/run_v2_gates.py`
- **Phase gate:** Full 19-gate V2 suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `packages/backends/codex/tests/test_stream_events.py` — covers STREAM-01 (Codex streaming with terminal event)
- [ ] `packages/backends/codex/tests/test_streaming_runner.py` — covers STREAM-01 (JSONL stream parsing)
- [ ] `packages/backends/codex/tests/fixtures/codex_exec_stream.jsonl` — sample streaming JSONL fixture
- [ ] `packages/backends/provider_model/tests/test_stream_events.py` — covers STREAM-01 (provider_model streaming with terminal event)
- [ ] `packages/backends/provider_model/tests/test_streaming_runner.py` — covers STREAM-01 (SSE delta parsing)
- [ ] `packages/platform-runtime/tests/test_stream_cancellation.py` — covers STREAM-02 (aclose propagation, no zombie runs)
- [ ] `packages/platform-runtime/tests/test_output_boundary.py` — extend with event-type allowlist tests (file exists, needs new test cases)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (no auth changes in this phase) |
| V3 Session Management | no | — (no session changes) |
| V4 Access Control | no | — (no access control changes) |
| V5 Input Validation | yes | Structured JSONL/SSE parsing with `json.loads()` — no ad hoc string parsing |
| V6 Cryptography | no | — (no crypto changes) |

### Known Threat Patterns for Streaming Events

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Raw provider tokens in stream events | Information Disclosure | Output boundary event-type allowlist + text-content regex filtering (existing `provider_leak` rule) |
| Model names leaking to channels | Information Disclosure | `_sanitize_model_name()` returns "redacted" (existing); output boundary `provider_leak` regex rule |
| Error traces with stack traces | Information Disclosure | Output boundary `debug_trace` hard-block rule; `_sanitize_error_message()` strips URLs/tokens/paths |
| Zombie runs after cancellation | Denial of Service | `try/finally` + `aclose()` propagation; adapter cleans up provider connection on `GeneratorExit` |
| Inline raw content in events | Information Disclosure | Use `raw_payload_ref` references, never inline content (AGENTS.md §Safety And Privacy) |

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `packages/platform-runtime/src/platform_runtime/protocols.py` — BackendAdapter Protocol (9 methods), RunEvent dataclass
- Codebase inspection: `packages/platform-contract/src/platform_contract/events.py` — RunEvent contract schema (richer version)
- Codebase inspection: `packages/platform-contract/src/platform_contract/enums.py` — RunEventType, AsyncTaskState enums
- Codebase inspection: `packages/platform-contract/src/platform_contract/agent_adapter.py` — AdapterCapabilitySet (14 fields)
- Codebase inspection: `packages/backends/codex/src/inkstatute_backends_codex/adapter.py` — CodexBackendAdapter with stream_events stub
- Codebase inspection: `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py` — ProviderModelBackendAdapter with stream_events stub
- Codebase inspection: `packages/platform-runtime/src/platform_runtime/runtime.py` — DefaultRunRuntime.stream() method
- Codebase inspection: `packages/platform-runtime/src/platform_runtime/output_boundary.py` — DefaultAssistantOutputBoundary
- Codebase inspection: `packages/platform-runtime/src/platform_runtime/fakes.py` — FakeBackendAdapter streaming pattern
- Codebase inspection: `packages/contract-test-suite/tests/test_contract_count_freeze.py` — frozen method/field counts
- Codebase inspection: `packages/contract-test-suite/tests/test_contract_freeze.py` — frozen schema hash baseline
- Codebase inspection: `packages/backends/codex/src/inkstatute_backends_codex/exec_runner.py` — JSONL parsing, error normalization
- Codebase inspection: `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py` — OpenAI runner, lazy import, error normalization
- Codebase inspection: `packages/platform-runtime/src/platform_runtime/feature_flags.py` — RuntimeFeatureFlags (streaming_lane_enabled)
- Codebase inspection: `.planning/REQUIREMENTS.md` — STREAM-01, STREAM-02, SAFETY-02
- Codebase inspection: `.planning/ROADMAP.md` — Phase 46 goal and success criteria

### Secondary (MEDIUM confidence)
- v1.6 research: `.planning/milestones/v1.6-phases/39-codex-adapter-prototype/39-RESEARCH.md` — adapter pattern, manifest structure
- v1.6 research: `.planning/milestones/v1.6-phases/40-provider-model-adapter-prototype/40-RESEARCH.md` — provider_model adapter pattern, output boundary rules

### Tertiary (LOW confidence)
- Python stdlib `aclose()` behavior on async generators — [ASSUMED] based on training knowledge, not verified in this session

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages, all existing project code inspected directly
- Architecture: HIGH — all patterns verified by reading existing source code
- Pitfalls: HIGH — all pitfalls discovered by reading existing tests and contract freeze mechanisms
- Code examples: HIGH — based on existing codebase patterns, not training data

**Research date:** 2026-07-06
**Valid until:** 2026-08-06 (30 days — stable codebase, no external dependencies)
