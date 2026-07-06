# Phase 46: Streaming Events (A1) - Pattern Map

**Mapped:** 2026-07-06
**Files analyzed:** 14 (8 source modifications, 6 test modifications)
**Analogs found:** 14 / 14

> **Path correction:** The additional_context listed adapter paths under
> `packages/platform-runtime/src/platform_runtime/adapters/`. The actual paths
> are `packages/backends/codex/src/inkstatute_backends_codex/` and
> `packages/backends/provider_model/src/inkstatute_backends_provider_model/`.
> All references below use the verified real paths.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `packages/backends/codex/src/inkstatute_backends_codex/adapter.py` | provider | streaming | `packages/platform-runtime/src/platform_runtime/fakes.py` (`FakeBackendAdapter.stream_events`) | exact (same role + same data flow) |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py` | provider | streaming | `packages/platform-runtime/src/platform_runtime/fakes.py` (`FakeBackendAdapter.stream_events`) | exact (same role + same data flow) |
| `packages/backends/codex/src/inkstatute_backends_codex/exec_runner.py` | service | streaming | `packages/backends/codex/src/inkstatute_backends_codex/exec_runner.py` (`SubprocessCodexExecRunner.invoke` + `parse_codex_jsonl`) | exact (same file, extending existing pattern) |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py` | service | streaming | `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py` (`OpenAIClientRunner.invoke` + `parse_openai_response`) | exact (same file, extending existing pattern) |
| `packages/platform-runtime/src/platform_runtime/runtime.py` | controller | streaming | `packages/platform-runtime/src/platform_runtime/runtime.py` (`stream()` lines 264-270) | exact (same method, adding try/finally) |
| `packages/platform-runtime/src/platform_runtime/output_boundary.py` | middleware | event-driven | `packages/platform-runtime/src/platform_runtime/output_boundary.py` (`DefaultAssistantOutputBoundary.apply`) | exact (same class, adding allowlist) |
| `packages/backends/codex/src/inkstatute_backends_codex/manifest.py` | config | request-response | `packages/backends/codex/src/inkstatute_backends_codex/manifest.py` (`codex_prototype_capabilities`) | exact (same function, parameterizing field) |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/manifest.py` | config | request-response | `packages/backends/provider_model/src/inkstatute_backends_provider_model/manifest.py` (`provider_model_prototype_capabilities`) | exact (same function, parameterizing field) |
| `packages/backends/codex/src/inkstatute_backends_codex/__init__.py` | config | request-response | `packages/backends/codex/src/inkstatute_backends_codex/__init__.py` (existing exports) | exact (same file, adding exports) |
| `packages/backends/provider_model/src/inkstatute_backends_provider_model/__init__.py` | config | request-response | `packages/backends/provider_model/src/inkstatute_backends_provider_model/__init__.py` (existing exports) | exact (same file, adding exports) |
| `packages/backends/codex/tests/test_adapter.py` | test | streaming | `packages/backends/codex/tests/test_adapter.py` (`CodexBackendAdapterTests`) | exact (same file, adding stream tests) |
| `packages/backends/codex/tests/test_runner.py` | test | streaming | `packages/backends/codex/tests/test_runner.py` (`SubprocessCodexExecRunnerTests`) | exact (same file, adding streaming runner tests) |
| `packages/backends/provider_model/tests/test_adapter.py` | test | streaming | `packages/backends/provider_model/tests/test_adapter.py` | exact (same file, adding stream tests) |
| `packages/backends/provider_model/tests/test_runner.py` | test | streaming | `packages/backends/provider_model/tests/test_runner.py` (`OpenAIClientRunnerTests`) | exact (same file, adding streaming runner tests) |
| `packages/platform-runtime/tests/test_run_runtime_lifecycle.py` | test | streaming | `packages/platform-runtime/tests/test_run_runtime_lifecycle.py` (`test_zero_channel_runtime_creates_polls_and_streams_fake_run`) | exact (same file, adding cancellation tests) |
| `packages/platform-runtime/tests/test_output_boundary.py` | test | event-driven | `packages/platform-runtime/tests/test_output_boundary.py` (`RuntimeStreamBoundaryTests`) | exact (same file, adding allowlist tests) |

## Pattern Assignments

### `packages/backends/codex/src/inkstatute_backends_codex/adapter.py` (provider, streaming)

**Analog:** `packages/platform-runtime/src/platform_runtime/fakes.py` — `FakeBackendAdapter.stream_events` (lines 157-160) and `FakeBackendAdapter._append_event` (lines 217-240)

The existing `stream_events()` stub to replace is at lines 130-133:

```python
async def stream_events(self, run_id: str) -> AsyncIterator[Any]:
    self._require_run(run_id)
    if False:
        yield
```

**Reference async generator pattern** (fakes.py:157-160):
```python
async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]:
    self._require_run(run_id)
    for event in tuple(self.events[run_id]):
        yield event
```

**RunEvent construction pattern** (fakes.py:230-238) — copy this shape for each yielded event:
```python
event = RunEvent(
    event_id=self._id_factory.new_id("run-event"),
    run_id=run_id,
    event_type=str(event_type),
    occurred_at=self._clock.now(),
    seq=seq,
    payload=event_payload,
    metadata={"backend_id": self._backend_id},
)
```

**Terminal event pattern** (fakes.py:226-227) — payload must include `status` + `raw_payload_ref`:
```python
event_payload = {"status": status_value, "raw_payload_ref": f"fixture://runs/{run_id}/events/{seq}"}
```

**Imports to add** (adapter.py:8 currently has `AsyncIterator, Protocol`):
```python
from platform_contract.enums import RunEventType  # add to existing enums import line 11
from platform_runtime import RunEvent  # add to existing platform_runtime import block lines 13-20
```

**Injected runner Protocol pattern** — mirror the existing `CodexExecRunner` (adapter.py:26-29):
```python
class CodexExecRunner(Protocol):
    async def invoke(self, req: RunRequest) -> "CodexExecResult": ...
```
Add a `StreamingCodexExecRunner` Protocol with an `async def stream(self, req: RunRequest) -> AsyncIterator[...]` method.

**Error handling pattern** — wrap the async-for loop in `try/except` and emit a terminal `FAILED` event on exception (see RESEARCH.md Code Examples lines 328-338). Use `_coerce_task_state` (adapter.py:186-194) for status coercion.

**Key constraints:**
- Yield `platform_runtime.RunEvent` (from `protocols.py:137-145`), NOT `platform_contract.events.RunEvent`.
- Terminal event = `RunEventType.STATE_CHANGED` + `status=SUCCEEDED/FAILED/CANCELLED` in payload.
- The adapter currently does NOT store `_run_requests` — the `submit_run` method (lines 86-125) stores runs in `self._runs` but not the original `RunRequest`. The streaming runner needs the request, so `submit_run` must be extended to store `self._run_requests[run_id] = req` (or the streaming runner must accept the stored `Run`).

---

### `packages/backends/provider_model/src/inkstatute_backends_provider_model/adapter.py` (provider, streaming)

**Analog:** `packages/platform-runtime/src/platform_runtime/fakes.py` — `FakeBackendAdapter.stream_events` (lines 157-160)

The existing `stream_events()` stub to replace is at lines 129-132:

```python
async def stream_events(self, run_id: str) -> AsyncIterator[Any]:
    self._require_run(run_id)
    if False:
        yield
```

**Imports to add** (adapter.py:8 currently has `AsyncIterator, Protocol`):
```python
from platform_contract.enums import RunEventType  # add to existing enums import line 11
from platform_runtime import RunEvent  # add to existing platform_runtime import block lines 13-20
```

**Injected runner Protocol pattern** — mirror the existing `ProviderModelRunner` (adapter.py:26-29):
```python
class ProviderModelRunner(Protocol):
    async def invoke(self, req: RunRequest) -> "ProviderModelExecResult": ...
```
Add a `StreamingProviderModelRunner` Protocol with an `async def stream(self, req: RunRequest) -> AsyncIterator[...]` method.

**SSE delta event pattern** — each SSE chunk yields a `MESSAGE_DELTA` event (RESEARCH.md lines 368-376):
```python
yield RunEvent(
    event_id=f"event-{run_id}-{seq:03d}",
    run_id=run_id,
    event_type=RunEventType.MESSAGE_DELTA.value,
    occurred_at=self._clock.now(),
    seq=seq,
    payload={"message_delta": delta.content, "status": "running"},
    metadata={"source": "provider_model_sse"},
)
```

**Same `_run_requests` storage gap** as the Codex adapter — `submit_run` (lines 86-124) does not store the original request. Must extend to store `self._run_requests[run_id] = req`.

---

### `packages/backends/codex/src/inkstatute_backends_codex/exec_runner.py` (service, streaming)

**Analog:** Same file — `SubprocessCodexExecRunner` (lines 279-355) and `parse_codex_jsonl` (lines 95-191)

**Existing non-streaming runner pattern** (exec_runner.py:279-355):
```python
class SubprocessCodexExecRunner:
    def __init__(
        self,
        config: CodexBackendConfig | None = None,
        transport: SubprocessTransport | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.config = config or CodexBackendConfig()
        self.transport = transport or _SystemSubprocessTransport()
        self.timeout = timeout

    async def invoke(self, req: RunRequest) -> CodexExecResult:
        command = list(self.config.exec_command) + [req.turn.content or ""]
        try:
            returncode, stdout, stderr = self.transport.run(
                tuple(command), input_text=None, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return CodexExecResult(status=AsyncTaskState.FAILED, ...)
        lines = stdout.splitlines()
        result = parse_codex_jsonl(lines, run_id="exec", turn_id=req.turn.turn_id)
        ...
        return result
```

**JSONL parsing pattern** (exec_runner.py:95-191) — `parse_codex_jsonl` already handles:
- `turn.completed` → `SUCCEEDED` (line 138-140)
- `turn.failed` → `FAILED` + normalized error (line 142-145)
- `item.completed`/`item.updated` → extracts message content (line 130-136)
- First failure is terminal (line 142 `not failed` guard)
- Empty stream → `CONTRACT_ERROR` with `codex_empty_stream` (line 152-160)

**Streaming extension approach:** Add an `AsyncSubprocessTransport` Protocol and a `StreamingSubprocessCodexExecRunner` class with an `async def stream(self, req: RunRequest) -> AsyncIterator[...]` method that reads stdout line-by-line via `asyncio.create_subprocess_exec` and yields parsed JSONL events as they arrive. Reuse `parse_codex_jsonl` logic but yield per-event instead of accumulating.

**Transport Protocol pattern** (exec_runner.py:44-54):
```python
class SubprocessTransport(Protocol):
    def run(self, command: tuple[str, ...], input_text: str | None, timeout: float | None) -> tuple[int, str, str]: ...
```
Add an `AsyncSubprocessTransport` Protocol with `async def start_stream(...)` returning an async line iterator.

**Error normalization** — reuse `_normalize_error` (exec_runner.py:199-238) and `_sanitize_message` (exec_runner.py:241-247) for streaming error events.

**Imports** (exec_runner.py:22-37) — add `import asyncio` and `from typing import AsyncIterator`.

**Exports** (exec_runner.py:358-362) — add new streaming classes to `__all__`.

---

### `packages/backends/provider_model/src/inkstatute_backends_provider_model/openai_runner.py` (service, streaming)

**Analog:** Same file — `OpenAIClientRunner` (lines 290-365) and `parse_openai_response` (lines 84-167)

**Existing non-streaming runner pattern** (openai_runner.py:311-342):
```python
async def invoke(self, req: RunRequest) -> ProviderModelExecResult:
    request_payload: JsonObject = {
        "model": self.config.model_name,
        "messages": [{"role": "user", "content": req.turn.content}],
        "timeout": self.config.timeout,
    }
    try:
        if self._transport is not None:
            response = await self._transport.create_chat_completion(request_payload)
        else:
            openai_module = importlib.import_module("openai")
            AsyncOpenAI = getattr(openai_module, "AsyncOpenAI")
            cred = self._api_key_resolver(self.config.api_key_ref)
            client = AsyncOpenAI(api_key=cred, base_url=self.config.api_base_url)
            completion = await client.chat.completions.create(
                model=self.config.model_name,
                messages=[{"role": "user", "content": req.turn.content}],
            )
            response = _completion_to_dict(completion)
    except Exception as exc:
        return self._build_error_result(exc, req)
    return parse_openai_response(response, run_id=..., turn_id=...)
```

**Streaming extension approach:** Add a `StreamingOpenAITransport` Protocol with `async def create_streaming_chat_completion(self, request_payload) -> AsyncIterator[JsonObject]` and a `StreamingOpenAIClientRunner` class. The real SDK path uses `stream=True`:
```python
stream = await client.chat.completions.create(
    model=self.config.model_name,
    messages=[{"role": "user", "content": req.turn.content}],
    stream=True,
)
async for chunk in stream:
    yield chunk  # SSE delta dict
```

**Lazy import pattern** (openai_runner.py:322-324) — MUST preserve:
```python
openai_module = importlib.import_module("openai")
AsyncOpenAI = getattr(openai_module, "AsyncOpenAI")
```
Never import `openai` at module top level (preserves `dependencies = []`).

**Fake transport pattern** (openai_runner.py:60-74) — add a `FakeStreamingOpenAITransport` for tests:
```python
class FakeOpenAITransport:
    def __init__(self, response=None, error=None): ...
    async def create_chat_completion(self, request_payload): ...
```

**Error normalization** — reuse `_normalize_api_error` (openai_runner.py:213-247) and `_sanitize_error_message` (openai_runner.py:203-210) for streaming error events.

**Model name sanitization** — reuse `_sanitize_model_name` (openai_runner.py:183-190) which always returns `"redacted"`.

**Exports** (openai_runner.py:368-373) — add new streaming classes to `__all__`.

---

### `packages/platform-runtime/src/platform_runtime/runtime.py` (controller, streaming)

**Analog:** Same file — `stream()` method (lines 264-270) and `_apply_output_boundary` (lines 403-434)

**Current stream() to modify** (runtime.py:264-270):
```python
async def stream(self, run_id: str) -> AsyncIterator[RunEvent]:
    self.feature_flags.require_enabled("run_runtime_enabled")
    self.feature_flags.require_enabled("streaming_lane_enabled")
    async for event in self.backend.stream_events(run_id):
        bounded_event = self._apply_output_boundary(event)
        if bounded_event is not None:
            yield bounded_event
```

**Target pattern** (RESEARCH.md lines 397-410) — wrap in try/finally + aclose():
```python
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

**Feature flag gating** (runtime.py:265-266) — preserve both `require_enabled` calls. `streaming_lane_enabled` defaults to `False` (feature_flags.py:15).

**Output boundary application** (runtime.py:403-434) — `_apply_output_boundary` calls `self.output_boundary.apply(visibility_target="ordinary_user", text=visible_text, event_metadata=event.metadata)`. The event-type allowlist addition to `output_boundary.py` may require passing `event.event_type` here — check if the boundary's `apply` signature gains an `event_type` parameter.

**Visible text extraction** (runtime.py:503-512) — `_VISIBLE_TEXT_KEYS = ("message_delta", "visible_text", "text", "content", "delta")`. Streaming deltas use `message_delta` key in payload, which is already covered.

---

### `packages/platform-runtime/src/platform_runtime/output_boundary.py` (middleware, event-driven)

**Analog:** Same file — `DefaultAssistantOutputBoundary.apply` (lines 28-76)

**Current apply() method** (output_boundary.py:31-76):
```python
def apply(self, visibility_target, text=None, event_metadata=None) -> BoundaryDecision:
    del visibility_target, event_metadata
    visible_text = "" if text is None else str(text)
    normalized = visible_text.lower()
    matched = _first_match(_HARD_BLOCK_RULES, normalized)
    if matched is not None:
        return BoundaryDecision(action=BoundaryAction.BLOCK, ...)
    matched = _first_match(_REWRITE_RULES, normalized)
    ...
    return BoundaryDecision(action=BoundaryAction.ALLOW, ...)
```

**Event-type allowlist to add** (RESEARCH.md lines 419-437):
```python
_ALLOWED_STREAM_EVENT_TYPES = frozenset({
    RunEventType.STATE_CHANGED.value,
    RunEventType.MESSAGE_DELTA.value,
    RunEventType.STEP_STARTED.value,
    RunEventType.STEP_COMPLETED.value,
    RunEventType.ARTIFACT_CREATED.value,
    RunEventType.APPROVAL_REQUESTED.value,
    # ERROR events NOT allowed — error traces filtered
    # TOOL_CALL_STARTED/COMPLETED NOT allowed — raw provider internals
})
```

**Signature extension** — add optional `event_type=None` parameter to `apply()`. The `AssistantOutputBoundary` Protocol (ports.py:34-40) is NOT count-frozen, so adding an optional parameter is additive and safe (RESEARCH.md Assumption A2).

**Imports to add** (output_boundary.py:11 currently imports only `JsonObject`):
```python
from platform_contract.enums import RunEventType
```

**Decision pattern** (output_boundary.py:20-25) — reuse `BoundaryDecision` dataclass:
```python
@dataclass(frozen=True, slots=True)
class BoundaryDecision:
    action: BoundaryAction
    visible_text: str | None = None
    audit_metadata: JsonObject = field(default_factory=dict)
    reason: str = "business_output"
```

**Block decision for non-allowlisted types** (RESEARCH.md lines 431-437):
```python
if event_type is not None and event_type not in _ALLOWED_STREAM_EVENT_TYPES:
    return BoundaryDecision(
        action=BoundaryAction.BLOCK,
        visible_text=None,
        audit_metadata={"rule_id": "event_type_not_allowed", "event_type": event_type},
        reason="event_type_not_allowed",
    )
```

**Runtime integration** — `_apply_output_boundary` (runtime.py:403-409) must pass `event.event_type` to the boundary's `apply()` call. The existing call is:
```python
decision = self.output_boundary.apply(
    visibility_target="ordinary_user",
    text=visible_text,
    event_metadata=event.metadata,
)
```
Add `event_type=event.event_type` parameter.

---

### `packages/backends/codex/src/inkstatute_backends_codex/manifest.py` (config, request-response)

**Analog:** Same file — `codex_prototype_capabilities` (lines 36-54)

**Current hardcoded `stream_event_support=False`** (manifest.py:48):
```python
def codex_prototype_capabilities() -> AdapterCapabilitySet:
    return AdapterCapabilitySet(
        ...
        stream_event_support=False,  # line 48 — hardcoded
        ...
    )
```

**Target pattern** (RESEARCH.md lines 446-451) — parameterize:
```python
def codex_prototype_capabilities(*, stream_event_support: bool = False) -> AdapterCapabilitySet:
    return AdapterCapabilitySet(
        ...  # all 14 fields unchanged
        stream_event_support=stream_event_support,
        ...
    )
```

**`build_codex_manifest`** (manifest.py:14-33) — optionally pass `stream_event_support` from config. The `CodexBackendConfig` (config.py) may need a `stream_event_support` field, or the manifest builder accepts it as a parameter.

---

### `packages/backends/provider_model/src/inkstatute_backends_provider_model/manifest.py` (config, request-response)

**Analog:** Same file — `provider_model_prototype_capabilities` (lines 37-55)

**Current hardcoded `stream_event_support=False`** (manifest.py:49):
```python
def provider_model_prototype_capabilities() -> AdapterCapabilitySet:
    return AdapterCapabilitySet(
        ...
        stream_event_support=False,  # line 49 — hardcoded
        ...
    )
```

**Target pattern** — same as Codex: parameterize with `*, stream_event_support: bool = False`.

---

### `packages/backends/codex/src/inkstatute_backends_codex/__init__.py` (config, request-response)

**Analog:** Same file (lines 1-23)

**Current exports** (__init__.py:3-7):
```python
from .adapter import CodexBackendAdapter, CodexExecResult, CodexExecRunner
from .exec_runner import SubprocessCodexExecRunner, SubprocessTransport, parse_codex_jsonl
```

**Add** new streaming runner classes/protocols to the import and `__all__` list (lines 9-23). Example: `StreamingCodexExecRunner`, `AsyncSubprocessTransport`.

---

### `packages/backends/provider_model/src/inkstatute_backends_provider_model/__init__.py` (config, request-response)

**Analog:** Same file (lines 1-34)

**Current exports** (__init__.py:6-11):
```python
from .openai_runner import (
    FakeOpenAITransport,
    OpenAIClientRunner,
    OpenAITransport,
    parse_openai_response,
)
```

**Add** new streaming runner classes/protocols. Example: `StreamingOpenAIClientRunner`, `StreamingOpenAITransport`, `FakeStreamingOpenAITransport`.

---

### `packages/backends/codex/tests/test_adapter.py` (test, streaming)

**Analog:** Same file — `CodexBackendAdapterTests` (lines 109-181) and `test_stream_cancel_and_approval_are_deterministic_non_runner_paths` (lines 149-164)

**Existing stream test pattern** (test_adapter.py:149-164):
```python
async def test_stream_cancel_and_approval_are_deterministic_non_runner_paths(self) -> None:
    runner = FakeCodexExecRunner()
    adapter = CodexBackendAdapter(runner=runner)
    handle = await adapter.submit_run(make_request())
    events = [event async for event in adapter.stream_events(handle.run_id)]
    ...
    self.assertEqual(events, [])  # currently asserts empty — will change
```

**Fake runner pattern** (test_adapter.py:46-69):
```python
class FakeCodexExecRunner:
    def __init__(self) -> None:
        self.calls: list[RunRequest] = []
    async def invoke(self, req: RunRequest) -> CodexExecResult:
        self.calls.append(req)
        return CodexExecResult(status=AsyncTaskState.SUCCEEDED, ...)
```
Add a `FakeStreamingCodexExecRunner` that yields scripted delta events.

**Test assertions to add:**
- Stream yields `MESSAGE_DELTA` events with content
- Stream ends with terminal `STATE_CHANGED` + `SUCCEEDED` event
- `assertNotIn("completed", ...)` — terminal status must be `SUCCEEDED` not "completed" (test_run_runtime_lifecycle.py:90 pattern)
- Error path yields terminal `FAILED` event
- Cancellation via `aclose()` propagates (no zombie)

**Imports** (test_adapter.py:6-20) — add `RunEventType` to the enums import and `RunEvent` if needed.

---

### `packages/backends/codex/tests/test_runner.py` (test, streaming)

**Analog:** Same file — `SubprocessCodexExecRunnerTests` (lines 133-168) and `FakeSubprocessTransport` (lines 108-120)

**Existing fake transport pattern** (test_runner.py:108-120):
```python
class FakeSubprocessTransport:
    def __init__(self, returncode=0, stdout="", stderr=""): ...
    def run(self, command, input_text, timeout) -> tuple[int, str, str]:
        return (self.returncode, self.stdout, self.stderr)
```

**Fixture loading pattern** (test_runner.py:46-47):
```python
def _load_fixture(name: str) -> list[str]:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8").splitlines()
```
Reuse `codex_exec_success.jsonl` and `codex_exec_failure.jsonl` fixtures for streaming tests.

**Add** `FakeAsyncSubprocessTransport` that yields lines asynchronously, and tests asserting incremental event delivery (not buffered).

---

### `packages/backends/provider_model/tests/test_adapter.py` (test, streaming)

**Analog:** `packages/backends/codex/tests/test_adapter.py` — `CodexBackendAdapterTests` (lines 109-181)

**Test pattern** — mirror the Codex adapter test structure. Add `FakeStreamingProviderModelRunner` that yields SSE delta dicts. Assert:
- `MESSAGE_DELTA` events with delta content
- Terminal `STATE_CHANGED` + `SUCCEEDED`
- Error path yields terminal `FAILED`
- Model name never appears in events (sanitized to `"redacted"`)

---

### `packages/backends/provider_model/tests/test_runner.py` (test, streaming)

**Analog:** Same file — `OpenAIClientRunnerTests` (lines 144-210) and `FakeOpenAITransport` (openai_runner.py:60-74)

**Existing fake transport pattern** (test_runner.py:145-147):
```python
runner = OpenAIClientRunner(transport=FakeOpenAITransport(response=response))
result = await runner.invoke(make_request())
```

**Add** `FakeStreamingOpenAITransport` that yields SSE chunk dicts asynchronously. Test that the streaming runner yields `MESSAGE_DELTA` events with content from each chunk, and a terminal `SUCCEEDED` event.

**Error test pattern** (test_runner.py:157-175):
```python
runner = OpenAIClientRunner(transport=FakeOpenAITransport(error=FakeRateLimitError("rate limit for gpt-4")))
result = await runner.invoke(make_request())
self.assertEqual(result.result.error.code, "provider_model_rate_limit")
self.assertNotIn("gpt-4", result.result.error.message or "")
```
Mirror for streaming: assert error during stream yields terminal `FAILED` with sanitized message.

---

### `packages/platform-runtime/tests/test_run_runtime_lifecycle.py` (test, streaming)

**Analog:** Same file — `test_zero_channel_runtime_creates_polls_and_streams_fake_run` (lines 388-405)

**Existing stream test pattern** (test_run_runtime_lifecycle.py:388-405):
```python
async def test_zero_channel_runtime_creates_polls_and_streams_fake_run(self) -> None:
    backend = FakeBackendAdapter()
    runtime = DefaultRunRuntime(
        backend=backend, channels=(),
        feature_flags=RuntimeFeatureFlags(run_runtime_enabled=True, streaming_lane_enabled=True),
    )
    created = await runtime.create_run(make_run_request())
    events = [event async for event in runtime.stream(created.run_id)]
    self.assertEqual([event.seq for event in events], [0, 1, 2])
```

**Add cancellation/aclose tests:**
- Client breaks out of `async for` early → `aclose()` called on backend generator → backend cleanup hook invoked
- Use a `FakeBackendAdapter` subclass with a `stream_aclosed` flag to verify `aclose()` propagation
- Assert no zombie events after cancellation

**Feature flag pattern** (test_run_runtime_lifecycle.py:393-396):
```python
feature_flags=RuntimeFeatureFlags(
    run_runtime_enabled=True,
    streaming_lane_enabled=True,
),
```

---

### `packages/platform-runtime/tests/test_output_boundary.py` (test, event-driven)

**Analog:** Same file — `RuntimeStreamBoundaryTests` (lines 140-353)

**Existing boundary test pattern** (test_output_boundary.py:155-174):
```python
async def test_stream_allows_business_delta_unchanged_and_does_not_mutate_backend_event(self) -> None:
    backend = FakeBackendAdapter()
    runtime = DefaultRunRuntime(backend=backend, feature_flags=RuntimeFeatureFlags(
        run_runtime_enabled=True, streaming_lane_enabled=True,
    ))
    run = await runtime.create_run(make_run_request())
    text = "Under the agreement, the buyer may request cure before termination."
    backend_event = backend.append_message_delta(run.run_id, text, metadata={"scripted": True})
    events = [event async for event in runtime.stream(run.run_id)]
    streamed = events[-1]
    self.assertEqual(streamed.payload["message_delta"], text)
    self.assertEqual(streamed.metadata["output_boundary"]["action"], BoundaryAction.ALLOW.value)
```

**Add event-type allowlist tests:**
- `ERROR` event type is blocked (not in allowlist)
- `TOOL_CALL_STARTED`/`TOOL_CALL_COMPLETED` event types are blocked
- `STATE_CHANGED`, `MESSAGE_DELTA`, `STEP_STARTED`, `STEP_COMPLETED`, `ARTIFACT_CREATED`, `APPROVAL_REQUESTED` are allowed
- Non-allowlisted events have `output_boundary.action == BoundaryAction.BLOCK.value` and `reason == "event_type_not_allowed"`

**Imports** (test_output_boundary.py:7) — `RunEventType` already imported.

## Shared Patterns

### 1. RunEvent Construction (all adapter streaming code)

Every yielded event must use the `platform_runtime.RunEvent` dataclass (protocols.py:137-145), NOT the `platform_contract.events.RunEvent`:

```python
from platform_runtime import RunEvent

RunEvent(
    event_id=f"event-{run_id}-{seq:03d}",  # or id_factory.new_id("run-event")
    run_id=run_id,
    event_type=str(RunEventType.STATE_CHANGED.value),  # or MESSAGE_DELTA
    occurred_at=clock.now(),
    seq=seq,
    payload={"status": status_value, "raw_payload_ref": ref, "message_delta": text},
    metadata={"source": "...", "backend_id": backend_id},
)
```

**Critical:** `event_type` must be a string (use `.value` on the enum). The runtime's `_event_visible_text` checks `event.payload` and `event.metadata` for keys in `_VISIBLE_TEXT_KEYS = ("message_delta", "visible_text", "text", "content", "delta")`.

### 2. Terminal Event Guarantee (all adapter streaming code)

Every `stream_events()` async generator MUST end with a terminal event:
- Success: `RunEventType.STATE_CHANGED` + `payload={"status": AsyncTaskState.SUCCEEDED.value}`
- Failure: `RunEventType.STATE_CHANGED` + `payload={"status": AsyncTaskState.FAILED.value, "error": ...}`
- Cancellation: `RunEventType.STATE_CHANGED` + `payload={"status": AsyncTaskState.CANCELLED.value}`

Use `try/except/finally` inside the adapter's `stream_events()` to guarantee the terminal event even on exception. Never use "completed" as a status — the contract uses `SUCCEEDED` (test_run_runtime_lifecycle.py:90 asserts `assertNotIn("completed", ...)`).

### 3. Injected Runner Protocol (both adapters)

Mirror the existing injection pattern — define a `Protocol` class, accept it in `__init__`, store as `self._streaming_runner`:

```python
class StreamingCodexExecRunner(Protocol):
    async def stream(self, req: RunRequest) -> AsyncIterator[...]: ...
```

Tests inject fake runners. Real runners use lazy imports for SDK paths. This preserves `dependencies = []` on both adapter packages.

### 4. Privacy / Sanitization (all adapter streaming code)

- Never inline raw content in stream event payloads — use `raw_payload_ref` references
- Reuse existing `_sanitize_metadata` (adapter.py:209-218), `_sanitize_text` (adapter.py:233-240), `_sanitize_message` (exec_runner.py:241-247), `_sanitize_error_message` (openai_runner.py:203-210)
- Model names always redacted to `"redacted"` via `_sanitize_model_name` (openai_runner.py:183-190)
- Error messages stripped of URLs, tokens, file paths, model names

### 5. Feature Flag Gating (runtime stream)

`stream()` requires TWO flags enabled (runtime.py:265-266):
- `run_runtime_enabled=True`
- `streaming_lane_enabled=True` (defaults to `False`, feature_flags.py:15)

Tests must construct `RuntimeFeatureFlags(run_runtime_enabled=True, streaming_lane_enabled=True)`.

### 6. Test Structure (all test files)

- `unittest.IsolatedAsyncioTestCase` for async tests
- `make_run_request()` helper at module top (test_adapter.py:27-43, test_runner.py:27-43)
- `Fake*Runner` / `Fake*Transport` classes for injection (test_adapter.py:46-69, test_runner.py:108-120)
- Fixture files in `tests/fixtures/` directory (test_runner.py:23, 46-47)
- `assertNotIn(raw_content, repr(result))` privacy assertion pattern (test_adapter.py:139)

### 7. Frozen Contract Constraint (all files)

Do NOT modify any frozen surface:
- `BackendAdapter` Protocol — 9 methods (protocols.py:222-239), count-frozen
- `AdapterCapabilitySet` — 14 fields, count-frozen
- `RunEventType` enum — 9 values (enums.py:100-109), hash-frozen
- `RunEvent` dataclass — 7 fields (protocols.py:137-145), frozen
- `AssistantOutputBoundary` Protocol (ports.py:34-40) — NOT count-frozen, adding optional `event_type` param is safe

## PATTERN MAPPING COMPLETE
