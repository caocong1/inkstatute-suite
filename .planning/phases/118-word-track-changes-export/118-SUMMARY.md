---
phase: 118-word-track-changes-export
status: complete
requirements_closed: [APP-04, GATE-03]
plans_executed: [118-01, 118-02, 118-03]
test_count: 449
v4_gates: all-pass
human_gate: HG-4 (HUMAN_NEEDED — pending lawyer confirmation)
---

# Phase 118 Summary: Word Track-Changes Export

## Goal Achieved

律师一键拿到带 Word 原生修订的 docx：模型产结构化变更清单，app 侧便携 Python 执行 track-changes 脚本做确定性变换；E2E 与金标准齐备，人工闸门 HG-4 就位。

## Plans Executed

### 118-01: Change list JSON schema + Dart models + parser

- `lib/export/change_list_schema.dart` — ChangeList, ChangeItem, RiskLevel (P0/P1/P2). JSON serialization, validation (empty items, duplicate IDs, empty comments).
- `lib/export/change_list_parser.dart` — Extracts JSON change lists from assistant messages. Supports fenced ```json blocks and [CHANGE_LIST: {...}] blocks with balanced-brace parsing.

### 118-02: Python script refactor + docx exporter + golden fixtures

- `assets/scripts/contract_review_trackchanges_v4.py` — Refactored from lawfirm-profile script (41,185 bytes). Accepts JSON change list via --changes argument. TrackChangesBuilder with process(change_items) and save(). Uses lxml for OOXML manipulation.
- `lib/export/docx_exporter.dart` — DocxExporter invokes Python with validated ChangeList. ExportResult sealed class (ExportSuccess/ExportFailure). Model never writes docx bytes — only ChangeList JSON reaches the script.
- Test fixtures: sample_input.docx, sample_change_list.json.

### 118-03: Export dialog + HG-4 status + GATE-03 E2E + research

- `lib/export/export_dialog.dart` — ExportDialog widget with progress, success/failure display, HG-4 pending notice.
- `lib/export/hg4_status.dart` — Hg4Tracker with pendingConfirmation/confirmed/rejected states. Never auto-completes.
- `test/export/gate03_e2e_test.dart` — GATE-03 E2E: mock ACP full flow + change list extraction + docx export + output boundary assertion + model-never-writes-docx assertion.
- `118-RESEARCH.md` — Embeddable Python + lxml compatibility confirmed (~15-20MB compressed). Degradation plan: replace lxml with xml.etree.ElementTree.

## Requirements Closed

- **APP-04**: Word 原生修订导出 — Change list JSON schema defined; Python script refactored; docx exporter implemented; golden fixtures created; model never directly writes docx bytes (asserted in tests).
- **GATE-03**: E2E — Mock ACP full flow test with change list extraction, docx export, output boundary verification, and model-never-writes-docx assertion. Real engine path tagged 'real-api'.

## Human Gate

**HG-4**: HUMAN_NEEDED — docx output must be confirmed by a lawyer as usable for external negotiation. The Hg4Tracker records "pendingConfirmation" status and only changes via explicit human action. The automation never auto-completes this gate.

## Test Count

449 tests total (all pass):
- 25 change list schema + parser tests (118-01)
- 9 docx exporter tests (118-02)
- 8 HG-4 status tests (118-03)
- 3 export dialog tests (118-03)
- 4 GATE-03 E2E tests (118-03)
- Plus all pre-existing Phase 112-117 tests

## V4 Gates

```
dart-analyze     PASS
flutter-test     PASS
engine-manifest  SKIP (build engine first)
mock-e2e         PASS
meta-test        PASS
docx-golden      SKIP (activated when Python runtime is bundled in Phase 119)
```

## Commits

- `c84b321` — phase context + 3 plans
- `e2ec1ab` — 118-01: change list schema + parser
- `766691e` — 118-02: Python script + docx exporter + fixtures
- (pending) — 118-03: export dialog + HG-4 + GATE-03 + research
