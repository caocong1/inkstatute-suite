# Phase 92: Shared UI Core — Summary

**Phase:** 92 (shared-ui-core)
**Status:** COMPLETE
**Date:** 2026-08-08
**Plans:** 4 (all complete)
**Gates:** 32/32 green
**Tests:** 105 vitest tests (ui-core) + 21 pytest tests (platform-sdk-ts)

## What Was Built

### Plan 92-01: Scaffold + Theme + Reducer + ChatPanel + Fixtures
- Created `packages/ui-core` with SolidJS + TypeScript + Vite build pipeline
- Ported molv-tokens.css and molv-base.css (墨律三主题: a/b/c)
- Implemented event-reducer.ts (unified event stream consumer → render state machine)
- Ported ChatPanel.tsx with streaming message rendering
- Created fixture-based integration tests

### Plan 92-02: Chat Interaction Components
- Ported ClarificationCard.tsx (ask_user: single-choice, multi-choice, free-text)
- Ported MessageFeedback.tsx (thumbs up/down + text feedback)
- Ported DraftingProgressSteps.tsx (five-phase progress indicator)
- Ported WorkflowProgressSteps.tsx

### Plan 92-03: Document Preview + Citations
- Ported DocPreview.tsx (document preview with section navigation)
- Ported CitationPanel.tsx (law/case citation tabs with verification status)
- Ported legal types (LegalDocument, Citation, CitationRecord)
- Implemented renderSegs and groupCitations utilities

### Plan 92-04: Full Integration (this plan)
- Ported Icons.tsx (30+ custom SVG icons from lawyer-desktop)
- Ported MentionComposer.tsx + MentionMenu.tsx (@-mention autocomplete)
- Ported TitleBar.tsx (stripped Tauri deps → WindowAdapter)
- Ported HomePage.tsx (stripped Tauri deps → FileAdapter/DropAdapter)
- Ported ConversationDrawer.tsx (stripped useConversation → ConversationStore interface)
- Ported AgentTracePanel.tsx (developer trace panel, stripped Tauri deps)
- Ported jsonHighlight.tsx (lexical JSON syntax highlighting)
- Ported trace store (TraceTurn/TraceEntry/AgentTraceEvent types)
- Ported docTypes.ts (16 document type cards + icon inference)
- Ported evidenceFlow.ts (path-to-alias, directory extraction)
- Ported conversationTitle.ts (title validation)
- Expanded platform-sdk-ts: all 13 Gateway endpoints + Last-Event-ID support in streamRun()
- Marked apps/web_chat as deprecated (@deprecated annotations in index.ts, render.ts, README.md)

## Architecture Decisions

### Tauri Dependency Removal
All ported components had `@tauri-apps/*` dependencies stripped and replaced with adapter interfaces:
- **WindowAdapter** — replaces `getCurrentWindow()` for minimize/maximize/close/drag
- **FileAdapter** — replaces `@tauri-apps/plugin-dialog` `open()` for file/directory picking
- **DropAdapter** — replaces `getCurrentWebview().onDragDropEvent()` for native drag-and-drop
- **ConversationStore** — replaces `useConversation()` store with injectable interface
- **AppInfoAdapter** — already existed for app metadata

### Adapter Injection Pattern
All platform-specific functionality is injected via SolidJS context (`AdapterContext`). Web consumers provide web-compatible adapters; desktop consumers provide Tauri-backed adapters. Components never import `@tauri-apps/*` directly.

### platform-sdk-ts Expansion
- Regenerated SDK from Gateway OpenAPI document (13 endpoints)
- Added `Last-Event-ID` header parameter support to `streamRun()` for SSE reconnection
- Updated generator (`generate_sdk.py`) to handle header parameters for stream operations
- Updated tests to verify all Gateway endpoints and Last-Event-ID support

## Success Criteria Verification

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `packages/ui-core` exists, ported components + themes, no `@tauri-apps/*` deps | ✅ Verified: `grep -r "@tauri-apps" packages/ui-core/src/` returns nothing |
| 2 | Unified event stream client (SSE consumer + render state machine) in ui-core | ✅ `eventStream.ts` + `event-reducer.ts` with 28 reducer tests |
| 3 | Streaming chat, ask_user, doc preview, citation panel, 5-phase progress in ui-core | ✅ ChatPanel, ClarificationCard, DocPreview, CitationPanel, DraftingProgressSteps |
| 4 | `platform-sdk-ts` generates unified event vocabulary TS bindings, ui-core uses it | ✅ 13 Gateway endpoints, events.ts, ui-core imports from platform-sdk-ts |
| 5 | No second chat implementation; `apps/web_chat` marked deprecated | ✅ `@deprecated` in index.ts, render.ts, README.md |
| 6 | `ui-core` has build artifacts and type declarations | ✅ `dist/index.js`, `dist/index.cjs`, `dist/index.d.ts`, `dist/ui-core.css` |

## Files Created/Modified

### New Files (Plan 92-04)
- `packages/ui-core/src/components/Icons.tsx`
- `packages/ui-core/src/components/MentionComposer.tsx` + `.css`
- `packages/ui-core/src/components/MentionMenu.tsx` + `.css`
- `packages/ui-core/src/components/TitleBar.tsx` + `.css`
- `packages/ui-core/src/components/HomePage.tsx` + `.css`
- `packages/ui-core/src/components/ConversationDrawer.tsx` + `.css`
- `packages/ui-core/src/components/AgentTracePanel.tsx` + `.css`
- `packages/ui-core/src/stores/trace.ts`
- `packages/ui-core/src/types/trace.ts`
- `packages/ui-core/src/types/conversation.ts`
- `packages/ui-core/src/utils/jsonHighlight.tsx`
- `packages/ui-core/src/utils/docTypes.ts`
- `packages/ui-core/src/utils/evidenceFlow.ts`
- `packages/ui-core/src/utils/conversationTitle.ts`
- `packages/ui-core/tests/icons.test.tsx`

### Modified Files
- `packages/ui-core/src/index.ts` (added exports for all new components/types)
- `packages/ui-core/src/adapters/index.ts` (added WindowAdapter)
- `packages/platform-sdk-ts/src/index.ts` (regenerated with 13 endpoints + Last-Event-ID)
- `packages/platform-sdk-ts/scripts/generate_sdk.py` (header param support, method quoting fix)
- `packages/platform-sdk-ts/tests/test_sdk_generation.py` (updated for Gateway endpoints)
- `packages/contract-test-suite/tests/test_phase12_channel_client_surface.py` (updated for Gateway)
- `services/gateway/src/gateway/openapi.py` (added "remote/thin" to description)
- `apps/platform_api/openapi/platform-api.json` (regenerated)
- `apps/web_chat/src/index.ts` (deprecated)
- `apps/web_chat/src/render.ts` (deprecated)
- `apps/web_chat/README.md` (deprecated)

## Commits
1. `feat(92-04): port Icons — full custom SVG icon set (30+ icons)`
2. `feat(92-04): port MentionComposer + MentionMenu — @-mention autocomplete`
3. `feat(92-04): port TitleBar + HomePage — strip Tauri deps, use WindowAdapter/FileAdapter/DropAdapter`
4. `feat(92-04): port ConversationDrawer + AgentTracePanel + jsonHighlight + trace store`
5. `feat(92-04): expand platform-sdk-ts — all 13 Gateway endpoints + Last-Event-ID support in streamRun()`
6. `deprecate(92-04): mark apps/web_chat deprecated — superseded by ui-core (UI-06)`
7. `fix(92-04): fix import paths, SDK method quoting, gate tests — all 32 gates green`

## Next Phase
Phase 93: Web Client — responsive web application using `packages/ui-core`, communicating with the platform via Gateway HTTP/SSE.
