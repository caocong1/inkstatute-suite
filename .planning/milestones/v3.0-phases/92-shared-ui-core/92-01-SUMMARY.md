---
phase: 92-shared-ui-core
plan: 01
subsystem: ui-core
tags: [solidjs, ui-core, theme, event-reducer, chat-panel, sse-consumer, tracer]
requires:
  - phase: 88
    provides: Event vocabulary
  - phase: 91
    provides: Gateway SSE
provides:
  - packages/ui-core scaffold (package.json, vite.config.ts, tsconfig.json, tsconfig.build.json)
  - 墨律 three-theme system (molv-tokens.css, molv-base.css, theme.ts store)
  - Event reducer — pure function mapping 13 unified event types to RenderState
  - EventStreamStore — SSE consumer with SolidJS signals + Last-Event-ID reconnection
  - Adapter interfaces — FileAdapter, DropAdapter, AppInfoAdapter, WorkspaceAdapter, DocumentParser
  - ChatPanel component — stripped Tauri deps, wired to event reducer state
  - Fixture-driven tests — 15 events covering all 13 types, 35 vitest tests passing
  - ui-core gate registered in run_v2_gates.py (32 gates total)
affects:
  - 92-02
  - 92-03
  - 92-04
key-files:
  - packages/ui-core/package.json
  - packages/ui-core/tsconfig.json
  - packages/ui-core/tsconfig.build.json
  - packages/ui-core/vite.config.ts
  - packages/ui-core/src/index.ts
  - packages/ui-core/src/event-reducer.ts
  - packages/ui-core/src/stores/theme.ts
  - packages/ui-core/src/stores/eventStream.ts
  - packages/ui-core/src/adapters/index.ts
  - packages/ui-core/src/components/ChatPanel.tsx
  - packages/ui-core/src/components/ChatPanel.css
  - packages/ui-core/src/themes/molv-tokens.css
  - packages/ui-core/src/themes/molv-base.css
  - packages/ui-core/src/themes/index.ts
  - packages/ui-core/src/types/workflow.ts
  - packages/ui-core/src/types/events.ts
  - packages/ui-core/src/shims/debug.ts
  - packages/ui-core/tests/event-reducer.test.ts
  - packages/ui-core/tests/chat-panel.test.tsx
  - packages/ui-core/tests/fixtures/events.json
  - packages/ui-core/tests/test_ui_core.py
  - packages/ui-core/tests/setup.ts
  - scripts/run_v2_gates.py
  - package.json (root workspace config)
  - packages/platform-sdk-ts/package.json (exports field added)
  - packages/platform-sdk-ts/src/index.ts (DELETE/POST/GET constants added)
  - packages/contract-test-suite/tests/test_audit_v2_requirements.py (gate count 31→32)
key-decisions:
  - "Event reducer as pure function (state, event) → state — no signals, no DOM, independently testable with fixtures"
  - "Adapter pattern for platform-specific operations — interfaces only, implementations injected by consumers"
  - "Vite library mode with vite-plugin-solid, dual ESM/CJS output, tsc --emitDeclarationOnly for .d.ts"
  - "Gate uses Python unittest wrapper (test_ui_core.py) that runs vitest via subprocess — uniform gate system"
  - "Idempotent reducer — message.completed, artifact.created, citation.recorded deduplicate on replay"
  - "tsconfig.build.json separates declaration generation (src only, rootDir=src) from typechecking (src+tests)"
  - "Root package.json created with workspaces config for bun workspace:* protocol resolution"
  - "platform-sdk-ts package.json exports field added for ./events subpath import"
  - "platform-sdk-ts index.ts: missing DELETE/POST/GET constants added (pre-existing auto-generation bug)"
patterns-established:
  - "Pure reducer pattern: (RenderState, RunEventEnvelope) → RenderState — single source of UI state"
  - "Adapter injection via SolidJS context: AdapterContext.Provider + useAdapters() hook"
  - "Fixture-driven testing: JSON fixture events fed through reducer, assertions on resulting state"
  - "Gate wrapper pattern: Python test_ui_core.py validates structure + runs vitest via subprocess"
  - "CSS verbatim port: theme and component CSS files copied unchanged, all use var(--*) tokens"
  - "Type re-export barrel: types/events.ts re-exports all types from platform-sdk-ts/events"
requirements-completed:
  - partial — UI-01 in progress (scaffold + theme + ChatPanel done; 16 more components in 92-02)
  - partial — UI-02 in progress (event reducer + EventStreamStore done; full integration in 92-04)
coverage:
  requirements: 2
  success_criteria: partial
  tasks: 8
  tests: 35 vitest + 7 Python gate = 42 total
  gates: 32 (31 existing + 1 new ui-core)
duration: 1 session
completed: 2026-08-08
status: complete
---

# Plan 92-01 Summary — Wave 1 Tracer

## What Was Built

The minimal vertical slice proving the end-to-end flow: theme tokens → ChatPanel → event reducer → fixture event stream → rendering test. The `packages/ui-core` package is scaffolded, the 墨律 three-theme system is ported, the event reducer handles all 13 unified event types, the ChatPanel renders from fixture event stream state, and all tests pass — with zero `@tauri-apps/*` dependencies.

## Task Execution Log

| Task | Commit | Description |
|------|--------|-------------|
| 92-01-01 | `635822b` | Scaffold packages/ui-core + register gate |
| 92-01-02 | `bb70f82` | Port 墨律 three-theme system |
| 92-01-03 | `e58ca0f` | Event reducer — 13 unified event types to RenderState |
| 92-01-04 | `9d4f51e` | EventStreamStore — SSE consumer + Last-Event-ID reconnection |
| 92-01-05 | `888babb` | Adapter interfaces — FileAdapter, DropAdapter, etc. |
| 92-01-06 | `603f00d` | Port ChatPanel — strip Tauri deps, wire to reducer |
| 92-01-07 | `22f0ee1` | Fixture-driven tests — 35 vitest tests, all 13 event types |
| 92-01-08 | `e161806` | Build artifacts + type declarations + zero Tauri deps |

## Acceptance Criteria Results

### Task 92-01-01 — Scaffold + Gate
- ✅ package.json with @inkstatute/ui-core, private, peer deps, workspace:* dependency
- ✅ tsconfig.json with strict, jsx: preserve, jsxImportSource: solid-js
- ✅ vite.config.ts with vite-plugin-solid, library mode, debug shim alias
- ✅ src/shims/debug.ts exists
- ✅ src/index.ts exists (minimal docstring)
- ✅ tests/setup.ts exists
- ✅ tests/fixtures/events.json exists
- ✅ `python scripts/run_v2_gates.py --list` includes "ui-core"
- ✅ Gate PYTHONPATH includes ui-core/src, platform-sdk-ts/src, platform packages
- ✅ No existing gate modified (diff purely additive)
- ✅ `python scripts/run_v2_gates.py` exits 0
- ✅ gate-coverage-meta-test passes

### Task 92-01-02 — Theme System
- ✅ molv-tokens.css with :root, [data-theme="a"], [data-theme="b"], [data-theme="c"]
- ✅ molv-base.css references var(--*) tokens
- ✅ theme.ts with ThemeVariant, useTheme(), setTheme(), cycleTheme()
- ✅ themes/index.ts imports both CSS files as side-effect imports
- ✅ useTheme and ThemeVariant exported from index.ts
- ✅ Zero @tauri-apps references
- ✅ localStorage key "ml-theme"
- ✅ document.documentElement.setAttribute("data-theme", variant)

### Task 92-01-03 — Event Reducer
- ✅ types/workflow.ts with all 6 interfaces
- ✅ types/events.ts re-exports all types from platform-sdk-ts/events
- ✅ event-reducer.ts with RenderState, ChatMessage, initialState, reduce, traceToolLabel, normalizeClarification
- ✅ reduce() is pure — no createSignal, no DOM, no side effects
- ✅ reduce() handles all 13 event types (15 case statements including tool_call sub-types)
- ✅ reduce() updates lastSeq on every event
- ✅ traceToolLabel maps legal_search, mcp__* law, ask_user correctly
- ✅ normalizeClarification caps at 4 questions, generates option IDs
- ✅ Zero @tauri-apps references
- ✅ All functions exported from index.ts

### Task 92-01-04 — EventStreamStore
- ✅ eventStream.ts with createEventStream(), EventStreamStore, EventStreamOptions
- ✅ Returns { state, streamEvents, stop }
- ✅ Uses reduce() from event-reducer.ts
- ✅ Last-Event-ID header sent when lastSeq > 0
- ✅ Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s
- ✅ stop() cancels timers and aborts stream
- ✅ Zero @tauri-apps references

### Task 92-01-05 — Adapter Interfaces
- ✅ FileAdapter with open() and save()
- ✅ DropAdapter with classifyDroppedPaths()
- ✅ AppInfoAdapter with getVersion() and optional checkForUpdate()/installUpdate()
- ✅ WorkspaceAdapter with listFiles()
- ✅ DocumentParser with parseLegalDocument()
- ✅ AdapterContext is SolidJS createContext
- ✅ useAdapters() throws if outside provider
- ✅ Zero @tauri-apps references (including comments)

### Task 92-01-06 — ChatPanel
- ✅ ChatPanel.tsx renders message thread, streaming buffer, composer, stage pill
- ✅ ChatPanel.css uses var(--*) tokens
- ✅ Receives RenderState via props
- ✅ Uses useAdapters() for file/drop
- ✅ Uses SolidMarkdown with remarkGfm
- ✅ Ctrl+Enter sends via props.onSend
- ✅ Send button disabled when runStatus === "running"
- ✅ Zero @tauri-apps references
- ✅ Zero invoke() calls

### Task 92-01-07 — Fixture Tests
- ✅ events.json with 15 RunEventEnvelope objects covering all 13 event types
- ✅ event-reducer.test.ts: 28 tests covering all event types, traceToolLabel, normalizeClarification, idempotency
- ✅ chat-panel.test.tsx: 7 tests covering message rendering, stage pill, composer, Ctrl+Enter, clarification
- ✅ npx vitest run exits 0 (35 tests pass)
- ✅ python scripts/run_v2_gates.py exits 0

### Task 92-01-08 — Build Verification
- ✅ vite build produces dist/index.js (ESM) and dist/index.cjs (CJS)
- ✅ tsc --emitDeclarationOnly produces dist/index.d.ts
- ✅ tsc --noEmit exits 0 (strict type checking passes)
- ✅ grep -r "@tauri-apps" packages/ui-core/src/ returns zero results
- ✅ grep -r "invoke(" packages/ui-core/src/ returns zero results
- ✅ grep -r "from \"@tauri-apps" packages/ui-core/ returns zero results
- ✅ python scripts/run_v2_gates.py exits 0 (all 32 gates green)
- ✅ Package exports include ".", "./themes", "./events"

## Deviations

1. **Root package.json created** — The plan did not explicitly mention creating a root `package.json` with workspace config, but bun's `workspace:*` protocol requires it. Created a minimal root package.json with `workspaces: ["packages/platform-sdk-ts", "packages/ui-core"]`.

2. **platform-sdk-ts/package.json exports field added** — The `@inkstatute/platform-sdk-ts/events` subpath import required an `exports` field in the platform-sdk-ts package.json. Added `.` and `./events` exports mapping to source .ts files.

3. **platform-sdk-ts/src/index.ts: DELETE/POST/GET constants added** — The auto-generated SDK was missing `const DELETE = "DELETE"`, `const POST = "POST"`, `const GET = "GET"` constants, causing tsc errors. Added them as a pre-existing bug fix.

4. **tsconfig.build.json created** — The main tsconfig includes both `src` and `tests` for typechecking. A separate `tsconfig.build.json` with `rootDir: "src"` and only `src` included is used for declaration generation, producing flat `dist/*.d.ts` files.

5. **Gate count test updated** — `test_audit_v2_requirements.py` expected 31 gates; updated to 32 after adding the ui-core gate.

6. **Idempotency deduplication** — The plan mentioned the reducer should be idempotent but didn't specify deduplication logic. Added deduplication for `message.completed` (by message ID), `artifact.created` (by artifact_id), and `citation.recorded` (by source) to handle replayed events correctly.

## Self-Check: PASSED

- ✅ All 8 tasks executed and committed
- ✅ All acceptance criteria PASS
- ✅ packages/ui-core scaffold created (package.json, vite.config.ts, tsconfig.json)
- ✅ Theme system ported (molv-tokens.css, molv-base.css, theme.ts)
- ✅ Event reducer handles all 13 event types
- ✅ ChatPanel renders from fixture event stream
- ✅ Fixture-driven rendering tests pass (35 vitest tests)
- ✅ ui-core gate registered in run_v2_gates.py
- ✅ All gates green (32 total)
- ✅ Build artifacts produced (dist/index.js, dist/index.cjs, dist/index.d.ts)
- ✅ Zero @tauri-apps dependencies
- ✅ SUMMARY.md with Self-Check: PASSED
