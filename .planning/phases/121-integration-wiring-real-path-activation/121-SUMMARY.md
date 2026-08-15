# Phase 121 Summary: Integration Wiring & Real-Path Activation

## Overview

Phase 121 closed the integration gaps identified in the Phase 120 audit. All five integration items (INT-01 through INT-05) were resolved, connecting the previously disconnected components into a real, end-to-end functional path from app startup through engine spawn, chat, guardrails, and Word export.

## Integration Items Closed

### INT-01: GuardrailIntegrator wired into ChatController

**Files changed:**
- `apps/flutter_app/lib/chat/chat_controller.dart`

**What was done:**
- Imported `GuardrailIntegrator` and `GuardrailModels` into `ChatController`.
- Added `lastGuardrailResults`, `lastMessageBlocked`, `guardrailWarnings`, and `guardrailBlocks` getters.
- After each assistant message is finalized in `sendPrompt()`, `GuardrailIntegrator.runAllChecks()` is called.
- If `shouldBlock()` returns true, a `SystemErrorMessage` with the block reasons is appended to the message list. The assistant text remains visible for transparency, but the block is enforced.

**Guardrails checked at this stage:** GRD-01 (research-gate), GRD-02 (citation audit), GRD-04 (de-AI polish), GRD-05 (human review). GRD-03 (ask-user) and GRD-06 (confidentiality) remain stateful and checked at the prompt-sending stage.

### INT-02: AppStartup replaces the old startup path

**Files changed:**
- `apps/flutter_app/lib/main.dart` (rewritten)

**What was done:**
- Replaced the old `HomeScreen` with local state with a `StartupGate` widget that:
  1. Instantiates `AppStartup` with a platform-appropriate app data directory.
  2. Calls `shouldShowWizard()` to determine if the first-run wizard is needed.
  3. Shows `FirstRunWizard` if needed, calling `completeWizard()` on completion.
  4. Shows `HomeScreen` with the startup coordinator on subsequent runs.
- Error and loading states are handled with retry buttons.

### INT-03: DshProcessManager.spawn() and healthProbe() wired

**Files changed:**
- `apps/flutter_app/lib/main.dart`

**What was done:**
- `HomeScreen._startEngine()` now:
  1. Loads engine config via `AppStartup.loadEngineConfig()`.
  2. Initializes the session database and repository.
  3. Creates a `DshConfig.forEngine()` and calls `DshProcessManager.spawn()`.
  4. Runs `healthProbe()` and aborts if the engine is unhealthy.
  5. Calls `client.initialize()` and `client.newSession()`.
  6. Wires the `ApprovalPolicy` through `client.setPermissionPolicy()` with a bridge function that uses `ApprovalPolicy.evaluate()` and `ApprovalPolicy.decisionToOutcome()`.
  7. Creates a `ChatController` with the real ACP client, repository, session ID, and practice area.
- Engine restart is supported via a retry button on failure.

### INT-04: ExportDialog reachable from ChatView

**Files changed:**
- `apps/flutter_app/lib/main.dart`

**What was done:**
- Added an export button (file_download icon) to the app bar in `HomeScreen`.
- `_showExportDialog()` scans the controller's messages for the latest `AssistantMessage` that parses as a `ChangeList`.
- If found, shows `ExportDialog` with the real `DocxExporter` (configured with portable Python paths from `EngineStartupConfig`) and `Hg4Tracker`.
- If no change list is found, shows a snackbar.

### INT-05: Portable Python download automated in installer

**Files changed:**
- `scripts/build_windows_installer.sh`
- `scripts/test_portable_python_download.sh` (new)

**What was done:**
- Replaced the manual `echo "NOTE: Portable Python must be downloaded..."` with an automated download section.
- Downloads Python 3.12.7 embeddable zip from python.org via curl/wget.
- Extracts to `staging/python/` via unzip/7z.
- Installs pip via get-pip.py, then installs `python-docx` and `lxml`.
- Verifies the portable Python can import `docx` and `lxml`.
- Supports `SKIP_PYTHON` and `PYTHON_ZIP_CACHE` environment variables for CI and offline builds.
- Created a standalone test script `test_portable_python_download.sh` for CI verification.

## Engine Packaging (Wave 1)

**Files changed:**
- `scripts/build_dsh_release.sh`

**What was done:**
- Rewrote the engine assembly strategy to produce a bootable, extractable engine ZIP.
- Uses `pnpm deploy --legacy` for the base dependency tree.
- Copies missing workspace packages from `packages/*/*`, `vendor/*`, and `native/landlock-run/packages/*`.
- Hoists external npm dependencies into the deploy tree's root `node_modules` with recursive pnpm store entry copying.
- Fixes broken pnpm store symlinks by scanning for dangling references and copying missing store entries.
- Fixes workspace-relative symlinks pointing to `/dsh/` paths.
- Produces a 172 MB archive that boots from a clean extraction directory.

**Engine verification:**
- Archive: `engines/releases/engine-0.1.0-47f943859b.zip` (172 MB)
- SHA-256: `b7ebfdb97cad911ae74025ed7dff5fcc39a7df90fb5a88d66deba23e30338219`
- Broken symlinks: 0 after extraction
- ACP `initialize` handshake: successful (returns `agentInfo` and `agentCapabilities`)
- DSH commit: `47f943859b`
- Node version: `v24.16.0`

## Tests Added

### New test files:
- `apps/flutter_app/test/chat/chat_controller_guardrail_test.dart` — 6 tests verifying guardrail integration in ChatController.
- `apps/flutter_app/test/app/startup_integration_test.dart` — 10 tests verifying AppStartup flow (wizard detection, config loading, persistence).

### Updated test files:
- `apps/flutter_app/test/widget_test.dart` — Updated to match the new StartupGate loading state.

## V4 Gate Results

All V4 gates pass:
- dart-analyze: PASS (0 issues)
- flutter-test: PASS (626 tests, 1 skipped)
- engine-manifest: PASS (pin + cordis + manifest valid)
- mock-e2e: PASS
- meta-test: PASS (all lib/ directories have test coverage)
- docx-golden: SKIP (not active until Phase 118)

## Human Gates

律师人工闸门延后至产品打磨成熟、交付律师时再做（当前团队仅开发人员）：
- HG-1 (法律质量): DEFERRED — 延后至交付律师时
- HG-3 (律师试运行): DEFERRED — 延后至交付律师时
- HG-4 (修订稿质量): DEFERRED — 延后至交付律师时

自动化永远不会代为声称通过。`Hg4Tracker` 只记录 pending 状态；`confirm()` 和 `reject()` 需律师本人操作。

## Files Changed

- `apps/flutter_app/lib/main.dart` — Rewritten with StartupGate + HomeScreen integration wiring.
- `apps/flutter_app/lib/chat/chat_controller.dart` — GuardrailIntegrator wired into sendPrompt.
- `scripts/build_dsh_release.sh` — Engine assembly strategy rewritten for bootable archive.
- `scripts/build_windows_installer.sh` — Automated portable Python download.
- `scripts/test_portable_python_download.sh` — New standalone test script.
- `apps/flutter_app/test/chat/chat_controller_guardrail_test.dart` — New guardrail integration tests.
- `apps/flutter_app/test/app/startup_integration_test.dart` — New startup integration tests.
- `apps/flutter_app/test/widget_test.dart` — Updated for new startup flow.
- `engines/engine-manifest.json` — Copied from releases for gate validation.
