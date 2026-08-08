---
phase: 110-arena-ui-integration
plan: 03
status: complete
requirements: [UI-03, UI-04]
---

# Plan 03: ScoreCard + ReviewSummary + SynthesisViewer - Summary

## Objective

Create the three arena UI components that consume `ArenaMetaState` (populated
by `arenaMetaReducer` from Plan 01) and render arena scores, reviews, and
synthesis output. All three components are prop-driven (no data fetching) and
follow existing ui-core SolidJS patterns.

## Tasks Completed

### Task 1: ScoreCard.tsx — per-agent per-round 10-point self-score display

- **Files created:**
  - `packages/ui-core/src/components/ScoreCard.tsx` — renders a table with one
    row per agent slot, dynamic round columns (1..maxRound), and a best-score
    column. Each score cell shows a numeric value with a visual bar
    (width = score * 10%). Color-coded: green >= 8, yellow 5-7, red < 5.
  - `packages/ui-core/src/components/ScoreCard.css` — table styling, score
    bars, agent avatars with deterministic color from slot name.
  - `packages/ui-core/tests/test_score_card.tsx` — 10 tests covering all 9
    behaviors plus prop-driven rendering.
- **Verify:** `npx vitest run tests/test_score_card.tsx` → 10 passed.
- **Commit:** `feat(110-03): ScoreCard per-agent per-round 10-point self-score display`

### Task 2: ReviewSummary.tsx — findings with categorical confidence and confirmed/disproved

- **Files created:**
  - `packages/ui-core/src/components/ReviewSummary.tsx` — flattens
    `ArenaReviewEntry[]` into `ReviewFindingItem[]`, groups by
    `reviewed_slot` (header "对 {reviewed_slot} 的评审"), sorts findings by
    severity (High → Medium → Low). Confidence is categorical
    (Certain/Likely/Possible) — numeric percentages are rejected and fall
    back to "Possible", matching `ConfidenceLevel` in `arena_engine/review.py`.
  - `packages/ui-core/src/components/ReviewSummary.css` — finding list,
    colored confidence/severity badges, confirmed/disproved markers.
  - `packages/ui-core/tests/test_review_summary.tsx` — 10 tests covering all
    10 behaviors.
- **Verify:** `npx vitest run tests/test_review_summary.tsx` → 10 passed.
- **Commit:** `feat(110-03): ReviewSummary findings with categorical confidence and confirmed/disproved`

### Task 3: SynthesisViewer.tsx — final version display + Word track-changes export

- **Files created:**
  - `packages/ui-core/src/components/SynthesisViewer.tsx` — renders synthesis
    content as markdown via `SolidMarkdown` + `remarkGfm` (same as DocPreview).
    "导出 Word 修订稿" button uses `useAdapters().file.save()` for the file
    dialog, then delegates actual docx generation to the `onExport` callback
    (parent calls arena-service). "复制全文" button copies content to
    clipboard via `navigator.clipboard.writeText()`. Empty state shows
    "等待综合最终版…" with a loading spinner.
  - `packages/ui-core/src/components/SynthesisViewer.css` — header, toolbar,
    markdown content (follows DocPreview.css conventions), loading spinner.
  - `packages/ui-core/tests/test_synthesis_viewer.tsx` — 11 tests covering
    all 10 behaviors plus empty-string placeholder.
- **Verify:** `npx vitest run tests/test_synthesis_viewer.tsx` → 11 passed.
- **Commit:** `feat(110-03): SynthesisViewer final version display with Word track-changes export`

## Verification

Combined run of all three test files:

```
cd packages/ui-core && npx vitest run tests/test_score_card.tsx tests/test_review_summary.tsx tests/test_synthesis_viewer.tsx

✓ tests/test_review_summary.tsx (10 tests) 40ms
✓ tests/test_score_card.tsx (10 tests) 55ms
✓ tests/test_synthesis_viewer.tsx (11 tests) 269ms

Test Files  3 passed (3)
     Tests  31 passed (31)
```

## Key Design Decisions

1. **Prop-driven components** — all three components accept data as props
   (`scores`, `reviews`, `synthesisContent`). They do NOT fetch data or
   create stores themselves. The parent wires `ArenaMetaState` from
   `arenaMetaReducer` (Plan 01) into these components.

2. **Categorical confidence only** — `ReviewSummary` normalizes confidence
   to Certain/Likely/Possible. Numeric percentages (e.g. "67%") are rejected
   and fall back to "Possible", matching the binding research anti-pattern
   and `ConfidenceLevel` enum in `arena_engine/review.py`.

3. **Export delegation** — `SynthesisViewer` does NOT generate the docx
   itself. It uses `useAdapters().file.save()` for the file dialog (same
   pattern as `DocPreview`) and delegates actual track-changes docx
   generation to the `onExport` callback. The parent calls arena-service,
   reusing the `lawfirm-profile/scripts/contract_review_trackchanges.py`
   Word-native track-changes pattern.

4. **Single UI core** — all three components extend the existing ui-core
   package, reusing `useAdapters()`, `Icon`, `SolidMarkdown` + `remarkGfm`,
   and CSS variable conventions from `DocPreview.css`.

## Artifacts Produced

- `ui-core.src.components.ScoreCard.ScoreCard` — UI-03
- `ui-core.src.components.ReviewSummary.ReviewSummary` — UI-03
- `ui-core.src.components.SynthesisViewer.SynthesisViewer` — UI-04
- `tests/test_score_card.tsx::ScoreCardTests` — 10 tests
- `tests/test_review_summary.tsx::ReviewSummaryTests` — 10 tests
- `tests/test_synthesis_viewer.tsx::SynthesisViewerTests` — 11 tests

## Key Links

- `ScoreCard` consumes `ArenaMetaState.scores` from `arenaMetaReducer` (Plan 01)
- `ReviewSummary` consumes `ArenaMetaState.reviews` from `arenaMetaReducer` (Plan 01)
- `SynthesisViewer` consumes `ArenaMetaState.synthesisContent` from `arenaMetaReducer` (Plan 01)
- `SynthesisViewer.onExport` is wired by parent to call arena-service for track-changes docx generation
- Confidence levels match `ConfidenceLevel` enum in `arena_engine/review.py` (Certain/Likely/Possible)
- Severity levels match `SeverityLevel` enum in `arena_engine/review.py` (High/Medium/Low)
