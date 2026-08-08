# Technology Stack

**Milestone:** v3.1 Legal AI Arena — multi-agent workflow engine, local arena service, desktop arena UI
**Researched:** 2026-08-09
**Confidence:** HIGH
**Runtime:** Python 3.11+ (CI floor `requires-python = ">=3.11"`; dev runs 3.14), Node/TypeScript via Bun workspace

## Scope Boundary

This research covers **only** stack additions for the v3.1 Legal AI Arena milestone. The following are **already validated in v3.0** and must not be re-researched or duplicated:

| Already shipped (reuse as-is) | Do NOT re-research / re-add |
|-------------------------------|----------------------------|
| `packages/acp-client` — `ACPClient`, `StdioACPTransport`, `ACPBackendAdapter`, per-session subprocess lifecycle (`agent-client-protocol>=0.12,<0.13`) | New ACP client library / new JSON-RPC transport |
| `packages/agent-core` — async streaming turn loop, 4 legal guardrails (research-gate / citation audit / ask-user / de-AI polish), `acp_server.py` (deliberately does NOT declare `fs/*` or `terminal/*`) | New guardrail engine / new agent runtime |
| `packages/skill-index` — 396 legal skills indexed from read-only vendored repos | New skill indexing / new corpus copying |
| `packages/ui-core` — 23 SolidJS components, 3 themes, `createEventStream` SSE consumer with Last-Event-ID reconnection, `event-reducer.ts` with `RenderState` | New UI component library / new SSE consumer primitive |
| `packages/platform-contract` — 13-category event vocabulary (15 JSON Schemas, 18 Python dataclasses, 18 TypeScript interfaces), isomorphic to ACP `session/update` | New event vocabulary / new schema format |
| `packages/platform-sdk-ts` — `PlatformApiClient`, `RunEventEnvelope`, generated from OpenAPI | New TS SDK / new API client |
| `services/gateway` — framework-free stdlib ASGI, `encode_sse_event`, `RunEventBuffer`, output boundary enforcement | New HTTP framework (FastAPI / Starlette / aiohttp) / new SSE library |
| `packages/platform-runtime` — `RunEvent`, `RunRequest`, `RunHandle`, `Run` dataclasses, `BackendAdapter` Protocol | New runtime abstractions |
| `apps/desktop` — Tauri 2 shell with SolidJS 1.9, `@tauri-apps/api`, `@tauri-apps/plugin-dialog`, `@tauri-apps/plugin-fs`, `useEventStream` hook | New desktop shell / new Tauri plugins for SSE |

**Milestone goal:** Lawyers create a legal task in the desktop app, select multiple ACP backend agents to process in parallel, each agent self-scores and iterates, agents cross-review each other, an independent session synthesizes the final version — all streaming live to the desktop UI, with legal guardrails non-bypassable throughout.

---

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Python stdlib `asyncio.TaskGroup`** | 3.11+ (stdlib) | Parallel agent execution — spawn N ACP subprocess sessions concurrently, await all, collect results | Structural concurrency with strong safety guarantees (exception propagation, automatic cancellation). Already the platform's concurrency model — `acp-client` uses `asyncio.create_subprocess_exec` throughout. Zero new dependencies. `TaskGroup` is the idiomatic Python 3.11+ replacement for `asyncio.gather` with built-in error containment. The arena runs N agents as independent `ACPBackendAdapter.submit_run()` coroutines inside one `TaskGroup`; each spawns its own stdio subprocess via the existing `StdioACPTransport`. |
| **Python stdlib ASGI (framework-free)** | 3.11+ (stdlib) | Local arena HTTP+SSE service — same pattern as the existing Gateway | The Gateway (`services/gateway/src/gateway/app.py`) is explicitly "framework-free (stdlib pattern, zero external dependencies)". The arena service must follow the same pattern for architectural consistency, output-boundary parity, and zero new runtime deps. Reuses `encode_sse_event` from `gateway/sse.py` and `RunEventBuffer` from `gateway/event_buffer.py`. SSE is just `Content-Type: text/event-stream` + `wfile.flush()` on a stdlib handler — no library needed. |
| **SolidJS signals + `createMemo`** | solid-js 1.9.14 (existing `^1.9.0` pin) | Desktop arena UI — demultiplex parallel agent streams by `agent_id` | The existing `createEventStream` in `ui-core` produces a single `RenderState` signal per SSE connection. The arena multiplexes N agent streams into one SSE endpoint (tagged with `agent_id` in `RunEvent.metadata`), so the UI needs one `createEventStream` per arena run + a `createMemo` that partitions events by `agent_id` into per-agent `RenderState` slices. SolidJS fine-grained reactivity means only the agent panel whose state changed re-renders — no virtual DOM diffing across N parallel streams. No new library; extends the existing `event-reducer.ts` pattern. |
| **Tauri 2 IPC (`@tauri-apps/api/event`)** | @tauri-apps/api 2.11.1 (existing `^2.11.0` pin) | Desktop ↔ Rust backend IPC for arena lifecycle commands (start/stop arena, directory selection handoff) | Already a desktop dependency. `listen()` / `emit()` for Tauri event IPC. The arena service is a local Python HTTP+SSE server (not a Tauri Rust command), so the desktop app consumes it via the same `createEventStream` + `fetch` path used for the Gateway. Tauri IPC is used only for: (1) directory selection via `@tauri-apps/plugin-dialog` `open({ directory: true })`, (2) passing the selected directory path to the arena service, (3) arena service process lifecycle if managed by Tauri. No new Tauri plugin required. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **`@tauri-apps/plugin-dialog`** | 2.7.2 (existing `^2.7.1` pin) | Native directory picker for user-selected reference directories | When the user selects a directory for ACP `fs/read_text_file` access. `open({ directory: true, recursive: true })` returns a path that the desktop app sends to the arena service. Already a desktop dependency — no addition needed, just new usage. |
| **`@tauri-apps/plugin-fs`** | 2.5.1+ (existing `^2.5.1` pin) | Filesystem scope management for selected directories | When the selected directory path needs to be registered in Tauri's fs scope so the webview can later open result files. Already a desktop dependency. |
| **`asyncio.Queue`** | 3.11+ (stdlib) | Multiplex N agent event streams into one SSE response | Each parallel agent's `ACPBackendAdapter.submit_run()` yields `RunEvent` objects. The arena engine pushes each event (tagged with `agent_id` and `phase` — parallel / self-score / cross-review / synthesis) into a shared `asyncio.Queue`. The SSE handler drains the queue and encodes each event via `encode_sse_event`. This is the same producer-consumer pattern the Gateway uses with `RunEventBuffer`, extended to multiplex multiple producers. |
| **`dataclasses` + `enum`** | 3.11+ (stdlib) | Arena workflow state machine — 4-level workflow modes, phase transitions, scoring records | The arena engine models workflow state (Level 1–4, phases: parallel → self-score → cross-review → synthesis) as frozen dataclasses and enums, mirroring the existing `platform-contract` pattern (18 dataclasses, `RunEventType` enum). No new schema library — reuse `platform-contract`'s `RunEvent` with arena-specific `metadata` fields (`arena_id`, `agent_id`, `phase`, `score`, `iteration`). |
| **`json` + `pathlib`** | 3.11+ (stdlib) | Agent registration directory — backend agent config discovery | A simple JSON config directory (e.g. `config/agents/`) listing available ACP backends (`backend_id`, `command`, `env_refs`, `capabilities`, `display_name`). The arena service scans this directory at startup. No new config library — same `pathlib` + `json` pattern used by `operator-config` and `gateway/config.py`. |
| **`uuid` + `time`** | 3.11+ (stdlib) | Arena run IDs, event sequencing, scoring timestamps | Same pattern as `platform-contract` events (`event_id`, `occurred_at`, `seq`). Arena run IDs are `uuid4().hex`; per-agent sub-runs get their own `run_id` within the arena's event stream. |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| **Python workflow orchestration** | stdlib `asyncio.TaskGroup` (no framework) | LangGraph 1.2.10 | LangGraph models agents as in-process graph nodes with its own state/checkpointing. InkStatute agents are **external ACP stdio subprocesses** — the arena engine is a scheduler/relay, not an agent runtime. LangGraph's durable execution, checkpointing, and state graphs are redundant with ACP's own `session/update` streaming and the platform's `RunEventBuffer`. Adding LangGraph would introduce a second event model (LangGraph's `StreamPart`) alongside the existing ACP-isomorphic `RunEvent` vocabulary — a net liability per Key Decision "通道层不对齐 AG-UI / Vercel AI SDK" (same reasoning: zero interop benefit, double event vocabulary). LangGraph also pulls in `langchain-core` as a transitive dep, violating the platform's zero-external-dep Python philosophy. |
| **Python workflow orchestration** | stdlib `asyncio.TaskGroup` (no framework) | CrewAI 1.15.1 | CrewAI's role/goal/backstory model and `Crew` process manager assume the framework controls agent execution and LLM calls. InkStatute agents are opaque ACP subprocesses — the platform cannot inject CrewAI's `Agent` abstraction into them. CrewAI's routing/ delegation model conflicts with the arena's explicit 4-level workflow (parallel → self-score → cross-review → synthesis) which is orchestrated by the engine, not by agent-to-agent conversation. |
| **Python workflow orchestration** | stdlib `asyncio.TaskGroup` (no framework) | AutoGen 0.7.5 / Microsoft Agent Framework 1.0 | AutoGen is in maintenance mode (Microsoft moved to MAF April 2026). Both assume conversational agent-to-agent messaging with framework-managed LLM calls. The arena's cross-review is not a free-form conversation — it's a structured workflow where each agent receives specific inputs (another agent's output + scoring rubric) and produces structured review output. ACP `session/update` already provides the streaming primitive; the arena engine just orchestrates which agent gets which input at which phase. |
| **Python workflow orchestration** | stdlib `asyncio.TaskGroup` (no framework) | Prefect / Temporal | Durable workflow engines for long-running distributed pipelines with external state stores. The arena is a local single-machine workflow that completes in minutes (agent turns), not hours/days. ACP's own subprocess lifecycle (`SubprocessLifecycleManager` with SIGTERM/SIGKILL/restart) already handles crash recovery. Adding Prefect/Temporal would require a database and a separate worker process — massive overkill for ≤50 lawyers on one machine. |
| **Local HTTP+SSE service** | stdlib ASGI (framework-free, same as Gateway) | FastAPI / Starlette + uvicorn | The Gateway is deliberately framework-free with zero external deps. Introducing FastAPI in the arena service would create an architectural split (two HTTP patterns in the same monorepo) and pull in `starlette`, `pydantic`, `uvicorn` as hard deps. The arena service needs only 4–6 endpoints (create arena, stream events, list agents, select directory, get result) — trivially implementable on stdlib ASGI. The existing `encode_sse_event` and `RunEventBuffer` are reusable as-is. |
| **Tauri SSE consumption** | `createEventStream` from `ui-core` (existing, uses `fetch` + `ReadableStream`) | `tauri-plugin-sse` 0.1.1 | The desktop app already consumes the Gateway's SSE via `createEventStream` using standard `fetch` + `ReadableStream` reader (see `ui-core/src/stores/eventStream.ts`). This works in Tauri's webview because Tauri 2 supports standard Fetch API. `tauri-plugin-sse` routes SSE through Rust, which is unnecessary when the webview's native `fetch` already works. Adding it would create a second SSE consumption path (Rust-backed vs. webview-native) — inconsistent and redundant. |
| **SolidJS SSE primitive** | `createEventStream` from `ui-core` (existing) | `@solid-primitives/sse` | `ui-core` already ships `createEventStream` with Last-Event-ID reconnection, exponential backoff, and `RenderState` reduction. `@solid-primitives/sse` provides `createSSE` / `createSSEStream` / `makeSSEWorker` but would be a third-party dep redundant with the existing primitive. The arena UI extends `event-reducer.ts` to handle multiplexed `agent_id`-tagged events, not replaces the stream consumer. |
| **SolidJS event composition** | SolidJS signals + `createMemo` (existing) | RxJS / `solid-events` / `solid-parallel` | The arena needs to demultiplex one SSE stream into N per-agent `RenderState` slices. This is a pure function: `events.filter(e => e.metadata.agent_id === agentId)` reduced per-agent. SolidJS `createMemo` computes this reactively with fine-grained updates. RxJS observables are a heavier abstraction for the same result; SolidJS author (ryansolid) explicitly recommends signals over streams for this kind of state derivation. |
| **ACP fs/* handler** | New `fs/read_text_file` handler in arena-service (Python) | `tauri-plugin-fs` Rust-side file reading | ACP `fs/read_text_file` is a JSON-RPC method that the **ACP client** (arena-service) must handle when an agent requests it. The agent sends `fs/read_text_file` over stdio; the arena-service resolves the path within the user-selected directory and returns file contents. This is a Python-side handler in the arena service, not a Tauri Rust command. `tauri-plugin-fs` is for the webview ↔ Rust filesystem access, a different layer. |
| **Agent registration** | JSON config directory + `pathlib` scan (stdlib) | SQLite registry / skill-index extension | Agent registration is a small static config (backend_id, command, env_refs, display_name, capabilities) read at startup. A JSON directory is consistent with `operator-config`'s pattern. SQLite is overkill for ≤20 agent configs that change rarely. `skill-index` indexes skills, not agents — conflating them would violate the existing separation of concerns. |

---

## Integration with Existing v3.0 Packages

### `packages/acp-client` (reuse — no changes)

The arena engine drives N parallel ACP sessions by instantiating N `ACPBackendAdapter` objects (one per selected agent) and calling `submit_run()` on each within an `asyncio.TaskGroup`. Each adapter spawns its own stdio subprocess via `StdioACPTransport`, negotiates capabilities at `initialize`, creates a session, and streams `session/update` notifications as `RunEvent` objects.

**Key integration point:** `ACPBackendAdapter.submit_run()` returns `AsyncIterator[RunEvent]` — the arena engine consumes this iterator and forwards events to the multiplexed SSE queue, tagging each with `agent_id` and `phase` in `RunEvent.metadata`.

**ACP fs/* handler:** The existing `acp-client` does NOT implement `fs/read_text_file` (the `agent-core`'s `acp_server.py` deliberately does not declare `fs/*` per AGENTS.md safety rule). The arena service adds a new fs handler layer: when an agent sends `fs/read_text_file`, the arena-service's ACP client intercepts the request, resolves the path within the user-selected directory (sandboxed), reads the file, and returns contents. This handler lives in the arena-service, NOT in `acp-client` or `agent-core`, to preserve the safety boundary.

### `packages/agent-core` (reuse — guardrails non-bypassable)

The arena engine does NOT re-implement legal guardrails. Guardrails are enforced inside each ACP agent session:
- If the agent is `agent-core` (self-built backend), guardrails run inside the `turn_loop.py` — non-bypassable by design.
- If the agent is an external ACP backend (Hermes, Codex, etc.), the arena engine wraps the agent's output through `agent-core`'s guardrail functions (`guardrails.py`) as a post-processing step before scoring.

**Key integration point:** `agent_core.guardrails` functions are importable as pure functions that take `AgentResult` + context and return pass/fail + citations. The arena engine calls these after each agent's run completes, before self-scoring.

### `packages/skill-index` (reuse — agent registration augmentation)

The agent registration directory maps each registered ACP backend to its skill capabilities. `skill-index` provides the skill catalog; the arena service cross-references selected agents' declared skills against the task's skill requirements to help the user choose appropriate agents.

**Key integration point:** `skill_index` exposes `search_skills(query)` and `get_skill(skill_id)` — the arena service calls these to show "recommended agents for this task type" in the desktop UI.

### `packages/ui-core` (extend — new arena components + reducer extension)

The arena UI extends `ui-core` with:
1. **New `ArenaEventReducer`** — extends `event-reducer.ts` to handle multiplexed events. The existing `reduce(state, event)` function processes one agent's events into one `RenderState`. The arena reducer maintains a `Map<agent_id, RenderState>` plus arena-level state (current phase, scores, cross-review assignments, synthesis status). Implemented as a new `arena-reducer.ts` that delegates per-agent reduction to the existing `reduce()` and merges arena-level metadata.
2. **New arena components** — `AgentPanel` (per-agent streaming view), `ScoreCard` (self-score display with 10-point framework), `CrossReviewMatrix` (agent × agent review grid), `SynthesisViewer` (final result with review opinions). These extend the existing component pattern (props-driven, CSS-co-located, theme-aware).
3. **Existing `createEventStream`** — reused as-is. One stream per arena run. The arena service multiplexes all agent events into one SSE endpoint (`/v1/arenas/{arena_id}/events`).

**Key integration point:** `createEventStream({ client, runId })` → the arena passes `arenaId` as the `runId`. The existing Last-Event-ID reconnection works because the arena service buffers events in an `RunEventBuffer` (reused from Gateway) keyed by `arena_id`.

### `packages/platform-contract` (reuse — extend metadata, no new event types)

The arena does NOT add new event types to the 13-category vocabulary. Instead, it uses existing `RunEvent` with arena-specific `metadata` fields:
- `metadata.arena_id` — identifies the arena run
- `metadata.agent_id` — identifies which agent produced this event
- `metadata.phase` — `"parallel"` | `"self_score"` | `"cross_review"` | `"synthesis"`
- `metadata.score` — self-score or cross-review score (10-point framework)
- `metadata.iteration` — self-score iteration count
- `metadata.review_target` — which agent's output is being reviewed (for cross-review phase)

This preserves the isomorphic ACP `session/update` mapping — each agent's events are still standard `RunEvent`s, just tagged with arena context. The existing `encode_sse_event` in `gateway/sse.py` serializes `metadata` as-is.

### `services/gateway` (reuse patterns — do NOT merge)

The arena service is a **separate local service** (`services/arena-service`), not merged into the Gateway. Rationale: the Gateway is the multi-tenant client-facing entry point for all channels; the arena service is a local-only workflow orchestrator that spawns ACP subprocesses (which must be local per the "agents are local stdio subprocesses" constraint). However, the arena service reuses:
- `encode_sse_event` from `gateway/sse.py` — identical SSE frame encoding
- `RunEventBuffer` from `gateway/event_buffer.py` — identical event buffering for Last-Event-ID reconnection
- `GatewayConfig.from_env` pattern — identical env-based config
- Output boundary enforcement — identical `_assert_no_forbidden_payload_keys` check

**Key integration point:** Extract `encode_sse_event` and `RunEventBuffer` into a shared module (e.g. `packages/platform-runtime` or a new `packages/sse-core`) OR import directly from `gateway` — the arena service depends on `gateway` as a library (it already has zero external deps).

### `apps/desktop` (extend — new arena page + contexts)

The desktop app extends with:
1. **New `ArenaPage.tsx`** — workflow creation form (task input, agent selection, workflow level 1–4, directory selection), live arena view (parallel agent panels, scores, cross-review matrix, synthesis viewer).
2. **New `ArenaContext.tsx`** — SolidJS context providing arena state (selected agents, workflow level, directory path, arena run ID) to child components.
3. **Existing `useEventStream` hook** — reused with `arenaId` as the `runId` parameter. The hook's `createEventStream` call hits the arena service's SSE endpoint instead of the Gateway's (configurable via `config/gateway.ts` — add an `arenaBaseUrl` alongside the existing `baseUrl`).
4. **Existing `@tauri-apps/plugin-dialog`** — `open({ directory: true, recursive: true })` for reference directory selection. Already a dependency.

**Key integration point:** `config/gateway.ts` exports `gateway` (PlatformApiClient pointing at the Gateway). Add `arena` (PlatformApiClient pointing at `http://127.0.0.1:<arena_port>`). The `useEventStream` hook accepts a `client` parameter — pass the arena client for arena runs.

### `packages/platform-sdk-ts` (reuse — no regeneration needed)

`PlatformApiClient` is a thin HTTP client with `fetchImpl` and `baseUrl`. The arena service speaks the same HTTP+SSE protocol (same endpoint shapes, same `RunEventEnvelope` format). The desktop app constructs a second `PlatformApiClient` with `baseUrl` pointing at the arena service — no SDK regeneration needed.

---

## What NOT to Add (no redundant dependencies)

| Do NOT add | Reason |
|------------|--------|
| LangGraph, CrewAI, AutoGen, MAF, Prefect, Temporal | Heavy workflow frameworks that model agents as in-process nodes. InkStatute agents are external ACP stdio subprocesses. The arena engine is a scheduler/relay, not an agent runtime. Adding any of these introduces a second event model, a second state management system, and hard deps — all redundant with ACP `session/update` + `RunEvent` + `asyncio.TaskGroup`. |
| FastAPI / Starlette / aiohttp / uvicorn | HTTP frameworks. The Gateway is framework-free stdlib ASGI. The arena service follows the same pattern for consistency and zero deps. |
| `tauri-plugin-sse` | Tauri SSE plugin. The desktop webview's native `fetch` + `ReadableStream` already consumes SSE (proven by existing `createEventStream`). Adding a Rust-side SSE path is redundant. |
| `@solid-primitives/sse` | SolidJS SSE primitive. `ui-core` already ships `createEventStream` with reconnection. Redundant. |
| RxJS / `solid-events` / `solid-parallel` | Event composition libraries. SolidJS signals + `createMemo` handle demultiplexing. Overkill. |
| New ACP client library | `packages/acp-client` already drives any ACP v1 agent over stdio. Reuse as-is. |
| New event vocabulary / schema format | `packages/platform-contract` provides the isomorphic event vocabulary. Arena extends `metadata`, not event types. |
| New UI component library | `packages/ui-core` provides 23 components + 3 themes. Arena adds new components in the same package. |
| SQLite / database for agent registration | Agent registration is ≤20 static configs. JSON directory is sufficient (matches `operator-config` pattern). |
| Pydantic / dataclass validation library | `platform-contract` uses stdlib `dataclasses` + `json` + JSON Schema. Arena follows the same pattern. |

---

## Sources

- [agent-client-protocol PyPI](https://pypi.org/project/agent-client-protocol/) — latest 0.11.0 (Jul 5, 2026); project pins `>=0.12,<0.13` (existing, not re-researched)
- [agentclientprotocol/python-sdk GitHub](https://github.com/agentclientprotocol/python-sdk) — ACP Python SDK, Apache 2.0
- [LangGraph PyPI](https://pypi.org/project/langgraph/) — latest 1.2.10; MIT; graph-based orchestration
- [CrewAI vs AutoGen vs LangGraph comparison (SimilarLabs, 2026)](https://similarlabs.com/blog/crewai-vs-autogen-vs-langgraph) — framework landscape
- [AI Agent Frameworks Mid-2026 Landscape (The Agent Report)](https://the-agent-report.com/2026/07/ai-agent-frameworks-comparison-2026-langgraph-crewai-autogen/) — AutoGen maintenance mode, MAF 1.0
- [Tauri releases](https://v2.tauri.app/release/tauri/) — latest 2.11.5 (Jul 1, 2026)
- [@tauri-apps/api npm](https://www.npmjs.com/package/@tauri-apps/api) — latest 2.11.1 (Jun 17, 2026)
- [@tauri-apps/plugin-dialog npm](https://www.npmjs.com/package/@tauri-apps/plugin-dialog) — latest 2.7.2 (Jul 18, 2026); `open({ directory: true })` for directory selection
- [tauri-plugin-sse docs.rs](https://docs.rs/crate/tauri-plugin-sse/latest) — 0.1.1 (Nov 2025); NOT recommended (redundant with webview native fetch)
- [Tauri Emitter trait docs](https://docs.rs/tauri/latest/tauri/trait.Emitter.html) — `emit()` / `emit_to()` IPC API
- [solid-js npm](https://www.npmjs.com/package/solid-js) — latest 1.9.14 (Jul 1, 2026)
- [@solid-primitives/sse JSR](https://jsr.io/@solid-primitives/sse) — `createSSE` / `createSSEStream`; NOT recommended (redundant with ui-core `createEventStream`)
- [Python 3.11 asyncio.TaskGroup docs](https://docs.python.org/3.11/library/asyncio-task.html) — structural concurrency, added 3.11
- [Python 3.11 asyncio-subprocess docs](https://docs.python.org/3.11/library/asyncio-subprocess.html) — parallel subprocess management
- Existing codebase: `services/gateway/src/gateway/{app.py,sse.py,event_buffer.py,config.py}`, `packages/acp-client/src/inkstatute_acp_client/{client.py,adapter.py,lifecycle.py,process_mode.py,event_mapping.py}`, `packages/agent-core/src/inkstatute_agent_core/{acp_server.py,guardrails.py,turn_loop.py}`, `packages/ui-core/src/{event-reducer.ts,stores/eventStream.ts}`, `apps/desktop/src/{hooks/useEventStream.ts,contexts/ConnectionContext.tsx,config/gateway.ts}`, `apps/desktop/src-tauri/Cargo.toml`, `apps/desktop/package.json`
