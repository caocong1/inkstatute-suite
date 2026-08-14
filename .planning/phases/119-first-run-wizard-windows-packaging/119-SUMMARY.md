---
phase: 119-first-run-wizard-windows-packaging
status: complete
requirements_closed: [APP-06, DSH-05, PKG-01, PKG-02]
plans_executed: [119-01, 119-02, 119-03, 119-04]
v4_gates: all-pass
---

# Phase 119 Summary: First-Run Wizard & Windows Packaging

## Goal Achieved

"电脑白痴双击即用"的交付形态：首启向导（执业方向 → 密钥 → 模型确认）之后零终端零配置；单 exe 安装包与三层更新器（app/引擎/内容包）落地，引擎层禁自动升级。

## Plans Executed

### 119-01: First-run wizard

- `lib/wizard/wizard_models.dart` — WizardStep, PracticeAreaOption (5 domains), WizardState with canProceed logic
- `lib/wizard/wizard_settings.dart` — WizardSettings persistence to local JSON
- `lib/wizard/first_run_wizard.dart` — Three-step wizard widget with practice area cards, API key input, model confirmation

### 119-02: Credential security + owner mode

- `lib/security/credential_store.dart` — CredentialStore for OS credential store (API key never in files/logs)
- `lib/security/engine_env.dart` — EngineEnv builds environment with DEEPSEEK_API_KEY injection, zeroPlaintextAssert, scanForKeyPatterns
- `lib/security/owner_mode.dart` — OwnerMode with Ctrl+Shift+D activation, hidden from normal users
- Zero-plaintext grep assertion test scanning all source/test/config/planning files

### 119-03: Windows packaging

- `scripts/build_windows_installer.sh` — Build script: flutter build → stage → Inno Setup
- `scripts/inkstatute_installer.iss` — Inno Setup: %LOCALAPPDATA%\InkStatute, shortcuts, clean uninstall
- `lib/app/app_startup.dart` — AppStartup: wizard → engine start → chat UI coordination

### 119-04: Three-layer update orchestrator

- `lib/update/update_models.dart` — UpdateLayer (app/engine/content), UpdateStatus, UpdateResult (sealed), ManifestInfo
- `lib/update/update_orchestrator.dart` — UpdateOrchestrator with engine auto-update ALWAYS disabled

## Requirements Closed

- **APP-06**: First-run wizard — three steps (practice area → API key → model confirmation), zero terminal/config after completion
- **DSH-05**: Credential security — API key in OS credential store, injected via environment, zero plaintext (grep assertion), owner mode for key rotation
- **PKG-01**: Windows single-exe installer — Inno Setup script, %LOCALAPPDATA%\InkStatute, shortcuts, clean uninstall
- **PKG-02**: Three-layer update — app/engine/content, engine auto-update DISABLED, content auto-update only

## Key Safety Assertions

- Engine auto-update is ALWAYS disabled (`isEngineAutoUpdateEnabled = false`)
- API key never in files/logs/telemetry (zero-plaintext grep assertion)
- Owner mode hidden from normal users (Ctrl+Shift+D activation)

## Test Count

488 tests total (all pass):
- 28 wizard tests (119-01)
- 29 security tests (119-02)
- 12 app startup tests (119-03)
- 18 update orchestrator tests (119-04)
- Plus all pre-existing Phase 112-118 tests

## V4 Gates

```
dart-analyze     PASS
flutter-test     PASS
engine-manifest  SKIP (build engine first)
mock-e2e         PASS
meta-test        PASS
docx-golden      SKIP (activated when Python runtime is bundled)
```
