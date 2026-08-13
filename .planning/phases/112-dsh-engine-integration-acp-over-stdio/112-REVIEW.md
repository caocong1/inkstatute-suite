---
phase: 112-dsh-engine-integration-acp-over-stdio
reviewed: 2026-08-13T17:08:09Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - apps/flutter_app/packages/acp_client/lib/acp_client.dart
  - apps/flutter_app/packages/acp_client/lib/acp_transport.dart
  - apps/flutter_app/packages/acp_client/lib/acp_protocol.dart
  - apps/flutter_app/packages/acp_client/lib/acp_types.dart
  - apps/flutter_app/packages/acp_client/lib/approval_policy.dart
  - apps/flutter_app/lib/engine/dsh_config.dart
  - apps/flutter_app/lib/engine/dsh_process.dart
  - apps/flutter_app/lib/engine/engine_health.dart
  - apps/flutter_app/lib/main.dart
  - apps/flutter_app/packages/acp_client/test/acp_client_test.dart
  - apps/flutter_app/packages/acp_client/test/acp_transport_test.dart
  - apps/flutter_app/packages/acp_client/test/approval_policy_test.dart
  - apps/flutter_app/packages/acp_client/test/session_cancel_test.dart
  - apps/flutter_app/packages/acp_client/test/session_new_test.dart
  - apps/flutter_app/packages/acp_client/test/session_prompt_test.dart
  - apps/flutter_app/packages/acp_client/test/session_update_test.dart
  - apps/flutter_app/packages/acp_client/test/fixtures/mock_acp_server.dart
  - apps/flutter_app/test/engine/dsh_config_test.dart
  - apps/flutter_app/test/engine/dsh_process_test.dart
  - apps/flutter_app/test/engine/mock_engine_process.dart
  - apps/flutter_app/test/widget_test.dart
  - scripts/build_dsh_release.sh
  - scripts/test_build_dsh_release.sh
  - scripts/run_v4_gates.py
  - scripts/test_run_v4_gates.py
  - engines/dsh-pin.txt
  - engines/acp.cordis.yml
  - .github/workflows/v4-gates.yml
findings:
  critical: 2
  warning: 6
  info: 4
  total: 12
status: findings_found
---

# Phase 112: Code Review Report

**Reviewed:** 2026-08-13T17:08:09Z
**Depth:** standard
**Files Reviewed:** 21 production source files + 8 test/fixture files + 5 scripts/config files
**Status:** findings_found

## Summary

Phase 112 implements the DSH engine integration layer: a Dart ACP v1 client (`packages/acp_client`), a DSH subprocess manager (`lib/engine/`), an engine release pipeline (`scripts/build_dsh_release.sh`), and a V4 gates runner (`scripts/run_v4_gates.py`).

**Security posture is strong.** The approval security boundary (`approval_policy.dart`) is correctly implemented: unknown kinds are always denied, terminal/execute_code render user cards (never auto-approved), no batch/durable/remember path exists (verified by negative grep + test). The API key is injected via environment only — never logged, never persisted to disk. No secrets found in any production code, config, or test fixture. Frozen directories (LEG-01) were not modified. Every `lib/` directory has corresponding `test/` coverage (meta-test gate passes).

**Two Critical findings** relate to unhandled async errors in the ACP client's server-request handler: if the permission policy callback throws or the server sends malformed permission params, the error becomes an unhandled async error (not caught by the stream's `onError` handler) and the pending prompt hangs indefinitely. Both should default to `reject-once` (safe default) on any error.

**Six Warnings** cover wire-boundary type safety (`id` cast without validation), Windows orphan-detection substring matching, and several robustness gaps in error paths.

## Critical Issues

### CR-01: Unhandled async error in `_handlePermissionRequest` — policy callback throw leaves prompt hanging

**File:** `apps/flutter_app/packages/acp_client/lib/acp_client.dart:316-322`
**Issue:** `_handlePermissionRequest` is `async` and called fire-and-forget from the sync `_handleMessage` stream listener (line 238: `_handleServerRequest(message)` — no `await`, return value discarded). If the `_permissionPolicy` callback throws (e.g., UI layer bug, null dereference), or if `RequestPermissionParams.fromJson(request.params!)` throws on malformed server params, the exception propagates as an **unhandled async error** — it is NOT caught by the stream subscription's `onError` handler (that only catches errors thrown synchronously in `onData`). The server never receives a permission response, so the in-flight `session/prompt` completer hangs forever. The client has no timeout on pending prompts, so the app freezes on the next prompt.

This violates the AGENTS.md safe-default rule: "未知 kind 一律拒绝" (unknown kind always denied) — a parse failure or callback throw is effectively an "unknown" condition and must default to deny, not hang.

**Fix:**
```dart
Future<void> _handlePermissionRequest(JsonRpcRequest request) async {
  PermissionOutcome outcome;
  try {
    final params = RequestPermissionParams.fromJson(request.params!);
    outcome = _permissionPolicy?.call(params) ??
        const PermissionOutcome.selected('reject-once');
  } catch (_) {
    // Parse failure or policy throw → safe default: reject-once.
    outcome = const PermissionOutcome.selected('reject-once');
  }
  await sendResponse(request.id, {'outcome': outcome.toJson()});
}
```

### CR-02: `_handleServerRequest` fire-and-forget async — unhandled errors for unknown server requests

**File:** `apps/flutter_app/packages/acp_client/lib/acp_client.dart:238, 291-311`
**Issue:** `_handleServerRequest` is `async` but called without `await` from `_handleMessage` (line 238). If `JsonRpcRequest.fromJson(message)` throws (e.g., server sends a request with a non-integer `id` — `json['id'] as int` in `acp_protocol.dart:30` throws `TypeError`), the error is an unhandled async error. The server's request goes unanswered, and depending on the server implementation, the session may deadlock. The `catch (e)` block at line 304 only wraps `sendResponse`, not the `fromJson` parse or the permission dispatch.

**Fix:** Wrap the entire `_handleServerRequest` body in try/catch, sending a JSON-RPC error response on any failure:
```dart
Future<void> _handleServerRequest(Map<String, dynamic> message) async {
  int id;
  try {
    final request = JsonRpcRequest.fromJson(message);
    id = request.id;
    if (request.method == 'session/request_permission' &&
        request.params != null) {
      await _handlePermissionRequest(request);
      return;
    }
    await sendResponse(request.id, <String, dynamic>{});
  } catch (e) {
    // Best-effort error response — id may be unknown if parse failed.
    try {
      await _transport.send({
        'jsonrpc': '2.0',
        'id': id,
        'error': {'code': -32603, 'message': e.toString()},
      });
    } catch (_) {
      // Transport closed — nothing more we can do.
    }
  }
}
```

## Warnings

### WR-01: `assertNoOrphans` Windows PID check uses substring match — false negatives possible

**File:** `apps/flutter_app/lib/engine/dsh_process.dart:234`
**Issue:** `!output.contains(pid.toString())` checks whether the PID's string representation appears anywhere in `tasklist` output. If the dead process had PID `123` and a *different* live process has PID `1234`, the string `"123"` is a substring of `"1234"`, so `contains` returns `true` and `assertNoOrphans` returns `false` (reports an orphan that doesn't exist). Conversely, if PID `1234` is being checked and PID `123` is alive, `"1234".contains("123")` is `true` → false orphan. This undermines the zero-orphan guarantee on Windows.

**Fix:** Parse the tasklist output and match the PID as a complete field, not a substring:
```dart
// tasklist /FO CSV outputs: "Image Name","PID","Session Name",...
final result = await Process.run(
  'tasklist',
  ['/FI', 'PID eq $pid', '/FO', 'CSV', '/NH'],
  stdoutEncoding: utf8,
  stderrEncoding: utf8,
);
final output = result.stdout as String;
// /NH suppresses the header. If the process is gone, output is empty
// or contains only "INFO: No tasks are running which match...".
final lines = output.trim().split('\n').where((l) => l.trim().isNotEmpty);
return lines.isEmpty;
```

### WR-02: `_handleResponse` casts `message['id'] as int` — crashes on non-integer id from server

**File:** `apps/flutter_app/packages/acp_client/lib/acp_client.dart:243`
**Issue:** `final id = message['id'] as int;` throws `TypeError` if the server sends a response with a string or fractional id. JSON-RPC 2.0 permits string, number, or null ids. While the DSH ACP server uses integer ids, the client is at the wire boundary and should be defensive. A `TypeError` here is thrown synchronously inside `_handleMessage` (a stream `onData` callback), so it IS caught by the stream's `onError` handler — but that handler silently drains it (line 33-35), so the matching pending completer never completes and the request hangs forever.

**Fix:** Use a null-safe cast with a fallback:
```dart
void _handleResponse(Map<String, dynamic> message) {
  final id = message['id'];
  if (id is! int) {
    // Malformed response — ignore (untrusted input from server).
    return;
  }
  final completer = _pending.remove(id);
  // ...
}
```

### WR-03: `JsonRpcRequest.fromJson` / `JsonRpcResponse.fromJson` cast `id` as int without validation

**File:** `apps/flutter_app/packages/acp_client/lib/acp_protocol.dart:30, 73`
**Issue:** Both `fromJson` factories do `json['id'] as int`. If a server request or response carries a non-integer id, this throws `TypeError`. For `JsonRpcRequest.fromJson`, this is called from `_handleServerRequest` (async, fire-and-forget — see CR-02). For `JsonRpcResponse.fromJson`, it is not currently called in any hot path, but it's a latent crash for future callers.

**Fix:** Add a null/type check before casting, or document that these factories assume integer ids and validate at the call site.

### WR-04: `shutdown` does not reset `_process` — double-shutdown re-awaits exit code

**File:** `apps/flutter_app/lib/engine/dsh_process.dart:166-209`
**Issue:** After `_cleanup()`, `_process` still holds the dead `Process` reference. If `shutdown()` is called a second time (e.g., app dispose + OS signal handler), it re-enters the body, calls `process.stdin.close()` (caught by try/catch), then `await process.exitCode.timeout(timeout)`. Since the process already exited, `exitCode` returns immediately with the cached code — so this is not a crash. However, `_cleanup()` is called again, which calls `client.close()` on an already-closed client (harmless) and cancels an already-cancelled stderr subscription (harmless). The `ForceKilled` path after SIGKILL also re-awaits `exitCode` which may already be completed.

This is a robustness concern, not a crash, but it means `dispose()` followed by `shutdown()` does redundant work and the `ForceKilled` result is never returned on the second call.

**Fix:** Null out `_process` in `_cleanup()` and add an early return in `shutdown()`:
```dart
Future<void> _cleanup() async {
  // ... existing cleanup ...
  _process = null;
}

Future<ShutdownResult> shutdown({...}) async {
  final process = _process;
  if (process == null) {
    return const CleanExit(0);
  }
  // ... rest of shutdown ...
}
```

### WR-05: `AcpTransport.messages` creates a new stream on every access — silent data loss if called twice

**File:** `apps/flutter_app/packages/acp_client/lib/acp_transport.dart:63-77`
**Issue:** `messages` is a getter that returns a new stream transformation chain each time it's called. The `_input` stream is a single-subscription stream (subprocess stdout). If `messages` is accessed a second time after the first listener has already subscribed, the second call will throw a "Stream has already been listened to" error or silently fail to receive data. In the current code, `AcpClient`'s constructor calls it exactly once, so this works — but it's a footgun for future callers.

**Fix:** Cache the stream in the constructor or make `messages` a `late final` field:
```dart
late final Stream<Map<String, dynamic>> messages = _buildMessagesStream();

Stream<Map<String, dynamic>> _buildMessagesStream() {
  return _input
      .transform(utf8.decoder)
      .transform(const LineSplitter())
      .where((line) => line.trim().isNotEmpty)
      .map((line) { ... })
      .where((m) => m != null)
      .cast<Map<String, dynamic>>();
}
```

### WR-06: `build_dsh_release.sh` — `cd` into workdir without restoring; `zip` may not be installed

**File:** `scripts/build_dsh_release.sh:150, 196`
**Issue:** Line 150 `cd "$WORKDIR/dsh"` changes the shell's working directory for the rest of the script. The `OUTPUT_DIR` was already resolved to an absolute path (line 139), so subsequent `zip -r "$ZIP_PATH"` works. However, if the script is sourced or if a future edit adds commands after the build that expect to be in `REPO_ROOT`, they'll silently run in the temp workdir. Additionally, `zip` is not guaranteed to be installed on minimal CI images (e.g., some Ubuntu runners need `apt-get install zip`). The script will fail with `command not found` at line 196.

**Fix:** Use subshells for `cd` or use `git -C "$WORKDIR/dsh" checkout`, and add a `zip` availability check:
```bash
if ! command -v zip >/dev/null 2>&1; then
  echo "ERROR: zip not found — install zip (apt-get install zip)" >&2
  exit 1
fi
```

## Info

### IN-01: `SessionNewParams.toJson()` always serializes `mcpServers` but never `additionalDirectories`

**File:** `apps/flutter_app/packages/acp_client/lib/acp_types.dart:153-158`
**Issue:** `toJson()` includes `mcpServers` (always, even when empty) but omits `additionalDirectories`. The `newSession` method in `acp_client.dart:122-125` manually patches the wire payload to add `additionalDirectories` when non-empty. This is inconsistent — either both should be in `toJson()` or both should be patched. The current approach works (server accepts empty `mcpServers`), but the asymmetry is a maintenance trap.

**Fix:** Either include both fields in `toJson()` (and remove the manual patch in `newSession`), or omit both and patch both in `newSession`.

### IN-02: `_handleMessage` silently drops messages with neither `id` nor `method`

**File:** `apps/flutter_app/packages/acp_client/lib/acp_client.dart:225-240`
**Issue:** If a message has neither `id` nor `method` (e.g., a malformed JSON object `{}`), all three branches are skipped and the message is silently ignored. This is arguably acceptable for untrusted input, but it means a corrupt response to a pending request would leave the completer hanging. Consider logging a warning or treating this as a protocol error.

**Fix:** Add an `else` branch that logs a diagnostic (reference-first — no raw payload):
```dart
} else {
  // Malformed message (no id, no method) — ignore.
  // Pending requests will time out at the caller level.
}
```

### IN-03: `engine_health.dart:72` — `catch (e)` includes `AcpRpcException` in the generic catch

**File:** `apps/flutter_app/lib/engine/engine_health.dart:70-73`
**Issue:** The `on AcpRpcException catch (e)` block at line 70 is followed by a generic `catch (e)` at line 72. This is correct ordering (specific before generic), but the generic catch will also swallow `StateError`, `ArgumentError`, and any other exception from `client.initialize()`. The reason string `'initialize failed: $e'` may leak internal exception details. Since this is a health probe (not user-facing), this is acceptable, but consider whether the reason should be sanitized before logging.

**Fix:** No change needed for Phase 112. Note for future: sanitize reason strings before they reach UI or telemetry.

### IN-04: `run_v4_gates.py` — `gate_dart_analyze` runs `dart analyze apps/flutter_app` from `repo_root`, but `dart analyze` expects a target relative to CWD

**File:** `scripts/run_v4_gates.py:155-161`
**Issue:** `subprocess.run([dart, "analyze", "apps/flutter_app"], cwd=repo_root)` — this is correct. However, the `acp_client` sub-package has its own `analysis_options.yaml` that excludes `test/**`. Running `dart analyze apps/flutter_app` from the repo root may not pick up the sub-package's analysis options correctly if the Flutter app's `pubspec.yaml` doesn't propagate the include path. This is a configuration concern, not a bug — the gate will surface any analyzer issues regardless.

**Fix:** No change needed. Verify in CI that `dart analyze apps/flutter_app` correctly analyzes the `packages/acp_client` library code (not just the test-excluded files).

---

## Security Verification (Phase 112 focus areas)

### Approval Security (CRITICAL) — PASS

- `approval_policy.dart`: Unknown kind → `AutoDeny` (line 69-71). terminal/execute_code → `RenderCard` only if `onUserCard` is set (line 74-77). No UI → `AutoDeny` (line 80). No `AutoAllow` subtype exists in the sealed class hierarchy (`acp_types.dart:506-525`).
- Negative grep for `allow-always`, `allow_all`, `allow-all`, `remember`, `batch` in `approval_policy.dart` source: **only present in comments and test assertions** (expected for negative grep tests). No production code path produces these.
- `assertValidOptionId` (line 137-145) rejects any optionId other than `allow-once` / `reject-once`.
- `resolveCard` only produces `allow-once` or `reject-once` (line 96-100). No durable grant path.
- Default policy (`defaultPolicy`, line 130) denies all kinds including terminal/execute_code.
- `acp.cordis.yml`: `approval.policy: ask` (line 44), `sandbox-policy.mode: workspace-write` (line 26). Terminal/execute_code requests escalate to `session/request_permission`.

### Secret Handling (CRITICAL) — PASS

- Grep for `DEEPSEEK_API_KEY`, `sk-`, `secret`, `password`, `api_key` in production code: **only in comments and environment variable names** (no hardcoded values).
- `dsh_config.dart:142`: `env['DEEPSEEK_API_KEY'] = apiKey` — API key injected via environment map only. `buildEnvironment` is pure (no side effects, no file writes). Verified by test `dsh_config_test.dart:130-157`.
- `dsh_process.dart:110-116`: API key passed to `config.buildEnvironment(apiKey)`, never logged. Stderr is collected as diagnostics only (line 134-139).
- `engines/acp.cordis.yml:5`: "The API key is runtime-injected via environment, NOT baked into this config." No secrets in config.
- `test_build_dsh_release.sh:102`: Grep assertion for no secrets in `engines/`.

### Subprocess Lifecycle (HIGH) — PASS (with WR-01 caveat)

- `dsh_process.dart`: spawn → health probe → graceful shutdown (stdin close → wait 10s → SIGTERM → wait 5s → SIGKILL). Zero-orphan assertion via `ps -p` / `tasklist`.
- Reference-first stderr logging: stderr lines collected to `_stderrLines` list (line 78, 138), not echoed to UI. Exposed as read-only `List.unmodifiable` (line 96).
- Tests cover clean shutdown, timeout/force-kill, and PID tracking (`dsh_process_test.dart:109-189`).
- **WR-01**: Windows orphan detection has a substring-match false-negative risk.

### ACP Protocol Correctness (HIGH) — PASS

- NDJSON framing: `acp_transport.dart` writes `jsonEncode(message) + "\n"` (line 47), reads via `LineSplitter` (line 66). No Content-Length headers.
- Protocol version 1: `acp_protocol.dart:14` `const int protocolVersion = 1`. Health probe asserts `protocolVersion == 1` (`engine_health.dart:57`).
- Single in-flight (DP-4): `acp_client.dart:140-158` — `_inflightSessions` set, `StateError` on second prompt for same session. Removed in `finally` block.
- session/new absolute cwd: `acp_client.dart:109-111` — `File(cwd).isAbsolute` check, `ArgumentError` on relative path.
- additionalDirectories/mcpServers rejection: mock server rejects with -32602 (`mock_acp_server.dart:141-167`), tested in `session_new_test.dart:70-127`.

### Frozen Directory Compliance (GATE) — PASS

- `git diff --name-only 45334bb^..HEAD` against all LEG-01 frozen dirs (services/gateway, services/wecom-service, services/qqbot-service, services/arena-service, packages/agent-core, packages/arena-engine, packages/acp-client, packages/ui-core, apps/web, apps/desktop): **zero files modified**.

### Test Coverage (GATE) — PASS

- `apps/flutter_app/lib/` → `apps/flutter_app/test/` (widget_test.dart, engine/*)
- `apps/flutter_app/lib/engine/` → `apps/flutter_app/test/engine/` (dsh_config_test, dsh_process_test, mock_engine_process)
- `apps/flutter_app/packages/acp_client/lib/` → `apps/flutter_app/packages/acp_client/test/` (7 test files + fixtures)
- Meta-test gate (`run_v4_gates.py:459-484`) verifies every `lib/` dir with `.dart` files has a matching `test/` dir with non-empty `_test.dart` files.

---

_Reviewed: 2026-08-13T17:08:09Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
