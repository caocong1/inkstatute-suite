# Phase 92 — Shared UI Core: Discussion Log

**Mode:** --auto
**Date:** 2026-08-08
**Phase:** 92 — Shared UI Core
**Requirements:** UI-01, UI-02, UI-03, UI-06

---

## Gray Area Identification

[--auto] Selected all gray areas: Component Extraction Strategy, Event Stream Consumer, Theme System, TypeScript Bindings, Build & Package Setup, ask_user Card Implementation, Five-Phase Progress Indicator, Document Preview & Citation Panel.

---

## Auto-Selected Decisions

### Area 1: Component Extraction Strategy

**Question:** "Which components to extract first, and how to handle Tauri-specific dependencies?"

**Options considered:**
1. Port all 23 components in one pass, strip Tauri deps via adapter/context injection pattern *(recommended)*
2. Port only chat-critical components first (ChatPanel, Workspace, DocPreview, CitationPanel, WorkflowProgressSteps), defer rest
3. Port components incrementally per plan, starting with theme + types + utils, then components

[auto] [Component Extraction Strategy] — Q: "Which components to extract first, and how to handle Tauri-specific dependencies?" → Selected: "Port all 23 components in one pass, strip Tauri deps via adapter/context injection pattern" (recommended default)

**Rationale:** Full extraction in one pass ensures UI-06 (single implementation) is satisfied immediately. Adapter pattern (FileAdapter, DropAdapter, AppInfoAdapter, WorkspaceAdapter) cleanly separates platform-specific operations from UI logic. SettingsPanel and SkillRefinementPanel are deferred to Phase 94 as they are desktop-admin-specific.

---

### Area 2: Event Stream Consumer

**Question:** "How should the SSE client and rendering state machine be designed?"

**Options considered:**
1. SSE consumer using PlatformApiClient.streamRun() + SolidJS signals as rendering state machine, driven by 13 event types *(recommended)*
2. Separate SSE client class + external state management (e.g., a finite state machine library)
3. Port lawyer-desktop's existing onChatStream/onAgentTrace pattern, adapted for SSE

[auto] [Event Stream Consumer] — Q: "How should the SSE client and rendering state machine be designed?" → Selected: "SSE consumer using PlatformApiClient.streamRun() + SolidJS signals as rendering state machine, driven by 13 event types" (recommended default)

**Rationale:** PlatformApiClient.streamRun() already yields SseFrame objects. A pure reducer function `(state, event) → state` is testable with fixtures and idempotent for replay. SolidJS signals provide reactivity without external state management libraries. This replaces lawyer-desktop's dual-listener (onChatStream + onAgentTrace) approach with a single SSE source.

---

### Area 3: Theme System

**Question:** "How to port 墨律 three themes (molv-tokens.css, data-theme='a|b|c')?"

**Options considered:**
1. Port molv-tokens.css + molv-base.css verbatim into ui-core/src/themes/, keep data-theme attribute switching *(recommended)*
2. Convert to CSS-in-JS or CSS Modules for better encapsulation
3. Rebuild theme system with a modern approach (e.g., Tailwind, vanilla-extract)

[auto] [Theme System] — Q: "How to port 墨律 three themes (molv-tokens.css, data-theme='a|b|c')?" → Selected: "Port molv-tokens.css + molv-base.css verbatim into ui-core/src/themes/, keep data-theme attribute switching" (recommended default)

**Rationale:** The theme system is pure CSS custom properties — no JS engine, no preprocessor. Porting verbatim preserves the design investment (80+ tokens × 3 themes). The 21 component CSS files all reference `var(--*)` tokens, so they port without color changes. PROJECT.md Key Decision: "墨律三主题与 23 个已打磨组件是设计资产."

---

### Area 4: TypeScript Bindings

**Question:** "How should platform-sdk-ts provide event type bindings — manual, codegen, or schema-first?"

**Options considered:**
1. Hand-written events.ts (already exists) + expand PlatformApiClient with Gateway endpoints *(recommended)*
2. Auto-generate events.ts from JSON Schemas via a new codegen script
3. Schema-first: generate both Python and TS from a single schema source

[auto] [TypeScript Bindings] — Q: "How should platform-sdk-ts provide event type bindings — manual, codegen, or schema-first?" → Selected: "Hand-written events.ts (already exists) + expand PlatformApiClient with Gateway endpoints" (recommended default)

**Rationale:** events.ts (187 lines) already exists and is hand-written, mirroring the JSON Schemas. The schemas are frozen (Phase 88 complete). Codegen would add complexity without value for simple interfaces. The existing generate_sdk.py handles PlatformApiClient regeneration from OpenAPI. ui-core imports types from platform-sdk-ts, never hand-writes them.

---

### Area 5: Build & Package Setup

**Question:** "How should ui-core be built and consumed by apps/web and apps/desktop?"

**Options considered:**
1. Vite library mode for build, workspace:* protocol for consumption, dual ESM/CJS output *(recommended)*
2. tsup for build (simpler config, faster)
3. Raw TypeScript source consumption (no build step, consumers compile directly)

[auto] [Build & Package Setup] — Q: "How should ui-core be built and consumed by apps/web and apps/desktop?" → Selected: "Vite library mode for build, workspace:* protocol for consumption, dual ESM/CJS output" (recommended default)

**Rationale:** Vite + vite-plugin-solid is the existing build pattern (lawyer-desktop uses it). Library mode produces consumable artifacts. Bun workspace protocol enables local linking. Peer dependencies (solid-js, solid-markdown) are provided by consumers. A gate must be added per AGENTS.md's gate-coverage requirement.

---

### Area 6: ask_user Card Implementation

**Question:** "How should the ask_user clarification card map to elicitation events?"

**Options considered:**
1. Map elicitation.requested to ClarificationCard with single-select/multi-select/free-text, submit via Gateway /v1/runs/{id}/elicitation *(recommended)*
2. Build a new card component from scratch, designed around the ElicitationRequestedPayload schema
3. Reuse apps/web_chat's render.ts approach (DOM-free render records)

[auto] [ask_user Card Implementation] — Q: "How should the ask_user clarification card map to elicitation events?" → Selected: "Map elicitation.requested to ClarificationCard with single-select/multi-select/free-text, submit via Gateway /v1/runs/{id}/elicitation" (recommended default)

**Rationale:** lawyer-desktop's ClarificationCard (in WorkflowProgressSteps.tsx) already supports all required modes (single/multi/free-text, 2-4 questions). The ElicitationRequestedPayload fields map directly to the card's props. Submission via Gateway HTTP replaces the Tauri invoke. The component's selection logic (toggleSelection, optionDisplayForAnswer) is tested and correct.

---

### Area 7: Five-Phase Progress Indicator

**Question:** "How should the 5-phase progress be rendered from events?"

**Options considered:**
1. Map phase.changed events to DraftingProgressSteps component, with phase-to-step index mapping *(recommended)*
2. Build a new progress component designed around FivePhase enum
3. Use WorkflowProgressSteps (dynamic) as the sole progress indicator, derive phase from tool/thought events

[auto] [Five-Phase Progress Indicator] — Q: "How should the 5-phase progress be rendered from events?" → Selected: "Map phase.changed events to DraftingProgressSteps component, with phase-to-step index mapping" (recommended default)

**Rationale:** DraftingProgressSteps (77 lines) already has 5 steps with Chinese labels matching the FivePhase enum. The existing `phaseToActiveIndex()` function needs updating to accept FivePhase values directly. WorkflowProgressSteps (dynamic, tool-call-driven) is also ported as a complementary indicator. Both are driven by the event stream reducer.

---

### Area 8: Document Preview & Citation Panel

**Question:** "How should document preview and citation panel work in ui-core?"

**Options considered:**
1. Port DocPreview + CitationPanel, driven by artifact.created + citation.recorded events, document parsing via injected parser *(recommended)*
2. Rebuild document preview using a web-first approach (e.g., docx-preview library)
3. Use a simpler markdown-only preview, defer structured document rendering

[auto] [Document Preview & Citation Panel] — Q: "How should document preview and citation panel work in ui-core?" → Selected: "Port DocPreview + CitationPanel, driven by artifact.created + citation.recorded events, document parsing via injected parser" (recommended default)

**Rationale:** DocPreview (323 lines) and CitationPanel (105 lines) are polished components with structured article rendering, citation verification badges, and document download. The legalDocument.ts utils (JSON extraction, markdown-to-legal-document, citation audit) are pure functions. A DocumentParser interface decouples the component from the parsing backend (Tauri invoke → Gateway HTTP). Event-driven: artifact.created populates the preview, citation.recorded populates the panel.

---

## Summary

| # | Gray Area | Selected Option | Key Rationale |
|---|-----------|----------------|---------------|
| 1 | Component Extraction Strategy | Port all 23, adapter pattern for Tauri deps | Full extraction satisfies UI-06 immediately |
| 2 | Event Stream Consumer | PlatformApiClient.streamRun() + SolidJS signals + pure reducer | Single SSE source, fixture-testable, idempotent replay |
| 3 | Theme System | Port molv-tokens.css + molv-base.css verbatim | Preserves design investment, pure CSS custom properties |
| 4 | TypeScript Bindings | Hand-written events.ts (exists) + expand PlatformApiClient | Schemas frozen, codegen adds no value |
| 5 | Build & Package | Vite library mode + workspace:* + dual ESM/CJS | Matches existing Vite pattern, bun workspace linking |
| 6 | ask_user Card | Port ClarificationCard, map elicitation.requested, submit via Gateway | Existing card supports all modes, tested logic |
| 7 | Five-Phase Progress | Map phase.changed to DraftingProgressSteps | 5 steps already match FivePhase enum |
| 8 | Document Preview & Citation | Port DocPreview + CitationPanel, injected parser, event-driven | Polished components, pure utils, adapter for backend |

**Total gray areas:** 8
**All auto-selected with recommended option.**
