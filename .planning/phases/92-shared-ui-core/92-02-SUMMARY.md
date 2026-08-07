---
phase: 92-shared-ui-core
plan: 02
subsystem: ui-core
tags: [clarification-card, drafting-progress, message-feedback, doc-loader, ask-user, five-phase, workflow-progress]
requires:
  - phase: 92-01
    provides: ui-core scaffold + event reducer + ChatPanel
provides:
  - ClarificationCard component — ask_user card with single-select, multi-select, free-text (elicitation.requested → ClarificationRequest)
  - DraftingProgressSteps component — five-phase progress indicator (phase.changed → FivePhase mapping)
  - MessageFeedback component — thumbs up/down + comment + dimension chips (Gateway POST /v1/feedback via callback)
  - DocDraftingLoader component — skeleton shimmer animation during document streaming
  - WorkflowProgressSteps component — full workflow notice + ClarificationCard + ModeSwitchCard + WorkflowSuggestions
  - Minimal Icons component (check, sparkle) — subset of full 30+ icon set
  - messageFeedbackLogic utility — pure functions for feedback state formatting
  - Extended WorkflowState type with mode, mode_label, suggestions, message_id fields
  - Fixture-driven tests — 33 new vitest tests (9 clarification + 16 drafting + 8 feedback)
  - ChatPanel upgraded to use full WorkflowProgressSteps (replacing simplified tracer versions)
affects:
  - 92-04
key-files:
  - packages/ui-core/src/components/ClarificationCard.tsx
  - packages/ui-core/src/components/ClarificationCard.css
  - packages/ui-core/src/components/DraftingProgressSteps.tsx
  - packages/ui-core/src/components/DraftingProgressSteps.css
  - packages/ui-core/src/components/MessageFeedback.tsx
  - packages/ui-core/src/components/MessageFeedback.css
  - packages/ui-core/src/components/DocDraftingLoader.tsx
  - packages/ui-core/src/components/DocDraftingLoader.css
  - packages/ui-core/src/components/WorkflowProgressSteps.tsx
  - packages/ui-core/src/components/WorkflowProgressSteps.css
  - packages/ui-core/src/components/Icons.tsx
  - packages/ui-core/src/utils/messageFeedbackLogic.ts
  - packages/ui-core/src/types/workflow.ts
  - packages/ui-core/src/components/ChatPanel.tsx
  - packages/ui-core/src/index.ts
  - packages/ui-core/tests/clarification-card.test.tsx
  - packages/ui-core/tests/drafting-progress.test.tsx
  - packages/ui-core/tests/message-feedback.test.tsx
  - packages/ui-core/tests/fixtures/elicitation-events.json
  - packages/ui-core/tests/fixtures/phase-events.json
key-decisions:
  - "ClarificationCard takes ClarificationRequest directly via props (not WorkflowState) — cleaner, more testable, decoupled from workflow state"
  - "DraftingProgressSteps phaseToActiveIndex updated from V2 strings (thinking/tool/streaming/review) to FivePhase values (research/intake/retrieval/draft/review) — null maps to -1"
  - "MessageFeedback replaces Tauri submitMessageFeedback invoke with onSubmit callback prop — consumer wires to PlatformApiClient POST /v1/feedback"
  - "MessageFeedback interface simplified: takes messageId + onSubmit + initialRating/initialComment/initialDimensions instead of full Message object"
  - "Minimal Icons component created with only check + sparkle icons — full 30+ icon set deferred to later plan"
  - "WorkflowState extended with optional mode, mode_label, suggestions, message_id fields to support full WorkflowProgressSteps"
  - "CSS split: ClarificationCard.css has .clarify-* rules, WorkflowProgressSteps.css has .workflow-notice + .workflow-suggestions rules, DraftingProgressSteps.css has .draft-step rules"
  - "ChatPanel upgraded from simplified tracer WorkflowNotice/ClarificationCard to full WorkflowProgressSteps component"
patterns-established:
  - "Callback prop pattern for Gateway submission: components call props.onSubmit(data), consumer wires to PlatformApiClient — no hard-coupling to SDK"
  - "Fixture-driven component testing: JSON fixture events → normalizeClarification() → ClarificationRequest → render → assert DOM"
  - "CSS co-location with verbatim port: component CSS files copied unchanged from lawyer-desktop, all use var(--*) tokens"
  - "Pure function extraction: messageFeedbackLogic.ts contains pure functions (feedbackStatusText, ratingClickAction) separated from component"
  - "FivePhase mapping as pure exported function: phaseToActiveIndex(phase) → number, independently testable"
  - "Minimal icon set pattern: create only the icons needed by current components, extend later"
requirements-completed:
  - partial — UI-03 in progress (ClarificationCard + DraftingProgressSteps + MessageFeedback + DocDraftingLoader done; DocPreview + CitationPanel in 92-03)
coverage:
  requirements: 1
  success_criteria: partial
  tasks: 5
  tests: 33 new vitest (9 clarification + 16 drafting + 8 feedback) + 7 Python gate = 40 new total; 68 vitest total (35 from 92-01 + 33 new)
  gates: 32 (unchanged — all green)
duration: 1 session
completed: 2026-08-08
status: complete
---

# Plan 92-02 Summary — Wave 2 Chat Interaction Components

## What Was Built

Ported four chat interaction components from lawyer-desktop into `packages/ui-core`, plus the full `WorkflowProgressSteps` component that integrates them. All components are independently testable with fixture events — no live SSE connection needed. All components receive state via props from the `RenderState` produced by the event reducer (established in Plan 92-01), and use callback props for any platform-specific operations (Gateway submission).

### Components Ported

1. **ClarificationCard** — The ask_user clarification card with single-select, multi-select, and free-text support. Maps to `elicitation.requested` events via `normalizeClarification()`. Takes `ClarificationRequest` directly as a prop (cleaner than the lawyer-desktop version which took `WorkflowState`). Submit button calls `props.onSubmit(answers)` — consumer wires to `POST /v1/runs/{id}/elicitation`.

2. **DraftingProgressSteps** — Five-phase progress indicator with updated `phaseToActiveIndex()` mapping for `FivePhase` values (`research`→0, `intake`→1, `retrieval`→2, `draft`→3, `review`→4, `null`→-1). The `DRAFTING_STEPS` array has 5 steps with Chinese labels. Driven by `phase.changed` events.

3. **MessageFeedback** — Thumbs up/down + comment textarea + dimension chips (案由, 法条, 结构, 检索, 其他). Replaced the Tauri `submitMessageFeedback` invoke with a callback prop `onSubmit(messageId, rating, comment, dimensions)`. Consumer wires to `POST /v1/feedback`.

4. **DocDraftingLoader** — Pure presentational skeleton shimmer animation (24 lines). 8 `.sk-line` elements at specified widths. The `sk` keyframes animation is in `molv-base.css` (ported in 92-01).

5. **WorkflowProgressSteps** — Full workflow progress component containing `WorkflowNotice` (collapsible progress header), `ClarificationCard` (imported from standalone), `ModeSwitchCard` (pre-turn confirmation), and `WorkflowSuggestions` (clickable suggestion chips). ChatPanel upgraded to use this instead of the simplified tracer versions.

### Supporting Files

- **Icons.tsx** — Minimal icon set with `check` and `sparkle` icons (subset of the full 30+ icon set, to be expanded in a later plan).
- **messageFeedbackLogic.ts** — Pure functions `feedbackStatusText()` and `ratingClickAction()` ported from lawyer-desktop.
- **WorkflowState** extended with optional `mode`, `mode_label`, `suggestions`, `message_id` fields.
- **Fixtures** — `elicitation-events.json` (2 questions: single-select + multi-select) and `phase-events.json` (5 phase.changed events, one per phase).

## Task Execution Log

| Task | Commit | Description |
|------|--------|-------------|
| 92-02-01 | `6480773` | Port ClarificationCard — ask_user card with single/multi/free-text, Gateway submission |
| 92-02-02 | `c42d4cf` | Port DraftingProgressSteps — five-phase progress with FivePhase mapping |
| 92-02-03 | `6304744` | Port MessageFeedback — thumbs up/down + comment + dimensions, Gateway submission |
| 92-02-04 | `593d302` | Port DocDraftingLoader — skeleton animation for document streaming |
| 92-02-05 | `2d1a5aa` | Port full WorkflowProgressSteps — WorkflowNotice + ModeSwitchCard + WorkflowSuggestions + ClarificationCard integration |

## Acceptance Criteria Results

### Task 92-02-01 — ClarificationCard
- ✅ `ClarificationCard.tsx` exists with `ClarificationCard`, `ClarificationCardProps`
- ✅ `ClarificationCard.css` exists and uses `var(--*)` tokens
- ✅ Single-select: clicking an option selects it, clicking another replaces the selection
- ✅ Multi-select: clicking options toggles add/remove, "（可多选）" hint shown
- ✅ Free-text input is shown when `allow_free_text !== false`
- ✅ Submit button disabled until all questions have answers
- ✅ Submit calls `onSubmit` with `ClarificationAnswer[]` (values joined with `|`, labels joined with `、`)
- ✅ `disabled()` prop disables the submit button
- ✅ `role="form"` with `aria-label="补充信息表单"` is present
- ✅ `grep -r "@tauri-apps" packages/ui-core/src/components/ClarificationCard.tsx` returns zero results
- ✅ `ClarificationCard` and `ClarificationCardProps` exported from `index.ts`
- ✅ `npx vitest run tests/clarification-card.test.tsx` exits 0 (9 tests pass)

### Task 92-02-02 — DraftingProgressSteps
- ✅ `DraftingProgressSteps.tsx` exists with `DraftingProgressSteps`, `DraftingProgressStepsProps`, `DRAFTING_STEPS`
- ✅ `DraftingProgressSteps.css` exists and uses `var(--*)` tokens
- ✅ `phaseToActiveIndex()` maps: research→0, intake→1, retrieval→2, draft→3, review→4, null→-1
- ✅ `DRAFTING_STEPS` has 5 steps with correct Chinese labels
- ✅ `stepState()` returns "done"/"run"/"wait" based on index vs active
- ✅ Default title "草拟 · 法律文书起草" is rendered, overridable via `skillTitle` prop
- ✅ `role="status"` is present
- ✅ `grep -r "@tauri-apps" packages/ui-core/src/components/DraftingProgressSteps.tsx` returns zero results
- ✅ `DraftingProgressSteps`, `DraftingProgressStepsProps`, `DRAFTING_STEPS` exported from `index.ts`
- ✅ `npx vitest run tests/drafting-progress.test.tsx` exits 0 (16 tests pass)

### Task 92-02-03 — MessageFeedback
- ✅ `MessageFeedback.tsx` exists with `MessageFeedback`, `MessageFeedbackProps`
- ✅ `MessageFeedback.css` exists
- ✅ Thumbs up/down buttons rendered with titles "有帮助" / "需改进"
- ✅ Comment textarea with placeholder "可选：一句话说明哪里好/哪里需改"
- ✅ Dimension chips: 案由, 法条, 结构, 检索, 其他
- ✅ Submit calls `props.onSubmit(messageId, rating, comment, dimensions)` — no `invoke()` call
- ✅ `submitting` state disables submit buttons
- ✅ `initialRating` / `initialComment` populate form for existing feedback
- ✅ `grep -r "@tauri-apps" packages/ui-core/src/components/MessageFeedback.tsx` returns zero results
- ✅ `grep -r "invoke(" packages/ui-core/src/components/MessageFeedback.tsx` returns zero results
- ✅ `MessageFeedback` and `MessageFeedbackProps` exported from `index.ts`
- ✅ `npx vitest run tests/message-feedback.test.tsx` exits 0 (8 tests pass)

### Task 92-02-04 — DocDraftingLoader
- ✅ `DocDraftingLoader.tsx` exists (pure presentational)
- ✅ `DocDraftingLoader.css` exists with `sk` shimmer animation (in molv-base.css)
- ✅ 8 `.sk-line` elements with widths `["92%", "78%", "85%", "64%", "88%", "72%", "80%", "55%"]`
- ✅ `grep -r "@tauri-apps" packages/ui-core/src/components/DocDraftingLoader.tsx` returns zero results
- ✅ `DocDraftingLoader` exported from `index.ts`

### Task 92-02-05 — WorkflowProgressSteps
- ✅ `WorkflowProgressSteps.tsx` exists with `WorkflowProgressSteps`, `WorkflowProgressStepsProps`
- ✅ `WorkflowProgressSteps.css` exists and uses `var(--*)` tokens
- ✅ `WorkflowNotice` renders status dot, title, summary, toggle button
- ✅ `WorkflowNotice` collapsed by default when status is "complete" or "error"
- ✅ `ClarificationCard` is imported and rendered when `workflow.clarification` is non-null
- ✅ `ModeSwitchCard` renders 3 options with descriptions
- ✅ `WorkflowSuggestions` renders clickable suggestion chips
- ✅ ChatPanel uses the full `WorkflowProgressSteps` (not the simplified tracer version)
- ✅ `grep -r "@tauri-apps" packages/ui-core/src/components/WorkflowProgressSteps.tsx` returns zero results
- ✅ `WorkflowProgressSteps` and `WorkflowProgressStepsProps` exported from `index.ts`
- ✅ `npx vitest run` in `packages/ui-core/` exits 0 (all 68 tests pass)
- ✅ `python scripts/run_v2_gates.py` exits 0 (all 32 gates green)

## Deviations

1. **Minimal Icons component created** — The plan did not mention creating an Icons component, but DraftingProgressSteps and WorkflowProgressSteps both use `Icon name="check"` and `Icon name="sparkle"`. Created a minimal `Icons.tsx` with only these two icons. The full 30+ icon set (315 lines) is planned for a later plan when all components are integrated.

2. **WorkflowState type extended** — The `WorkflowState` interface from Plan 92-01 did not include `mode`, `mode_label`, `suggestions`, or `message_id` fields needed by the full `WorkflowProgressSteps` component. Added these as optional fields to maintain backward compatibility.

3. **ClarificationCard interface simplified** — The plan specified `request: ClarificationRequest` as the prop (not `workflow: () => WorkflowState` as in lawyer-desktop). This is a cleaner design that makes the component more testable and decoupled from workflow state. The `WorkflowProgressSteps` wrapper passes `workflow.clarification` to the standalone `ClarificationCard`.

4. **MessageFeedback interface simplified** — The plan specified `messageId`, `onSubmit`, `initialRating`, `initialComment` as props (not `message: Message` as in lawyer-desktop). This removes the dependency on the lawyer-desktop `Message` type and `useConversation` store.

5. **CSS split** — In lawyer-desktop, `WorkflowProgressSteps.tsx` imports `DraftingProgressSteps.css` which contains all styles. In ui-core, the CSS was split into three files: `ClarificationCard.css` (`.clarify-*` rules), `DraftingProgressSteps.css` (`.draft-step` rules), and `WorkflowProgressSteps.css` (`.workflow-notice` + `.workflow-suggestions` rules). This improves modularity.

## Self-Check: PASSED

- ✅ All 5 tasks executed and committed
- ✅ All acceptance criteria PASS
- ✅ ClarificationCard ported (single/multi/free-text)
- ✅ DraftingProgressSteps ported (five-phase with FivePhase mapping)
- ✅ MessageFeedback ported (thumbs up/down + comment + dimensions)
- ✅ DocDraftingLoader ported (skeleton animation)
- ✅ WorkflowProgressSteps ported (full component with all 4 sub-components)
- ✅ Fixture-driven tests pass for each component (33 new tests)
- ✅ 32 gates green
- ✅ Zero @tauri-apps dependencies in all new files
- ✅ Zero invoke() calls in all new files
- ✅ ChatPanel upgraded to use full WorkflowProgressSteps
- ✅ SUMMARY.md with Self-Check: PASSED
