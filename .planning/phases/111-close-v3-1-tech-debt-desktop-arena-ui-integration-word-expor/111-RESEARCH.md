# Phase 111: v3.1 Closure — Desktop Arena Integration + Export + Wiring + Test Fix - Research

**Researched:** 2026-08-09
**Domain:** Desktop UI integration, arena-service export endpoint, arena-engine FS handler wiring, BackendAdapter test-count regression fix
**Confidence:** HIGH

## Summary

Phase 111 is a wiring/integration/test-fix closure phase. All the hard components already exist and are tested in isolation — this phase connects them end-to-end inside the desktop app and closes two regressions. The arena UI components (`ArenaWorkflowCreator`, `ParallelStreamPanel`, `ScoreCard`, `ReviewSummary`, `SynthesisViewer`), the `arenaStream` store, and the `ArenaEventReducer` all live in `packages/ui-core/src/` and are already exported from `@inkstatute/ui-core` (verified in `packages/ui-core/src/index.ts` lines 199-212). The arena-service already has 5 endpoints (`POST /v1/arena`, `GET /v1/arena/{id}/stream`, `POST /v1/arena/{id}/cancel`, `POST /v1/arena/{id}/action`, `GET /v1/arena/{id}/status`) — the export endpoint is the one missing piece. The `FSSandbox.read_text_file` and `ReferenceSanitizer` from Phase 106 are complete and tested; arena-engine simply does not call them yet when `ArenaWorkflowConfig.reference_dir` is set. The track-changes docx generator (`create_document_generate_tool` in `packages/agent-core/src/inkstatute_agent_core/tools/document_generate.py`) is a finished, lazy-importing tool that wraps `TrackChangesBuilder` from `lawfirm-profile/scripts/contract_review_trackchanges.py`.

The BackendAdapter regression is wider than the phase goal names: SAFE-06's `backend_family()` addition to the `BackendAdapter` Protocol (in `packages/platform-runtime/src/platform_runtime/protocols.py` line 232) broke **four** assertions across **three** gates (qqbot-channel, qqbot-service, contract-test-suite), not just the one named test. All four must be updated to 10 for the gate system to go green. The qqbot-channel gate additionally carries a pre-existing recall-test failure (`test_recall01_c2c_over_window_wakeup_omits_msg_id_on_wire`) that is accepted as carry and must NOT be touched.

**Primary recommendation:** Add an `ArenaPage` to the desktop app that wires the existing ui-core arena components to a new arena-service `PlatformApiClient` (port 8001, separate from the Gateway on 8000); add `POST /v1/arena/{arena_id}/export` to arena-service delegating to the existing track-changes tool; wire `FSSandbox` + `ReferenceSanitizer` into arena-engine's `_build_run_request` when `reference_dir` is set; and update all four BackendAdapter count assertions (9→10) plus the contract-freeze baseline hash for `protocols.py`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Discuss phase was skipped (workflow.skip_discuss). All implementation choices are at the agent's discretion, constrained by the binding architecture decisions in AGENTS.md / PROJECT.md. There are no user-locked decisions beyond those binding constraints.

### Binding constraints from AGENTS.md / PROJECT.md that MUST be honored
- Chat UI must have exactly one implementation (in `@inkstatute/ui-core`); desktop app imports, does not re-implement.
- Word-native track-changes docx generation lives in agent-core (the 41,185-byte Python module `contract_review_trackchanges.py`); the new export endpoint calls into it, never re-implements it.
- ACP fs/* handler from Phase 106 (`FSSandbox.read_text_file`) is the only sanctioned path for reference_dir reading; path sandboxing must not be bypassed.
- Output boundary enforced twice (ACP event bridge + Gateway); backend/system notices must not reach ordinary lawyer users.
- Permission requests must never be auto-approved server-side.
- Legal guardrails (research-gate / citation audit / ask-user / de-AI polish) are non-bypassable in the arena workflow.
- Every new `packages/*/src` and `services/*/src` directory must be covered by a gate.
- Run `python scripts/run_v2_gates.py` before claiming phase complete; all 41 gates must stay green (qqbot-channel recall test pre-existing failure accepted as carry).

### Claude's Discretion
All implementation choices are at the agent's discretion — use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | Arena workflow creator (mode/agent/task/directory selection) | `ArenaWorkflowCreator` component exists and is exported from ui-core (index.ts:200). Desktop app must render it on a new arena page and wire `onCreate` → `POST /v1/arena`. |
| UI-02 | Parallel stream panel — N demultiplexed live agent streams | `ParallelStreamPanel` exists (index.ts:202). Desktop arena page must pass `slotStates()` from `createArenaStream` + ordered `agentSlots`. |
| UI-03 | Score card display (per agent, per round) | `ScoreCard` exists (index.ts:207). Accepts `ArenaScoreEntry[]` from `arenaMetaReducer`. Desktop page passes `metaState().scores`. |
| UI-04 | Review summary display (findings, confidence, confirmed/disproved) | `ReviewSummary` exists (index.ts:209). Accepts `ArenaReviewEntry[]` from `arenaMetaReducer`. Desktop page passes `metaState().reviews`. |
| UI-05 | Synthesis viewer (final version + Word-native track-changes export) | `SynthesisViewer` exists (index.ts:211). `onExport({format, path})` callback must call new `POST /v1/arena/{id}/export` endpoint and write docx to `path` via `desktopFileAdapter`. |
| UI-06 | `ArenaEventReducer` demultiplexes — composes existing `reduce()` per slot | `arenaEventReducer` + `arenaMetaReducer` exist in `reducers/arenaEventReducer.ts`. `createArenaStream` store in `stores/arenaStream.ts` already consumes SSE and applies both reducers. Desktop page must instantiate the store. NOTE: `createArenaStream` and `arenaEventReducer` are NOT yet exported from `index.ts` — must add exports. |
| UI-07 | Refresh preserves state — run state persistence + SSE reconnection | `arenaStream.ts` already implements localStorage persistence (`arena-state-{id}`) + Last-Event-ID reconnection with exponential backoff. Wiring the store into the desktop page satisfies this. |
| GATE-01 | Gate-coverage meta-test updated (34 → 36+ gates) | Gate-coverage meta-test (test_gate_coverage.py) already asserts `>= 40` gates and 41 gates exist. E2E export test must be added to `test_arena_e2e.py` (arena-e2e gate). No new gate needed unless a new `src` dir is introduced. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Arena page rendering + screen switching | Browser / Client (desktop) | — | Desktop app owns routing (signal-based screen switch in App.tsx); arena page is a new screen alongside "home"/"workspace". |
| Arena workflow creation (POST /v1/arena) | API / Backend (arena-service) | Browser / Client | arena-service owns the endpoint; desktop client issues the HTTP call via a PlatformApiClient pointed at port 8001. |
| SSE stream consumption + demultiplexing | Browser / Client (desktop) | — | `createArenaStream` store runs client-side; arena-service only emits SSE frames. |
| Word docx export generation | API / Backend (arena-service → agent-core) | — | Export endpoint lives in arena-service; docx generation delegated to agent-core's track-changes tool (never re-implemented client-side). |
| docx file save dialog | Browser / Client (desktop) | — | `desktopFileAdapter.save()` shows native Tauri dialog; SynthesisViewer triggers it, then calls export endpoint to generate + write. |
| reference_dir file reading + sanitization | API / Backend (arena-engine → acp-client) | — | `FSSandbox.read_text_file` + `ReferenceSanitizer` are server-side security primitives; arena-engine calls them when building RunRequest context. |
| BackendAdapter method-count contract | Database / Storage (contract-test-suite) | — | Contract freeze is a test-suite responsibility; baseline JSON + count assertions are the enforcement layer. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| solid-js | ^1.9.0 | UI reactivity (desktop app + ui-core) | Binding v3.0 decision: shared UI is SolidJS [VERIFIED: apps/desktop/package.json] |
| @inkstatute/ui-core | workspace:* | Single chat/arena UI implementation | Binding: chat UI must have exactly one implementation [VERIFIED: packages/ui-core/src/index.ts] |
| @inkstatute/platform-sdk-ts | workspace:* | PlatformApiClient + TS event/contract types | Used by arenaStream store for SSE + types [VERIFIED: packages/ui-core/src/stores/arenaStream.ts] |
| @tauri-apps/plugin-dialog | ^2.7.1 | Native file open/save dialogs | Used by desktopFileAdapter for docx save path [VERIFIED: apps/desktop/src/adapters/desktopFileAdapter.ts] |
| vitest | ^3.0.0 | TS/TSX test runner | Desktop + ui-core test framework [VERIFIED: apps/desktop/vite.config.ts, apps/desktop/package.json] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| solid-markdown | ^2.1.0 | Markdown rendering in SynthesisViewer | Already used by SynthesisViewer for synthesis content display [VERIFIED: packages/ui-core/src/components/SynthesisViewer.tsx] |
| remark-gfm | ^4.0.0 | GFM markdown extensions | Paired with solid-markdown in SynthesisViewer [VERIFIED: SynthesisViewer.tsx] |
| pytest / unittest | stdlib | Python test runner for arena-service / contract-test-suite gates | Gates use `python -m unittest discover` [VERIFIED: scripts/run_v2_gates.py] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New PlatformApiClient for arena-service | Extend existing Gateway client | Rejected: arena-service is a separate local-only service on port 8001 with its own bearer token; Gateway is port 8000. Mixing bases would violate the single-entry-point rule for Gateway. Use a second PlatformApiClient instance pointed at 8001. |
| Adding docx generation to arena-service | Call agent-core tool directly | Rejected by binding constraint: track-changes generation lives in agent-core (41,185-byte Python module); arena-service delegates, never re-implements. |

**Installation:**
```bash
# No new packages to install — all dependencies already in workspace.
```

**Version verification:** No new installs in this phase (wiring/integration/test-fix only). All versions verified via existing package.json files. [VERIFIED: apps/desktop/package.json, packages/ui-core/package.json]

## Package Legitimacy Audit

> This phase installs **zero** external packages. All work is wiring existing components, adding an endpoint to an existing service, and fixing test assertions. The Package Legitimacy Gate is not triggered.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (none) | — | — | — | — | — | N/A — no new installs |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Desktop App (apps/desktop, Tauri + SolidJS)
  │
  ├── App.tsx (signal screen switch: "home" | "workspace" | "arena"  ← NEW)
  │     └── ArenaPage.tsx  ← NEW
  │           ├── ArenaWorkflowCreator  (ui-core)  ──onCreate──▶ PlatformApiClient(8001).POST /v1/arena
  │           ├── createArenaStream(arenaClient, arenaId)  ──SSE──▶ GET /v1/arena/{id}/stream
  │           │     └── arenaEventReducer (per-slot demultiplex)
  │           │     └── arenaMetaReducer  (scores/reviews/synthesis)
  │           ├── ParallelStreamPanel  (slotStates)
  │           ├── ScoreCard            (metaState.scores)
  │           ├── ReviewSummary        (metaState.reviews)
  │           └── SynthesisViewer      (metaState.synthesisContent)
  │                 └── onExport({format, path}) ──▶ POST /v1/arena/{id}/export
  │                       └── write docx bytes to path (desktopFileAdapter / Tauri fs)
  │
  └── config/arena.ts  ← NEW (PlatformApiClient @ http://127.0.0.1:8001)

Arena Service (services/arena-service, port 8001)
  ├── app.py  dispatch  ──NEW route──▶ POST /v1/arena/{arena_id}/export
  │     └── _handle_export_arena  ← NEW
  │           └── engine.export_arena(arena_id, body)  ← NEW on ArenaServiceEngine
  │                 └── agent-core create_document_generate_tool → TrackChangesBuilder.process() → .save()
  │
  └── engine_integration.py  ArenaServiceEngine
        └── create_arena()  ──▶ ArenaEngine.start(config)
              └── _build_run_request()  ← MODIFY: inject reference_dir content via FSSandbox

Arena Engine (packages/arena-engine)
  └── engine.py / mode1.py _build_run_request()
        └── if config.reference_dir: FSSandbox.read_text_file + ReferenceSanitizer → AgentTurn.metadata["reference_context"]
```

### Recommended Project Structure
```
apps/desktop/src/
├── pages/
│   └── ArenaPage.tsx          # NEW — arena workflow page (wires all ui-core arena components)
├── config/
│   ├── gateway.ts             # existing — Gateway client (port 8000)
│   └── arena.ts               # NEW — arena-service client (port 8001)
└── App.tsx                    # MODIFY — add "arena" screen + route

services/arena-service/src/arena_service/
├── app.py                     # MODIFY — add OPERATION_EXPORT_ARENA + route + handler
├── engine_integration.py      # MODIFY — add export_arena() method
└── openapi.py                 # MODIFY — add export path to OpenAPI doc

packages/arena-engine/src/arena_engine/
├── engine.py                  # MODIFY (optional) — accept fs_sandbox param
└── mode1.py                   # MODIFY — _build_run_request injects reference_dir content

packages/ui-core/src/
└── index.ts                   # MODIFY — export createArenaStream, ArenaStreamStore, arenaEventReducer, arenaMetaReducer

# Test-fix files (no new structure):
packages/channels/qqbot/tests/test_v1_8_safety_baseline.py          # MODIFY 9→10
services/qqbot-service/tests/test_host_safety_baseline.py           # MODIFY 9→10 + frozenset
packages/contract-test-suite/tests/test_contract_count_freeze.py    # MODIFY 9→10
packages/contract-test-suite/fixtures/contract_freeze_baseline.json # MODIFY protocols.py hash
packages/contract-test-suite/tests/test_arena_e2e.py                # MODIFY — add export flow test
```

### Pattern 1: Signal-based screen switching (no router)
**What:** The desktop app uses a SolidJS signal `screen()` with values `"home" | "workspace"` to switch pages — NO router library (App.tsx line 45, 135-145). This matches the original lawyer-desktop architecture.
**When to use:** Adding the arena page — extend the screen union to `"home" | "workspace" | "arena"` and add a `<Show when={screen() === "arena"}>` block.
**Example:**
```typescript
// Source: apps/desktop/src/App.tsx (existing pattern, lines 45, 135-145)
const [screen, setScreen] = createSignal<"home" | "workspace" | "arena">("home");
// ...
<Show when={screen() === "arena"}>
  <ArenaPage onGoHome={() => setScreen("home")} />
</Show>
```

### Pattern 2: Adapter injection via AdapterContext
**What:** Platform-specific adapters (file, window, drop) are provided via `AdapterContext.Provider` in App.tsx (line 164). ui-core components access them via `useAdapters()`.
**When to use:** ArenaPage uses `useAdapters().file` for the reference-dir picker (ArenaWorkflowCreator already does this internally) and SynthesisViewer uses it for `file.save()`.
**Example:**
```typescript
// Source: apps/desktop/src/App.tsx line 164 + packages/ui-core/src/components/SynthesisViewer.tsx line 29
<AdapterContext.Provider value={desktopAdapters}>
  {/* ArenaPage and its children inherit file adapter */}
</AdapterContext.Provider>
// Inside SynthesisViewer:
const { file } = useAdapters();
const path = await file.save({ defaultPath: "综合最终版.docx", filters: [...] });
```

### Pattern 3: Framework-free arena-service dispatch (stdlib)
**What:** arena-service uses a stdlib `_parse_route(method, path, base_path)` pattern (app.py lines 389-437) that pattern-matches path parts to `(operation, path_params)`. No web framework.
**When to use:** Adding the export endpoint — add a new route match for `POST /v1/arena/{arena_id}/export` and a new `OPERATION_EXPORT_ARENA` constant + handler.
**Example:**
```python
# Source: services/arena-service/src/arena_service/app.py lines 413-431 (existing pattern)
# POST /v1/arena/{arena_id}/export — export arena
if method == "POST" and len(parts) == 3 and parts[0] == "arena" and parts[2] == "export":
    return OPERATION_EXPORT_ARENA, {"arena_id": parts[1]}
```

### Pattern 4: arena-service handler delegates to engine via getattr
**What:** Each handler in app.py checks `getattr(self._engine, "<method>", None)` and returns `_not_implemented()` if absent (app.py lines 283-285, 311-313, etc.). This keeps app.py decoupled from the engine concrete type.
**When to use:** The export handler should follow the same pattern: `export = getattr(self._engine, "export_arena", None)`.

### Anti-Patterns to Avoid
- **Re-implementing chat/arena UI in the desktop app:** Binding constraint — import from `@inkstatute/ui-core`, never write a second implementation. ArenaPage is wiring only.
- **Re-implementing track-changes docx generation:** Binding constraint — delegate to agent-core's `create_document_generate_tool` / `TrackChangesBuilder`; the export endpoint is a thin caller.
- **Bypassing FSSandbox for reference_dir reading:** Binding constraint — `FSSandbox.read_text_file` is the only sanctioned path; never use raw `open()` or `Path.read_text()` for reference files in arena-engine.
- **Pointing arena client at the Gateway (port 8000):** arena-service is a separate local-only service on port 8001 with its own bearer token. Do not conflate the two clients.
- **Auto-approving permission requests server-side:** Binding safety constraint — never auto-approve `session/request_permission` for terminal/execute_code.
- **Touching the qqbot-channel recall test:** `test_recall01_c2c_over_window_wakeup_omits_msg_id_on_wire` is a pre-existing failure accepted as carry — do NOT modify it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Word docx with native track-changes | Custom docx XML generation | `create_document_generate_tool` (agent-core) → `TrackChangesBuilder` (lawfirm-profile/scripts/contract_review_trackchanges.py) | 41,185 bytes of battle-tested Python; binding constraint: import, don't rewrite. Handles insertions/deletions/comments natively in Word. |
| SSE stream consumption + reconnection | Custom EventSource wrapper | `createArenaStream` store (ui-core/stores/arenaStream.ts) | Already implements slot demultiplexing, localStorage persistence, Last-Event-ID reconnection, exponential backoff. |
| Per-slot event demultiplexing | Custom reducer | `arenaEventReducer` (ui-core/reducers/arenaEventReducer.ts) | Composes the existing single-stream `reduce()` per slot; handles lifecycle broadcast. |
| Reference file path validation | Custom path checks | `FSSandbox.read_text_file` (acp-client/fs_sandbox.py) | Five-layer sandbox (traversal/symlink/resolve/prefix/extension) + size cap; defense-in-depth. |
| Reference file prompt-injection defense | Custom sanitization | `ReferenceSanitizer` (acp-client/sanitizer.py) | Delimiter wrapping + pattern detection + detection logging (no content logged). |
| Native file save dialog | Custom dialog | `desktopFileAdapter.save()` (apps/desktop/src/adapters/desktopFileAdapter.ts) | Wraps @tauri-apps/plugin-dialog; returns real OS path. |
| Arena HTTP routing | Web framework | Existing `_parse_route` stdlib pattern (arena-service/app.py) | arena-service is framework-free by design; adding a framework would violate the zero-external-deps invariant. |

**Key insight:** This phase is pure wiring. Every capability already has a tested implementation. The planner should never see a task that builds new logic for SSE, docx, path sandboxing, or UI components — only tasks that connect existing outputs to existing inputs.

## Runtime State Inventory

> This phase is a wiring/integration/test-fix phase, not a rename/refactor/migration. However, the contract-freeze baseline update touches a stored artifact.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `packages/contract-test-suite/fixtures/contract_freeze_baseline.json` — SHA-256 hash for `protocols.py` is stale (`afc6c808...`, pre-backend_family). Actual file hash is `219ad588...`. | Code edit — update baseline hash to `219ad58892b90b840aa642f90cd8d093f5e6d8b22cc67a2d51eb8dc7fc78a27c`. |
| Live service config | None — arena-service config is env-driven (`ArenaServiceConfig.from_env`), no persisted config changes. | None |
| OS-registered state | None | None |
| Secrets/env vars | `ARENA_SERVICE_TOKEN` — arena-service bearer token; desktop app's new arena client must send it as `Authorization: Bearer <token>`. Token is env-injected, not committed. | Code edit — arena client config reads token from `import.meta.env.VITE_ARENA_SERVICE_TOKEN`. |
| Build artifacts | None — no package renames or new installs. | None |

## Common Pitfalls

### Pitfall 1: BackendAdapter regression is wider than the named test
**What goes wrong:** The phase goal names only `test_backend_adapter_has_exactly_9_methods`, but SAFE-06's `backend_family()` broke **four** assertions across **three** gates. Fixing only the named test (qqbot-channel) leaves qqbot-service and contract-test-suite red.
**Why it happens:** The `backend_family()` method was added to the `BackendAdapter` Protocol (`protocols.py` line 232) during Phase 108 (SAFE-06), but the count-freeze assertions and the contract-freeze SHA-256 baseline were not updated. Multiple gates independently assert the old count.
**How to avoid:** Update ALL four locations:
1. `packages/channels/qqbot/tests/test_v1_8_safety_baseline.py` line 56-58 (9→10, rename test)
2. `services/qqbot-service/tests/test_host_safety_baseline.py` lines 27-39 (add `"backend_family"` to `BACKEND_ADAPTER_METHODS` frozenset) + line 48-50 (9→10, rename test)
3. `packages/contract-test-suite/tests/test_contract_count_freeze.py` line 25 (`BACKEND_ADAPTER_METHOD_COUNT = 10`)
4. `packages/contract-test-suite/fixtures/contract_freeze_baseline.json` line 62 (protocols.py hash → `219ad58892b90b840aa642f90cd8d093f5e6d8b22cc67a2d51eb8dc7fc78a27c`)
**Warning signs:** Running `python scripts/run_v2_gates.py` and seeing failures in qqbot-service or contract-test-suite gates after fixing only qqbot-channel.

### Pitfall 2: arena-service and Gateway are different ports + tokens
**What goes wrong:** The desktop app's existing `gateway` client (config/gateway.ts) points at `http://127.0.0.1:8000` (Gateway). The arena-service is `http://127.0.0.1:8001` with a separate bearer token. Reusing the gateway client for arena calls hits the wrong service.
**Why it happens:** Both use `PlatformApiClient`, so they look interchangeable. But they have different base URLs, ports, and auth tokens.
**How to avoid:** Create a separate `config/arena.ts` exporting an `arenaClient` (new `PlatformApiClient` with `baseUrl = VITE_ARENA_SERVICE_URL || "http://127.0.0.1:8001"` and `defaultHeaders: { Authorization: \`Bearer ${VITE_ARENA_SERVICE_TOKEN}\` }`). Pass this client to `createArenaStream({ client: arenaClient, arenaId })`.
**Warning signs:** 404s or 401s when the desktop arena page calls `/v1/arena`.

### Pitfall 3: createArenaStream and arenaEventReducer are not exported from ui-core index
**What goes wrong:** The desktop app imports from `@inkstatute/ui-core` but `createArenaStream`, `ArenaStreamStore`, `arenaEventReducer`, and `arenaMetaReducer` are NOT in the barrel export (index.ts). The import fails.
**Why it happens:** Phase 110 built the arena UI components and exported them (lines 199-212), but the stream store and reducer were not added to index.ts.
**How to avoid:** Add exports to `packages/ui-core/src/index.ts`: `export { createArenaStream } from "./stores/arenaStream"; export type { ArenaStreamStore, ArenaStreamOptions } from "./stores/arenaStream"; export { arenaEventReducer, arenaMetaReducer, getSlotState, getAllSlotStates } from "./reducers/arenaEventReducer";`
**Warning signs:** TypeScript error "Module has no exported member 'createArenaStream'".

### Pitfall 4: SynthesisViewer.onExport delegates — it does not generate docx
**What goes wrong:** The implementer assumes SynthesisViewer generates the docx. It does not — it only shows a save dialog to get a path, then calls `props.onExport({ format: "docx", path })`. The parent (ArenaPage) must call the export endpoint and write the bytes to that path.
**Why it happens:** SynthesisViewer.tsx lines 36-50 show `file.save()` then `props.onExport(...)` — the docx generation is the parent's job.
**How to avoid:** ArenaPage's `onExport` handler: (1) call `POST /v1/arena/{id}/export` with `{ output_path: path }`, (2) the endpoint generates the docx at that path server-side (agent-core writes directly to the filesystem path), OR (3) the endpoint returns docx bytes and the desktop writes them via Tauri fs. Decide based on whether arena-service runs on the same machine as the desktop app (it does — local-only). Prefer server-side write to the path since the desktop chose it via native dialog.
**Warning signs:** Export button does nothing or produces an empty file.

### Pitfall 5: backend_family() is only implemented on MockACPBackendAdapter
**What goes wrong:** After updating the count to 10, the implementer assumes all adapters implement `backend_family()`. They do not — only `MockACPBackendAdapter` (arena-engine/mock_acp.py:119) and the Protocol define it. `InProcessAgentCoreAdapter`, `FakeBackendAdapter`, and `ProviderModelBackendAdapter` do NOT implement it.
**Why it happens:** SAFE-06 added the method to the Protocol and the mock adapter but did not add it to every adapter. The arena-engine's `_build_backend_families` (engine.py:511-519) has a try/except fallback to `backend_id()`.
**How to avoid:** This phase's success criteria only require updating the test count, NOT implementing `backend_family()` on all adapters. The fallback handles it at runtime. Do NOT expand scope. (Optional: note for a future phase to implement `backend_family()` on InProcessAgentCoreAdapter + FakeBackendAdapter for Protocol completeness.)
**Warning signs:** Tests that check `hasattr(adapter, "backend_family")` would fail — but none of the failing assertions do this (they check Protocol method count, not per-adapter implementation).

### Pitfall 6: E2E export test needs a synthesis result to export
**What goes wrong:** The new E2E export test (success criterion #8) calls the export endpoint, but the export needs a synthesis result + review items to generate a track-changes docx. Without a completed Mode 3/Mode 4 run, there's nothing to export.
**Why it happens:** The export endpoint generates docx from the arena's synthesis content / review findings. Mode 1 and Mode 2 don't produce synthesis.
**How to avoid:** The E2E export test should use a Mode 3 fixture (which produces `synthesis_completed` + review findings), then call `POST /v1/arena/{id}/export`. The existing `fixtures/arena_e2e_mode3.py` provides the synthesis adapter. The test may need to mock the TrackChangesBuilder import (the script path may not exist in CI) — use a temp file or mock `_load_trackchanges_module`.
**Warning signs:** Export test fails with `ImportError: TrackChangesBuilder script not found` because `~/workspace/lawfirm-profile/scripts/contract_review_trackchanges.py` doesn't exist in the test environment.

## Code Examples

### ArenaWorkflowCreator — onCreate emits ArenaWorkflowConfig
```typescript
// Source: packages/ui-core/src/components/ArenaWorkflowCreator.tsx lines 63-70, 134-148
export interface ArenaWorkflowCreatorProps {
  availableAgents: string[];
  onCreate: (config: ArenaWorkflowConfig) => void;
  disabled?: boolean;
}
// submit() builds: { arena_id, mode, agent_slots, task_instruction, reference_dir, max_rounds }
// and calls props.onCreate(config). The parent does the HTTP POST.
```

### createArenaStream — SSE store signature
```typescript
// Source: packages/ui-core/src/stores/arenaStream.ts lines 30-45, 111
export interface ArenaStreamOptions {
  client: PlatformApiClient;
  arenaId: string;
  onError?: (error: Error) => void;
}
export interface ArenaStreamStore {
  slotStates: () => ArenaSlotStates;   // Map<string, RenderState>
  metaState: () => ArenaMetaState;     // scores, reviews, synthesisContent, status
  streamEvents: () => Promise<void>;
  stop: () => void;
}
export function createArenaStream(options: ArenaStreamOptions): ArenaStreamStore
// Internally hits `${client.baseUrl}/v1/arena/${arenaId}/stream` with Last-Event-ID.
```

### SynthesisViewer — onExport callback shape
```typescript
// Source: packages/ui-core/src/components/SynthesisViewer.tsx lines 22-26, 36-49
export interface SynthesisViewerProps {
  synthesisContent: string | null;
  round: number;
  onExport: (params: { format: "docx"; path: string }) => void;
}
// exportDocx() calls file.save({ defaultPath: "综合最终版.docx", filters: [...] })
// then props.onExport({ format: "docx", path }). Parent must generate + write docx.
```

### FSSandbox.read_text_file — Phase 106 FS handler
```python
# Source: packages/acp-client/src/inkstatute_acp_client/fs_sandbox.py lines 203-228
class FSSandbox:
    def __init__(self, config: FSSandboxConfig) -> None: ...
    def read_text_file(self, path: str | Path) -> str:
        """Validate path (5 layers) then read UTF-8 text with size cap."""
        resolved = self.validate_path(path)
        size = resolved.stat().st_size
        if size > self.config.max_file_size:
            raise FSSandboxError(...)
        return resolved.read_text(encoding="utf-8")

# FSSandboxConfig: allowed_root, allowed_extensions (default text allowlist), max_file_size (1MB)
# ReferenceSanitizer.sanitize(content, path) → delimiter-wrapped content + injection detection log
```

### arena-service route + handler pattern (for export endpoint)
```python
# Source: services/arena-service/src/arena_service/app.py lines 37-51, 389-437
OPERATION_EXPORT_ARENA = "export_arena"
# Add to OPERATIONS tuple.

# In _parse_route (after line 427):
if method == "POST" and len(parts) == 3 and parts[0] == "arena" and parts[2] == "export":
    return OPERATION_EXPORT_ARENA, {"arena_id": parts[1]}

# In dispatch (after line 160):
if operation == OPERATION_EXPORT_ARENA:
    return await self._handle_export_arena(ctx, path_params, body_dict)

# Handler delegates to engine via getattr (same pattern as _handle_cancel_arena):
async def _handle_export_arena(self, ctx, path_params, body):
    arena_id = path_params.get("arena_id", "")
    export = getattr(self._engine, "export_arena", None)
    if not callable(export):
        return _not_implemented("export_arena")
    result = export(arena_id, dict(body))
    ...
    return {"status": 200, "body": data}
```

### agent-core track-changes tool (for export endpoint delegation)
```python
# Source: packages/agent-core/src/inkstatute_agent_core/tools/document_generate.py lines 157-337
# The tool is created via factory:
handler = create_document_generate_tool(sandbox, emitter, script_path)
# handler(args) where args = {
#   "input_docx_path": str,      # original contract docx
#   "review_items": list[dict],  # [{id, find_text, old_text, new_text, comment, level}]
#   "output_path": str,          # output docx path
#   "reviewer": str,             # optional reviewer name
# }
# Returns ToolResult with metadata.output_path.
# Lazy-imports TrackChangesBuilder via importlib (won't crash if lxml missing).
# DEFAULT_TRACKCHANGES_SCRIPT_PATH = env INKSTATUTE_TRACKCHANGES_SCRIPT or
#   ~/workspace/lawfirm-profile/scripts/contract_review_trackchanges.py
```

### BackendAdapter Protocol — the 10 methods (post-fix)
```python
# Source: packages/platform-runtime/src/platform_runtime/protocols.py lines 229-248
class BackendAdapter(Protocol):
    def backend_id(self) -> str: ...          # 1
    def backend_family(self) -> str: ...      # 2  ← added by SAFE-06
    def capabilities(self) -> AdapterCapabilitySet: ...  # 3
    async def bootstrap_check(self) -> BootstrapStatus: ...  # 4
    async def submit_run(self, req: RunRequest) -> RunHandle: ...  # 5
    async def get_run(self, run_id: str) -> Run: ...  # 6
    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]: ...  # 7
    async def cancel_run(self, run_id: str) -> Run: ...  # 8
    async def submit_approval(self, run_id: str, approval: Approval) -> Run: ...  # 9
    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]: ...  # 10
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| BackendAdapter 9 methods | BackendAdapter 10 methods (`backend_family()` added) | Phase 108 (SAFE-06) | 4 count/hash assertions must update; arena-engine cross-family enforcement uses it with try/except fallback |
| Arena UI components unbuilt | Arena UI components built + exported (UI-01..05) | Phase 110 | Desktop app only needs to wire them, not build them |
| arenaStream store unbuilt | arenaStream store built (UI-06/UI-07) | Phase 110 | Store exists but is not exported from index.ts — must add exports |
| No arena export endpoint | (this phase adds it) | Phase 111 | New `POST /v1/arena/{id}/export` delegating to agent-core track-changes tool |

**Deprecated/outdated:**
- The `BACKEND_ADAPTER_METHODS` frozenset in `services/qqbot-service/tests/test_host_safety_baseline.py` (lines 27-39) is missing `backend_family` — must be added alongside the count update.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | arena-service runs on the same machine as the desktop app (local-only, 127.0.0.1:8001), so the export endpoint can write the docx directly to the path chosen by the desktop's native save dialog. | Code Examples / Pitfall 4 | If arena-service is remote, the endpoint must return docx bytes and the desktop writes them via Tauri fs. Low risk — config says `bind_host = "127.0.0.1"`. |
| A2 | The `VITE_ARENA_SERVICE_TOKEN` env var will be used to pass the arena-service bearer token to the desktop app. | Pitfall 2 | If a different env var name is expected, the desktop arena client gets 401s. Low risk — follows existing `VITE_GATEWAY_URL` pattern. |
| A3 | The E2E export test can mock `_load_trackchanges_module` or use a temp script to avoid depending on `~/workspace/lawfirm-profile/scripts/contract_review_trackchanges.py` existing in CI. | Pitfall 6 | If the test requires the real script, it fails in CI. Medium risk — verify the script path exists or mock it. |

## Open Questions

1. **RESOLVED — Where should the arena page go in the desktop app?**
   - What we know: App.tsx uses signal-based screen switching (`"home" | "workspace"`), no router.
   - Resolution: Add `"arena"` to the screen union, add a `<Show when={screen() === "arena"}>` block, and create `apps/desktop/src/pages/ArenaPage.tsx`. Add a menu/nav entry to switch to it (e.g., a button on HomePage or a menu handler in menuHandlers.ts).

2. **RESOLVED — How does the desktop app call arena-service vs Gateway?**
   - What we know: Gateway is port 8000 (config/gateway.ts); arena-service is port 8001 (config.py). Both use PlatformApiClient.
   - Resolution: Create `apps/desktop/src/config/arena.ts` with a separate `PlatformApiClient` pointed at `VITE_ARENA_SERVICE_URL || "http://127.0.0.1:8001"` and `Authorization: Bearer ${VITE_ARENA_SERVICE_TOKEN}` header.

3. **RESOLVED — Does the export endpoint write the docx server-side or return bytes?**
   - What we know: arena-service is local-only (127.0.0.1); the desktop's native save dialog returns a real OS path; agent-core's track-changes tool writes directly to `output_path`.
   - Recommendation: The export endpoint accepts `{ output_path: str }` and writes the docx server-side (agent-core tool writes to that path). The desktop app's `onExport` handler calls the endpoint with the path from `file.save()`. This avoids streaming binary over HTTP. If the path is not accessible to the service process, fall back to returning bytes.

4. **RESOLVED — Where is `test_backend_adapter_has_exactly_9_methods` and what's the full fix scope?**
   - What we know: The named test exists in TWO files (qqbot-channel + qqbot-service). Plus `test_contract_count_freeze.py` and `contract_freeze_baseline.json` also assert the old count/hash.
   - Resolution: Update all four locations (see Pitfall 1). The qqbot-channel gate will still have the pre-existing recall test failure (accepted as carry).

5. **RESOLVED — Are createArenaStream / arenaEventReducer exported from ui-core?**
   - What we know: index.ts (lines 199-212) exports the arena UI components but NOT the stream store or reducer.
   - Resolution: Add exports for `createArenaStream`, `ArenaStreamStore`, `ArenaStreamOptions`, `arenaEventReducer`, `arenaMetaReducer`, `getSlotState`, `getAllSlotStates` to `packages/ui-core/src/index.ts`.

6. **RESOLVED — Does arena-engine already use reference_dir?**
   - What we know: `grep reference_dir packages/arena-engine/src` returns nothing. `ArenaWorkflowConfig.reference_dir` exists (arena_contract.py:16) but `_build_run_request` (mode1.py:226) ignores it.
   - Resolution: Modify `_build_run_request` (and the equivalent in mode2/3/4 if they have their own) to read reference files via `FSSandbox.read_text_file` + `ReferenceSanitizer.sanitize()` when `config.reference_dir` is set, injecting the sanitized content into `AgentTurn.metadata["reference_context"]` or `AgentTurn.content` (appended to task_instruction). The engine needs an `FSSandbox` instance — accept it as a constructor param or build one from `config.reference_dir`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Desktop app build + vitest | ✓ | v24.16.0 | — |
| Python 3.14 | arena-service / arena-engine / contract-test-suite gates | ✓ | 3.14.6 | — |
| Tauri CLI | Desktop native build (not needed for tests) | ✓ | ^2.11.2 (devDep) | Tests use jsdom, not Tauri runtime |
| lxml | agent-core track-changes docx generation (export endpoint) | Unknown — lazy-imported | — | Tool returns error ToolResult if lxml missing; E2E test should mock the script path |
| lawfirm-profile/scripts/contract_review_trackchanges.py | Export endpoint docx generation | Unknown — sibling repo, may not be cloned in CI | — | E2E test must mock `_load_trackchanges_module` or use `INKSTATUTE_TRACKCHANGES_SCRIPT` env override |

**Missing dependencies with no fallback:**
- None that block implementation. The track-changes script + lxml are only needed at runtime for real docx generation; tests can mock them.

**Missing dependencies with fallback:**
- `contract_review_trackchanges.py` + `lxml`: If absent, the export endpoint returns an error result (the tool handles ImportError gracefully). E2E tests should set `INKSTATUTE_TRACKCHANGES_SCRIPT` to a fixture script or mock the loader.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework (TS) | vitest ^3.0.0 (apps/desktop, packages/ui-core) |
| Framework (Python) | unittest stdlib (arena-service, arena-engine, contract-test-suite) |
| Config file (desktop) | apps/desktop/vite.config.ts (test.environment=jsdom, setupFiles=tests/setup.ts) |
| Config file (ui-core) | packages/ui-core/vite.config.ts |
| Quick run command (desktop) | `cd apps/desktop && npx vitest run` |
| Quick run command (arena-service) | `python -m unittest discover -s services/arena-service/tests` |
| Full suite command | `python scripts/run_v2_gates.py` (41 gates) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | Arena page renders ArenaWorkflowCreator + onCreate wires to POST /v1/arena | integration (TS) | `cd apps/desktop && npx vitest run tests/arena-page.test.tsx` | ❌ Wave 0 (new) |
| UI-02 | ParallelStreamPanel renders N slot streams from arenaStream store | integration (TS) | `cd apps/desktop && npx vitest run tests/arena-page.test.tsx` | ❌ Wave 0 (new) |
| UI-03 | ScoreCard displays scores from metaState | integration (TS) | `cd apps/desktop && npx vitest run tests/arena-page.test.tsx` | ❌ Wave 0 (new) |
| UI-04 | ReviewSummary displays reviews from metaState | integration (TS) | `cd apps/desktop && npx vitest run tests/arena-page.test.tsx` | ❌ Wave 0 (new) |
| UI-05 | SynthesisViewer onExport calls export endpoint + writes docx | integration (TS) | `cd apps/desktop && npx vitest run tests/arena-page.test.tsx` | ❌ Wave 0 (new) |
| UI-06 | arenaStream store wired into desktop arena page (SSE demultiplex) | integration (TS) | `cd apps/desktop && npx vitest run tests/arena-page.test.tsx` | ❌ Wave 0 (new) |
| UI-07 | Refresh preserves state (localStorage + Last-Event-ID reconnection) | unit (TS, already covered) | `cd packages/ui-core && npx vitest run tests/test_arena_stream.ts` | ✅ (existing in ui-arena gate) |
| GATE-01 | Gate-coverage + E2E export flow test | integration (Python) | `python -m unittest packages/contract-test-suite/tests/test_arena_e2e.py` | ✅ (exists, but export test missing — ❌ Wave 0 add) |
| SC-7 | BackendAdapter test count = 10 | unit (Python) | `python -m unittest packages/channels/qqbot/tests/test_v1_8_safety_baseline.py services/qqbot-service/tests/test_host_safety_baseline.py packages/contract-test-suite/tests/test_contract_count_freeze.py` | ✅ (exist, must update 9→10) |
| SC-9 | All 41 gates green (recall carry accepted) | gate suite | `python scripts/run_v2_gates.py` | ✅ (existing) |

### Sampling Rate
- **Per task commit:** `cd apps/desktop && npx vitest run` + `python -m unittest discover -s services/arena-service/tests` + `python -m unittest discover -s packages/arena-engine/tests`
- **Per wave merge:** `python scripts/run_v2_gates.py` (full 41-gate suite)
- **Phase gate:** Full suite green before `/gsd:verify-work` (qqbot-channel recall test failure accepted as carry — 40 gates fully green + qqbot-channel green except recall test)

### Wave 0 Gaps
- [ ] `apps/desktop/tests/arena-page.test.tsx` — covers UI-01..UI-06 (arena page wiring with mocked arena client + SSE)
- [ ] `apps/desktop/src/config/arena.ts` — arena-service PlatformApiClient (needed before arena-page test)
- [ ] `packages/ui-core/src/index.ts` — add exports for `createArenaStream`, `ArenaStreamStore`, `arenaEventReducer`, `arenaMetaReducer` (needed before desktop can import them)
- [ ] `packages/contract-test-suite/tests/test_arena_e2e.py` — add `test_export_flow` test covering create → stream → synthesis → export docx (GATE-01 / SC-8); mock `_load_trackchanges_module` or set `INKSTATUTE_TRACKCHANGES_SCRIPT` to a fixture
- [ ] Test-fix: update 4 BackendAdapter count assertions (9→10) + contract_freeze_baseline.json hash — no new files, just edits

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | arena-service Bearer token (constant-time compare in auth.py); desktop client sends `Authorization: Bearer <token>` |
| V3 Session Management | yes | arena-service is local-only (127.0.0.1:8001, never 0.0.0.0); localhost check BEFORE auth |
| V4 Access Control | yes | arena-service auth.require_localhost + auth.require_auth applied BEFORE routing to any handler (including the new export endpoint) — no bypass |
| V5 Input Validation | yes | Export endpoint must validate `arena_id` (non-empty) and `output_path` (non-empty); FSSandbox validates reference_dir paths (5-layer) |
| V6 Cryptography | no | No new crypto in this phase |

### Known Threat Patterns for arena-service + desktop integration

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Non-localhost arena-service access | Spoofing | `auth.require_localhost(client_address)` BEFORE auth (app.py:121) — reject 403 forbidden_remote |
| Missing/wrong arena-service token | Spoofing | `auth.require_auth(headers)` BEFORE routing (app.py:143) — reject 401 unauthorized |
| Path traversal via reference_dir | Tampering | `FSSandbox.validate_path` rejects `..` components (fs_sandbox.py:160) |
| Symlink escape via reference_dir | Tampering | `FSSandbox.validate_path` rejects symlinks at any component (fs_sandbox.py:176) |
| Prompt injection via reference file content | Tampering | `ReferenceSanitizer` delimiter-wraps content + detects injection patterns (sanitizer.py) |
| Output boundary bypass (backend/system notices reach lawyer) | Information Disclosure | `ArenaOutputBoundary` filters SSE events (engine_integration.py:189); export endpoint must not leak backend error details to the client |
| Permission auto-approval | Elevation | Binding constraint: never auto-approve `session/request_permission`; arena-service permission_safety.py enforces this (existing) |
| docx path injection (export endpoint writes to arbitrary path) | Tampering | Export endpoint must validate `output_path` — prefer re-using agent-core's `PathSandbox.validate()` before writing; do not write outside user-chosen paths |

## Sources

### Primary (HIGH confidence)
- `apps/desktop/src/App.tsx` — desktop app structure, signal-based screen switching, AdapterContext wiring
- `packages/ui-core/src/index.ts` — barrel exports (arena components exported, stream store/reducer NOT exported)
- `packages/ui-core/src/components/ArenaWorkflowCreator.tsx` — onCreate callback, ArenaWorkflowConfig shape
- `packages/ui-core/src/components/SynthesisViewer.tsx` — onExport callback shape, file.save() delegation
- `packages/ui-core/src/stores/arenaStream.ts` — createArenaStream signature, SSE consumption, localStorage + reconnection
- `packages/ui-core/src/reducers/arenaEventReducer.ts` — arenaEventReducer + arenaMetaReducer
- `services/arena-service/src/arena_service/app.py` — endpoint routing, _parse_route pattern, handler delegation
- `services/arena-service/src/arena_service/engine_integration.py` — ArenaServiceEngine, create_arena, stream_arena
- `services/arena-service/src/arena_service/config.py` — port 8001, local-only, env-driven token
- `packages/arena-engine/src/arena_engine/engine.py` — ArenaEngine, _build_backend_families (backend_family fallback)
- `packages/arena-engine/src/arena_engine/mode1.py` — _build_run_request (ignores reference_dir — to be wired)
- `packages/acp-client/src/inkstatute_acp_client/fs_sandbox.py` — FSSandbox.read_text_file, 5-layer validation
- `packages/acp-client/src/inkstatute_acp_client/sanitizer.py` — ReferenceSanitizer
- `packages/agent-core/src/inkstatute_agent_core/tools/document_generate.py` — create_document_generate_tool, TrackChangesBuilder lazy-import
- `packages/platform-runtime/src/platform_runtime/protocols.py` — BackendAdapter Protocol (10 methods post-SAFE-06)
- `packages/platform-contract/src/platform_contract/arena_contract.py` — ArenaWorkflowConfig.reference_dir field
- `packages/contract-test-suite/tests/test_contract_count_freeze.py` — BACKEND_ADAPTER_METHOD_COUNT = 9 (to update)
- `packages/contract-test-suite/tests/test_contract_freeze.py` — SHA-256 baseline enforcement
- `packages/contract-test-suite/fixtures/contract_freeze_baseline.json` — protocols.py hash (stale)
- `packages/channels/qqbot/tests/test_v1_8_safety_baseline.py` — test_backend_adapter_has_exactly_9_methods (to update)
- `services/qqbot-service/tests/test_host_safety_baseline.py` — test_backend_adapter_has_exactly_9_methods + BACKEND_ADAPTER_METHODS frozenset (to update)
- `scripts/run_v2_gates.py` — 41 gates, gate definitions, PYTHONPATH per gate
- `packages/contract-test-suite/tests/test_gate_coverage.py` — gate-coverage meta-test (asserts >= 40)
- `packages/contract-test-suite/tests/test_arena_e2e.py` — existing E2E test (no export test yet)
- Gate run output — confirmed 4 failures from backend_family() + 1 pre-existing recall carry

### Secondary (MEDIUM confidence)
- `apps/desktop/src/config/gateway.ts` — existing Gateway client pattern (port 8000) to mirror for arena client
- `apps/desktop/src/adapters/desktopFileAdapter.ts` — Tauri file.save() pattern
- `packages/platform-sdk-ts/src/index.ts` — PlatformApiClient constructor (baseUrl, fetchImpl, defaultHeaders)

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in workspace, no new installs, verified via package.json
- Architecture: HIGH — all components exist and were read in source; wiring points are concrete and verified
- Pitfalls: HIGH — gate failures reproduced by running `python scripts/run_v2_gates.py`; 4 failing assertions confirmed with exact line numbers and expected/actual values
- Test-fix scope: HIGH — all 4 affected files identified with exact line numbers; contract_freeze baseline hash mismatch confirmed (`afc6c808...` → `219ad588...`)

**Research date:** 2026-08-09
**Valid until:** 2026-09-08 (30 days — stable codebase, no external library version drift)
