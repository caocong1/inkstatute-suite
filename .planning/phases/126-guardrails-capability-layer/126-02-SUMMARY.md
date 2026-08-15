---
plan: 126-02
plan_name: Six Guardrails — Two Layers
phase: 126
status: complete
requirements-completed: [GRD-11, GRD-12, GRD-13, GRD-14, GRD-15, GRD-16]
commits:
  - 556992db  # feat(126-02): model-side guardrail anchors in legal-core preset
  - d9547011  # feat(126-02): guardrails scanner + mapper event derivation
  - 3bb25428  # feat(126-02): PermissionCard component — allow-once/reject-once, no batch
  - 70b1ea1a  # feat(126-02): Workspace guardrail wiring — 6 render-side guardrails
  - f1357b97  # test(126-02): restore e2e-workflow coverage — 9 V5 flows
  - d3f3fd6a  # feat(126-02): guardrails gate — dual-layer assertion (model + render)
date_completed: "2026-08-16"
---

# 126-02 Summary: Six Guardrails — Two Layers

## Overview

Implemented the complete two-layer guardrail system for the InkStatute v5.0 desktop product. Each of the six guardrails (GRD-11 through GRD-16) has both a **model-side** layer (preset prompt anchors) and a **render-side** layer (Rust scanner + SolidJS UI enforcement). Either layer missing counts as a bypass (regression-locked).

## Tasks Completed

### Task 1 — Model-side anchors (commit `556992db`)

Added all six `[GUARDRAIL:...]` anchors and `[SKILL_LOADING]` to:
- `presets/legal-core/preset.yml` — 6 guardrail anchors + 1 skill-loading anchor
- `presets/legal-core/agent.cordis.yml` — full persona with CLARIFY/HUMAN_REVIEW format specs

Verification: `grep -c '\[GUARDRAIL:' preset.yml` → 6; `grep -c '\[SKILL_LOADING\]'` → 1.

### Task 2 — Renderer-side text-derived guardrail events (commit `d9547011`)

- `apps/desktop/src-tauri/src/engine/guardrails.rs` — scanner functions for:
  - Citation markers (verified/retrieved/unverified)
  - `[CLARIFY:]` blocks (requires closing `]`)
  - `[HUMAN_REVIEW:]` blocks
  - Research-tool detection
- `apps/desktop/src-tauri/src/engine/mapper.rs` — on committed assistant messages:
  - Emits `message.completed` with `metadata.human_review`
  - Emits `citation.recorded` for parsed citations
  - Emits `elicitation.requested` for CLARIFY blocks
  - Tracks `research_performed` on research tool calls
  - Adds `research_performed` to `run.state_changed` metadata

15 Rust unit tests for guardrails scanner + 18 mapper tests (all green).

### Task 3 — Permission card (commit `3bb25428`)

- `apps/desktop/src/components/PermissionCard.tsx` — allow-once / reject-once only
- `apps/desktop/src/components/PermissionCard.css`
- `apps/desktop/tests/permission-card.test.tsx` — 7 tests

Safety properties:
- Exactly two buttons (allow once, reject once)
- Locks after decision
- 60-second auto-reject timeout
- Unknown permission kinds rejected by default
- No persistent/group/batch approval control
- Source code contains zero forbidden batch-approval keywords

### Task 4 — Workspace wiring + guardrail render tests (commit `70b1ea1a`)

- `apps/desktop/src/components/Workspace.tsx` — wires all 6 guardrails:
  - GRD-11: 待核实 bar (no verified citation + `research_performed === false`)
  - GRD-12: CitationPanel + citation trigger (reuses ui-core)
  - GRD-13: ClarificationCard + input lock (reuses ui-core)
  - GRD-14: 需人工复核 badge — no close button, survives re-renders
  - GRD-15: PermissionCard in chat stream
  - GRD-16: One-time confidentiality confirm dialog
- `apps/desktop/src/components/Workspace.css` — guardrail UI styles
- `apps/desktop/src/hooks/useEventStream.ts` — tracks `humanReview` + `researchPerformed` from raw envelopes (event-reducer.ts NOT modified)
- `apps/desktop/src/contexts/SessionContext.tsx` — exposes `humanReview()` + `researchPerformed()`
- `apps/desktop/tests/guardrails.test.tsx` — 8 render assertions

### Task 4.5 — e2e-workflow restoration (commit `f1357b97`)

- `apps/desktop/tests/e2e-workflow.test.tsx` — rebuilt with 11 tests (9 flows + 2 bonus)
- Flows: startup greeting, new session, streaming reply, clarification card, permission card, offline + history, settings 4 tabs, theme switch, window controls
- Header documents that original was deleted in Phase 125 with Gateway transport

### Task 5 — Guardrails gate (commit `d3f3fd6a`)

- `scripts/gates/v5/guardrails.mjs` — 14 dual-layer checks:
  - Model-layer: preset.yml has 6 GUARDRAIL anchors + SKILL_LOADING; agent.cordis.yml has CLARIFY/HUMAN_REVIEW formats
  - Render-layer: guardrails.rs scanners; mapper.rs research_performed; PermissionCard allow-once/reject-once only; Workspace.tsx wires all 6; guardrails.test.tsx exists; no batch-approval keywords
- `scripts/gates/v5/run-gates.mjs` — added guardrails as 4th gate
- Gate output: **4 passed, 0 failed**

## Coverage Evidence

### Rust tests
- `cargo test guardrails` → 15 passed, 0 failed
- `cargo test mapper` → 18 passed, 0 failed (includes 6 new guardrail-derived event tests)
- `cargo check` → clean

### TypeScript
- `bunx tsc --noEmit` → clean (0 errors)

### Vitest
- `bunx vitest run` → 69 tests passed (10 test files)
  - guardrails.test.tsx: 8 tests
  - permission-card.test.tsx: 7 tests
  - e2e-workflow.test.tsx: 11 tests
  - event-transport.test.tsx: 4 tests
  - settings-panel.test.tsx: 7 tests
  - app-update.test.tsx: 6 tests
  - adapters.test.ts: 12 tests
  - fts5-search.test.tsx: 3 tests
  - + 2 more files

### Gates
- `node scripts/gates/v5/guardrails.mjs` → all 14 checks PASS
- `node scripts/gates/v5/run-gates.mjs guardrails` → 1 passed, 0 failed
- `node scripts/gates/v5/run-gates.mjs token-budget` → 1 passed, 0 failed
- `node scripts/gates/v5/run-gates.mjs event-mapping` → 1 passed, 0 failed
- Full suite: 4 passed, 0 failed (engine-assembly may require extended timeout for cargo build)

### No-batch-approval hard check
```
grep -rniE '总是允许|always.?allow|批量批准|approve.?all' apps/desktop/src packages/ui-core/src
→ PASS: no batch approval
```

## Key Files Created/Modified

| File | Action | Purpose |
|---|---|---|
| `presets/legal-core/preset.yml` | Modified | 6 GUARDRAIL anchors + SKILL_LOADING |
| `presets/legal-core/agent.cordis.yml` | Modified | Full persona with guardrail instructions |
| `apps/desktop/src-tauri/src/engine/guardrails.rs` | Created | Text scanner for citations, CLARIFY, HUMAN_REVIEW |
| `apps/desktop/src-tauri/src/engine/mapper.rs` | Modified | Derive guardrail events from committed text |
| `apps/desktop/src-tauri/src/engine/mod.rs` | Modified | `pub mod guardrails;` |
| `apps/desktop/src/components/PermissionCard.tsx` | Created | Allow-once/reject-once permission card |
| `apps/desktop/src/components/PermissionCard.css` | Created | Permission card styles |
| `apps/desktop/tests/permission-card.test.tsx` | Created | 7 permission card tests |
| `apps/desktop/src/components/Workspace.tsx` | Modified | Wires all 6 guardrails into workspace |
| `apps/desktop/src/components/Workspace.css` | Modified | Guardrail UI styles |
| `apps/desktop/src/hooks/useEventStream.ts` | Modified | Tracks humanReview + researchPerformed |
| `apps/desktop/src/contexts/SessionContext.tsx` | Modified | Exposes humanReview() + researchPerformed() |
| `apps/desktop/tests/guardrails.test.tsx` | Created | 8 guardrail render assertions |
| `apps/desktop/tests/e2e-workflow.test.tsx` | Created | 11 e2e flow tests (9 flows + 2 bonus) |
| `scripts/gates/v5/guardrails.mjs` | Created | Dual-layer guardrail gate (14 checks) |
| `scripts/gates/v5/run-gates.mjs` | Modified | Added guardrails as 4th gate |

## Deviations

None.

## Notes

- `packages/ui-core/src/event-reducer.ts` was NOT modified (per binding constraint).
- Raw envelope metadata (human_review, research_performed) is tracked in the app-layer `useEventStream` hook, not in the immutable reducer.
- Human gates (HG-1 legal quality, HG-3 lawyer trial) remain DEFERRED — not auto-closed.
- The `event-reducer.ts` immutable reducer does not store `message.completed` metadata; this is by design and solved at the app layer.
