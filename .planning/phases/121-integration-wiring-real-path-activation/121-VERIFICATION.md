# Phase 121 Verification

## Verification Summary

Phase 121 integration wiring is verified through:
1. Static analysis (dart analyze) — 0 issues.
2. Flutter test suite — 626 tests pass, 1 skipped (docx-golden).
3. V4 gate runner — all gates pass.
4. Engine boot verification — archive extracts and boots cleanly.
5. Manual code path inspection — all integration points traced.

## INT-01: GuardrailIntegrator → ChatController

### Verification evidence:
- `dart analyze`: 0 issues on `chat_controller.dart`.
- `chat_controller_guardrail_test.dart`: 6/6 tests pass.
  - "guardrail results are empty before any assistant message" — PASS
  - "clean assistant message passes all guardrails" — PASS
  - "assistant message without polish marker triggers GRD-04 warning" — PASS
  - "assistant message with unverified citations triggers GRD-02" — PASS
  - "guardrail block adds a system error message to the message list" — PASS
  - "guardrail results are accessible after sendPrompt" — PASS
- Code path: `ChatController.sendPrompt()` calls `GuardrailIntegrator.runAllChecks()` after constructing `AssistantMessage`, before marking status as completed.

### Human gate preservation:
- HG-4 (修订稿质量): `Hg4Tracker.markPending()` is the only automated call. `confirm()` and `reject()` are documented as human-action-only and are never called automatically.

## INT-02: AppStartup → FirstRunWizard → engine init

### Verification evidence:
- `dart analyze`: 0 issues on `main.dart`.
- `startup_integration_test.dart`: 10/10 tests pass.
  - "shouldShowWizard returns true on first run" — PASS
  - "shouldShowWizard returns false after wizard completion" — PASS
  - "isReady returns false before wizard completion" — PASS
  - "isReady returns true after wizard completion" — PASS
  - "loadEngineConfig returns null before wizard completion" — PASS
  - "loadEngineConfig returns config after wizard completion" — PASS
  - "buildEngineEnv returns null without API key" — PASS
  - "buildEngineEnv returns env map after wizard completion" — PASS
  - "EngineStartupConfig.validatePaths returns false for non-existent paths" — PASS
  - "wizard settings persist across AppStartup instances" — PASS
- `widget_test.dart`: 2/2 tests pass (loading indicator + MaterialApp title).

### Code path traced:
1. `main()` → `runApp(InkStatuteApp())` → `StartupGate`
2. `StartupGate._initStartup()` → `AppStartup(appDataDir)` → `shouldShowWizard()`
3. If wizard needed → `FirstRunWizard` → `completeWizard()`
4. If wizard not needed → `HomeScreen(startup)` → `_startEngine()`

## INT-03: DshProcessManager.spawn() + healthProbe()

### Verification evidence:
- `dart analyze`: 0 issues.
- Existing `dsh_process_test.dart` and `engine_health_probe_test.dart` continue to pass.
- Code path: `HomeScreen._startEngine()` calls:
  1. `startup.loadEngineConfig()`
  2. `DshConfig.forEngine(engineDir)`
  3. `processManager.spawn(dshConfig, apiKey)`
  4. `processManager.healthProbe()` — aborts on `Unhealthy`
  5. `client.initialize()` + `client.newSession(cwd)`
  6. `client.setPermissionPolicy(...)` with `ApprovalPolicy` bridge

### Engine boot verification (separate):
- Archive: `engines/releases/engine-0.1.0-47f943859b.zip`
- Extracted to: `/tmp/engine-boot-test`
- Broken symlinks: 0
- ACP `initialize` request: `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1}}`
- Response: valid result with `protocolVersion: 1`, agent name `deepseek-harness-acp`

## INT-04: ExportDialog reachable from ChatView

### Verification evidence:
- `dart analyze`: 0 issues.
- Code path: `HomeScreen` app bar has an export button (`Icons.file_download`) that calls `_showExportDialog()`.
- `_showExportDialog()` scans `controller.messages` for the latest `AssistantMessage` that parses as a `ChangeList`.
- If found, shows `ExportDialog` with real `DocxExporter` (portable Python paths from `EngineStartupConfig`) and `Hg4Tracker`.
- If not found, shows a snackbar with "无可导出的变更清单".
- Existing `export_dialog_test.dart` and `hg4_status_test.dart` continue to pass.

### HG-4 preservation:
- `ExportDialog` calls `hg4Tracker.markPending()` on success — never `confirm()`.
- The dialog displays "HG-4 待确认：修订稿须经律师确认可用于对外谈判" in orange.
- `Hg4Tracker.confirm()` and `Hg4Tracker.reject()` are never called automatically.

## INT-05: Portable Python download automated

### Verification evidence:
- `bash -n scripts/build_windows_installer.sh`: syntax OK.
- `bash -n scripts/test_portable_python_download.sh`: syntax OK.
- `grep -n 'NOTE: Portable Python must be downloaded' scripts/build_windows_installer.sh`: 0 matches (manual note removed).
- The download section:
  - Downloads Python 3.12.7 embeddable zip from `https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip`
  - Extracts via unzip or 7z
  - Installs pip via get-pip.py
  - Installs `python-docx` and `lxml`
  - Verifies imports work
  - Supports `SKIP_PYTHON` and `PYTHON_ZIP_CACHE` env vars

## V4 Gate Results

```
Gate                 Status   Message
----------------------------------------------------------------------
dart-analyze         PASS     No issues found
flutter-test         PASS     All tests passed
engine-manifest      PASS     Pin + cordis + manifest valid
mock-e2e             PASS     All mock E2E tests passed
meta-test            PASS     All lib/ directories have test coverage
docx-golden          SKIP     SKIP: docx golden not active until Phase 118
----------------------------------------------------------------------
All V4 gates passed.
```

## Human Gates Status

律师人工闸门延后至产品打磨成熟、交付律师时再做（当前团队仅开发人员）：

| Gate | Status | Note |
|------|--------|------|
| HG-1 法律质量 | DEFERRED | 延后至交付律师时 |
| HG-3 律师试运行 | DEFERRED | 延后至交付律师时 |
| HG-4 修订稿质量 | DEFERRED | 延后至交付律师时 |

自动化永远不会代为声称通过。当前阶段不列入阻塞项。
