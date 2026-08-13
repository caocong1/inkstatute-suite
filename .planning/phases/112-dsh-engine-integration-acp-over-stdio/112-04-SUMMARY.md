---
phase: 112-dsh-engine-integration-acp-over-stdio
plan: 04
subsystem: engine (DSH subprocess manager)
tags: [dsh, subprocess, spawn, health-probe, shutdown, zero-orphan, lifecycle]
requires:
  - "112-01: Flutter skeleton + Dart ACP client tracer (NDJSON transport, initialize handshake)"
  - "112-02: Full ACP v1 client method coverage (session/new, prompt, cancel, update, permission hook)"
provides:
  - "DshPaths class with static methods: resolveDshHome (platform-aware), resolveEngineDir, engineBinPath, engineConfigPath"
  - "DshConfig class: forEngine factory (node + bin.js + --config), test factory (custom executable), buildEnvironment (DSH_HOME + DEEPSEEK_API_KEY + DSH_PERMISSION_MODE + inherited env)"
  - "EngineHealthProbe class: sends initialize via AcpClient, asserts protocolVersion 1, returns HealthResult.healthy or HealthResult.unhealthy"
  - "HealthResult sealed class: Healthy and Unhealthy(reason)"
  - "DshProcessManager class: spawn (Process.start + AcpClient wrap + stderr collection), healthProbe, shutdown (stdin close → 10s timeout → SIGTERM → SIGKILL), assertNoOrphans (ps/tasklist PID check), dispose"
  - "ShutdownResult sealed class: CleanExit(exitCode) and ForceKilled(pid)"
  - "MockEngineProcess: standalone Dart script with --hang and --stderr modes for testing"
  - "16 config tests + 12 process manager tests (27 total, 1 skipped), flutter analyze clean"
affects:
  - "Phase 116 (chat UI): DshProcessManager will be the lifecycle owner of the engine process"
  - "Phase 118 (真机回归): real DSH engine spawn tested with the same DshProcessManager"
  - "Wave 3+ plans: chat UI and session management build on this subprocess manager"
tech-stack:
  added: []
  patterns:
    - "Sealed class for HealthResult and ShutdownResult — exhaustiveness checking ensures all cases handled"
    - "DshConfig.test factory — allows tests to spawn mock engine process instead of real DSH (no @visibleForTesting annotation needed, factory name is self-documenting)"
    - "Completer<int> for exit tracking — isAlive checks _exitCompleter.isCompleted synchronously"
    - "Stderr collected as List<String> — reference-first diagnostics, not echoed to UI"
    - "Graceful shutdown sequence: stdin.close() → exitCode.timeout(10s) → kill(sigterm) → exitCode.timeout(5s) → kill(sigkill)"
    - "assertNoOrphans uses ps -p (Linux) / tasklist /FI (Windows) — platform-branched PID verification"
    - "MockEngineProcess --hang mode: awaits Completer<void>().future (never completes) to simulate hung engine"
key-files:
  created:
    - apps/flutter_app/lib/engine/dsh_config.dart
    - apps/flutter_app/lib/engine/dsh_process.dart
    - apps/flutter_app/lib/engine/engine_health.dart
    - apps/flutter_app/test/engine/dsh_config_test.dart
    - apps/flutter_app/test/engine/dsh_process_test.dart
    - apps/flutter_app/test/engine/mock_engine_process.dart
  modified: []
decisions:
  - "DshConfig uses a private constructor with factory methods (forEngine, test) — production config spawns node + bin.js + --config; test config spawns custom executable (dart run mock_engine_process.dart)"
  - "DshPaths.resolveDshHome uses Platform.isWindows to branch: LOCALAPPDATA on Windows, HOME/.local/share on Linux/WSL — with USERPROFILE fallback if LOCALAPPDATA is unset"
  - "buildEnvironment is a pure function: reads Platform.environment, returns a new Map, no side effects — API key exists only in the returned Map for Process.start"
  - "EngineHealthProbe has a configurable timeout (default 30s) — returns Unhealthy on TimeoutException, AcpRpcException, or any other error"
  - "DshProcessManager.shutdown closes stdin first (not AcpClient.close) — direct stdin.close() signals EOF to DSH quiesce without canceling the AcpClient subscription prematurely"
  - "Force kill escalation: SIGTERM first (10s timeout), then SIGKILL (5s timeout) — gives the process two chances to exit cleanly"
  - "assertNoOrphans uses ps -p (Linux) / tasklist /FI (Windows) — returns true if the PID is not found in the process table"
  - "MockEngineProcess --hang mode uses await Completer<void>().future to hang forever — the process is killed externally by DshProcessManager.shutdown"
  - "stderr lines are collected in a List<String> — in production these would go to a logger; the key invariant is they are never echoed to the UI (reference-first)"
metrics:
  duration: "~9 minutes"
  completed: "2026-08-13T16:44:00Z"
  tasks: 2
  files_created: 6
  files_modified: 0
  tests_passing: 27
  tests_skipped: 1
  flutter_analyze_issues: 0
---

# Phase 112 Plan 04: DSH Subprocess Manager Summary

Implemented and tested the DSH subprocess manager (DSH-02) that spawns, monitors, and cleanly shuts down the DSH ACP engine process. The manager guarantees no orphan processes remain after app exit — a critical reliability requirement for a desktop app.

## What Was Built

### Task 1: DshConfig + DshProcessManager (spawn + health probe) + EngineHealthProbe + tests (commit ac18233)

**Library code (3 files created):**

- `dsh_config.dart` — DSH configuration:
  - `DshPaths` class with static methods:
    - `resolveDshHome()` — Windows: `%LOCALAPPDATA%\InkStatute\runtime\.dsh`; Linux/WSL: `~/.local/share/InkStatute/runtime/.dsh`
    - `resolveEngineDir(String engineVersion)` — `<appDir>/engine/<version>`
    - `engineBinPath(String engineDir)` — `[engineDir]/lib/bin.js`
    - `engineConfigPath(String engineDir)` — `[engineDir]/acp.cordis.yml`
  - `DshConfig` class:
    - `forEngine(String engineDir)` factory — production: `node [engineDir]/lib/bin.js --config [engineDir]/acp.cordis.yml`
    - `test(...)` factory — testing: custom executable + args (e.g. `dart run mock_engine_process.dart`)
    - `buildEnvironment(String apiKey, {String? dshHome, String permissionMode})` — returns Map with DSH_HOME, DEEPSEEK_API_KEY, DSH_PERMISSION_MODE + all inherited env vars. Pure function — no side effects, no file writes, no logging.

- `engine_health.dart` — Health probe:
  - `HealthResult` sealed class: `Healthy` and `Unhealthy(reason)`
  - `EngineHealthProbe` class: `check(AcpClient client)` — sends `initialize`, asserts `protocolVersion == 1`, asserts `agentInfo.name` non-empty. Returns `Healthy` or `Unhealthy(reason)`. Configurable timeout (default 30s).

- `dsh_process.dart` — Subprocess manager:
  - `ShutdownResult` sealed class: `CleanExit(exitCode)` and `ForceKilled(pid)`
  - `DshProcessManager` class:
    - `spawn(DshConfig config, String apiKey)` — `Process.start` with correct executable/args/workingDirectory/environment. Wraps stdin/stdout in `AcpTransport` + `AcpClient`. Collects stderr line-by-line.
    - `healthProbe()` — delegates to `EngineHealthProbe.check(acpClient)`
    - `pid` getter, `isAlive` getter (via Completer pattern), `acpClient` getter, `stderrLines` getter
    - `shutdown({timeout, killTimeout})` — stdin close → 10s timeout → SIGTERM → 5s timeout → SIGKILL
    - `assertNoOrphans()` — `ps -p` (Linux) / `tasklist /FI` (Windows) PID verification
    - `dispose()` — shutdown + assertNoOrphans

**Mock engine process (1 file created):**
- `mock_engine_process.dart` — Standalone Dart script simulating DSH ACP server:
  - Responds to `initialize` with protocolVersion 1, agentInfo, agentCapabilities, authMethods
  - Responds to `session/new`, `authenticate`
  - `--hang` mode: ignores stdin close, keeps running until killed (for timeout/kill tests)
  - `--stderr` mode: writes diagnostic line to stderr on startup (for stderr handling tests)
  - Normal mode: exits with code 0 on stdin close

**Test files (2 files created, 27 tests, 1 skipped):**
- `dsh_config_test.dart` (16 tests):
  - DshPaths.resolveDshHome returns platform-appropriate path
  - DshPaths.resolveEngineDir returns correct path
  - DshPaths.engineBinPath returns [engineDir]/lib/bin.js
  - DshPaths.engineConfigPath returns [engineDir]/acp.cordis.yml
  - DshConfig.forEngine sets node executable and correct arguments
  - DshConfig.forEngine computes engineBinPath from engineDir
  - DshConfig.forEngine computes engineConfigPath from engineDir
  - buildEnvironment contains DSH_HOME
  - buildEnvironment contains DEEPSEEK_API_KEY
  - buildEnvironment contains DSH_PERMISSION_MODE
  - buildEnvironment accepts custom permissionMode
  - buildEnvironment accepts custom dshHome override
  - buildEnvironment preserves inherited PATH
  - buildEnvironment preserves inherited HOME on Linux
  - buildEnvironment does NOT persist API key to any file
  - test factory creates config with custom executable

- `dsh_process_test.dart` (11 tests + 1 skipped):
  - spawn starts the process and PID is non-zero
  - spawn creates an AcpClient for protocol communication
  - health probe returns Healthy when initialize succeeds
  - health probe returns Unhealthy when process not spawned
  - stderr lines are collected as reference-first diagnostics
  - stderr collection does not crash on empty stderr
  - clean shutdown: stdin close → exit code 0 → no orphans
  - timeout shutdown: hanging mock → force-killed → no orphans
  - dispose combines shutdown + orphan assertion
  - PID tracking: non-zero after spawn, dead after shutdown
  - EngineHealthProbe check returns Healthy for valid initialize response
  - (skipped) check with short timeout returns Unhealthy on no response — mock always responds

### Task 2: Graceful shutdown + zero-orphan PID assertion (commit ac18233)

**Shutdown sequence (in dsh_process.dart):**
1. Close `process.stdin` (signals EOF → DSH quiesce)
2. Await `process.exitCode` with 10s timeout
3. On timeout: `process.kill(ProcessSignal.sigterm)` + log warning
4. After SIGTERM: await `process.exitCode` with 5s timeout
5. On second timeout: `process.kill(ProcessSignal.sigkill)` (last resort)
6. Return `CleanExit(exitCode)` or `ForceKilled(pid)`

**Zero-orphan assertion:**
- `assertNoOrphans()` — after shutdown, verifies PID is no longer alive
- Linux/WSL: `Process.run('ps', ['-p', pid])` — exit code != 0 means process is gone
- Windows: `Process.run('tasklist', ['/FI', 'PID eq $pid'])` — PID not in output means gone
- Returns `true` if no orphans found

**Mock engine --hang mode:**
- `MockEngineProcess` with `--hang` flag: after stdin closes, awaits `Completer<void>().future` (never completes)
- Simulates a hung engine that ignores EOF — only exits when killed
- Used by the timeout/kill test to verify the force-kill path

## Verification Results

| Check | Result |
|-------|--------|
| `flutter test test/engine/dsh_config_test.dart test/engine/dsh_process_test.dart` | exit 0 — 27/27 tests passed (1 skipped) |
| `flutter test` (full app suite) | exit 0 — 28/28 tests passed (1 skipped) |
| `flutter analyze` (apps/flutter_app) | exit 0 — No issues found |
| `grep -r "DEEPSEEK_API_KEY\|apiKey\|api_key" lib/engine/ \| grep -i "log\|print\|write\|file"` | 0 matches (no API key in logs/files) |
| `grep -n "Process.kill\|\.kill(" dsh_process.dart` | kill only used after timeout (lines 190, 199 — inside timeout catch blocks) |
| Frozen directories modified | None |
| Real model calls | None — all tests use mock engine process |

## Test Inventory

| File | Tests | Coverage |
|------|-------|----------|
| dsh_config_test.dart | 16 | DshPaths (4), DshConfig.forEngine (3), buildEnvironment (8), test factory (1) |
| dsh_process_test.dart | 11+1 skipped | spawn (2), healthProbe (2), stderr (2), shutdown (4), EngineHealthProbe (1+1 skipped) |
| **Total** | **27+1 skipped** | |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Analyzer: depend_on_referenced_packages for package:meta**
- **Found during:** Task 1 (flutter analyze)
- **Issue:** Importing `package:meta/meta.dart` for `@visibleForTesting` triggered `depend_on_referenced_packages` info because `meta` is not an explicit dependency in pubspec.yaml.
- **Fix:** Removed the `@visibleForTesting` annotation and the `package:meta` import. The `DshConfig.test` factory name is self-documenting — the annotation is not needed.
- **Files modified:** `dsh_config.dart`
- **Commit:** ac18233

**2. [Rule 1 - Bug] Analyzer: unintended_html_in_doc_comment**
- **Found during:** Task 1 (flutter analyze)
- **Issue:** Doc comments containing `<engineDir>` and `<appDir>` with angle brackets were flagged as potential HTML.
- **Fix:** Replaced angle brackets with square brackets (`[engineDir]`, `[appDir]`) in doc comments.
- **Files modified:** `dsh_config.dart`
- **Commit:** ac18233

**3. [Rule 1 - Bug] Analyzer: unused_local_variable and unused_import**
- **Found during:** Task 1 (flutter analyze)
- **Issue:** Unused `env` variable in config test, unused `dart:io` import and unused `result` variable in process test.
- **Fix:** Removed unused variable assignments and imports. Cleaned up the skipped EngineHealthProbe test to remove unused variables.
- **Files modified:** `dsh_config_test.dart`, `dsh_process_test.dart`
- **Commit:** ac18233

### Implementation Notes

- Both tasks (Task 1: spawn + health probe, Task 2: shutdown + orphan assertion) were implemented in a single commit. The code is cohesive — the shutdown logic is tightly coupled with the spawn logic in `DshProcessManager`, and the mock engine process needs both normal and `--hang` modes from the start. Splitting into two commits would require an intermediate state where shutdown tests are written but the implementation is incomplete, which adds no value for this plan.

## Known Stubs

None — all code is production-quality. The `DshProcessManager` implements the complete subprocess lifecycle (spawn, health probe, stderr, shutdown, orphan assertion) with no placeholders or TODOs. The real DSH engine spawn is tested in Phase 118 (真机回归).

## Threat Flags

All four threats from the plan's threat model are mitigated:

- **T-112-11 (Information Disclosure — API key in environment):** MITIGATED — `buildEnvironment` is a pure function that returns a Map for `Process.start`. The API key exists only in the returned Map. Grep assertion confirms zero plaintext keys in logs/files. No `print`, `log`, or file-write operations touch the API key.

- **T-112-12 (Denial of Service — Orphan processes after exit):** MITIGATED — `shutdown()` closes stdin first (signals EOF → DSH quiesce), awaits exit with 10s timeout, then force-kills (SIGTERM → SIGKILL). `assertNoOrphans()` verifies the PID is no longer alive via `ps -p` / `tasklist`. Tests verify both clean exit and force-kill paths with zero orphans.

- **T-112-13 (Information Disclosure — stderr logging):** MITIGATED — stderr lines are collected in a `List<String>` as reference-first diagnostics. The lines are engine diagnostics (not customer data), but they are never echoed to the UI. The `stderrLines` getter returns an unmodifiable list for logging purposes only.

- **T-112-14 (Tampering — Engine process spawn):** MITIGATED — The engine is spawned from a fixed `DshConfig.forEngine(engineDir)` factory that constructs the path from the engine directory. No user-controlled path enters the spawn arguments. The `DshConfig.test` factory is for testing only (spawns mock engine process).

## Self-Check: PASSED

All created files exist on disk. All commit hashes verified in git log. All verification checks pass.
