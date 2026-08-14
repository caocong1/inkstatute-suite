---
phase: 118-word-track-changes-export
next_phase: 119-first-run-wizard-windows-packaging
carry_forward:
  - DocxExporter ready for portable Python integration (Phase 119)
  - ExportDialog ready for ChatView integration (Phase 119)
  - Hg4Tracker ready for persistence layer (Phase 119)
  - GATE-03 E2E test framework established
  - docx-golden gate ready for activation when Python runtime is bundled
---

# Phase 118 Transition: Word Export → Packaging

## What Phase 118 Delivered

- Change list JSON schema with validation (ChangeList, ChangeItem, RiskLevel)
- Change list parser extracting from assistant messages (fenced json, [CHANGE_LIST:] blocks)
- Refactored Python track-changes script accepting JSON input
- Docx exporter with model-never-writes-docx enforcement
- Export dialog with progress and HG-4 pending notice
- HG-4 status tracker (never auto-completes)
- GATE-03 E2E test (mock ACP full flow + export + boundary assertions)
- Research: embeddable Python + lxml compatibility confirmed

## What Phase 119 (Packaging) Needs

Phase 119 depends on Phase 118 (per roadmap). The packaging phase needs to:

1. **Bundle portable Python**: Include Windows embeddable Python + lxml in the installer
2. **Bundle track-changes script**: Include `contract_review_trackchanges_v4.py` in the app assets
3. **Wire DocxExporter**: Connect the exporter to the app's Python path and script path
4. **Wire ExportDialog**: Add "导出" button to ChatView when a ChangeList is available
5. **Wire Hg4Tracker**: Persist HG-4 status to the local database
6. **Activate docx-golden gate**: Enable the docx golden test in V4 gates once Python is bundled
7. **First-run wizard**: Include Python runtime setup in the first-run experience

## Carry-Forward Notes

- The export pipeline is complete: model → JSON change list → parser → validated ChangeList → Python script → docx
- The model never directly writes docx bytes — enforced by type system and tested
- HG-4 is HUMAN_NEEDED — the automation only records "pendingConfirmation"
- The GATE-03 E2E test covers the mock ACP path; the real-api path is tagged for when API keys are available
- The docx-golden V4 gate is ready to activate once Python is bundled

## Architecture Decisions for Phase 119

- Portable Python is bundled in the installer, not downloaded separately
- The track-changes script is in `assets/scripts/` and bundled with the app
- The export dialog is accessible from ChatView when a ChangeList is detected
- HG-4 status persists across sessions in the local database
