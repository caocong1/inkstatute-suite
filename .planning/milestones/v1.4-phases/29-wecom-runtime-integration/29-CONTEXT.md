# Phase 29 Context: WeCom/Runtime Integration

**Date:** 2026-07-03
**Phase goal:** Wire the unified memory layer into the ordinary WeCom/runtime flow so recall happens before the agent turn and retention happens after the reply is finalized.

---

## Current State

- Phase 28 shipped a `Memory` interface with retention/focus policies.
- `FakeMemory` and `HindsightMemory` implement the interface.
- `WeComSessionRuntime` handles turn lifecycle, active task routing, and output delivery.
- `MemoryOrchestrator` (native record-style) exists but is not integrated with the new `Memory` interface.

## What Needs to Change

1. `WeComSessionRuntime` needs a `Memory` port to recall before the agent turn and retain after the reply.
2. The recall result must be passed into the runtime context without leaking raw user text or internal notices.
3. Retention must only happen after the reply is finalized and output policy has approved it.
4. The existing Hermes one-shot adapter must continue to work unchanged.

## Key Decisions Already Made

- The `Memory` interface is async and scoped by tenant/workspace/user.
- The default retention policy keeps durable facts; it discards transient task details.
- Hindsight is the backend, but tests use `FakeMemory`.
- Secrets and raw payloads stay out of the platform-runtime package.

---

## Open Questions

1. Should recall be awaited inline before `backend.submit_run`, or can it happen concurrently with session resolution?
2. How do we represent recalled memory in the `RunRequest` metadata? (refs, summary, full text?)
3. What content do we retain after the reply: user turn, agent reply, or both?
4. How do we handle memory failures without breaking the user-facing response?

---

## Suggested Minimal Shippable Scope

- Add an optional `memory: Memory` parameter to `WeComSessionRuntime`.
- Before `runtime.create_run`, call `memory.arecall` with the user turn text as query.
- Inject the recall result into `run_request.metadata["memory_context"]` as a safe summary (no raw text).
- After the reply is finalized (or in the outcome), retain a durable memory combining user turn and agent reply.
- Add a `MemoryIntegrationPolicy` to control whether memory is enabled, failure mode, and retention scope.
- Write tests for pre-turn recall and post-turn retention using `FakeMemory`.
- Keep V2 gates green.
