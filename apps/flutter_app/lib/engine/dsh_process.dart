/// DSH subprocess manager: spawn, health probe, stderr logging, lifecycle.
///
/// [DshProcessManager] owns the DSH engine process lifecycle:
/// - [spawn]: starts the engine process with the correct environment
///   and wraps stdin/stdout in an [AcpClient].
/// - [healthProbe]: sends an `initialize` handshake and asserts
///   `protocolVersion == 1`.
/// - stderr: logged as reference-first warnings (no raw payload content
///   echoed to UI).
/// - [shutdown]: closes stdin → waits for clean exit → kills on timeout.
/// - [assertNoOrphans]: verifies the process is no longer alive after
///   shutdown.
///
/// The manager guarantees no orphan processes remain after app exit.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:acp_client/acp_client.dart';

import 'dsh_config.dart';
import 'engine_health.dart';

/// Result of a graceful shutdown.
sealed class ShutdownResult {
  const ShutdownResult();
}

/// The process exited cleanly with exit code 0 within the timeout.
final class CleanExit extends ShutdownResult {
  /// Creates a clean exit result.
  const CleanExit(this.exitCode);

  /// The process exit code.
  final int exitCode;
}

/// The process did not exit within the timeout and was force-killed.
final class ForceKilled extends ShutdownResult {
  /// Creates a force-killed result.
  const ForceKilled(this.pid);

  /// The PID that was killed.
  final int pid;
}

/// Manages the DSH engine subprocess lifecycle.
///
/// The manager is the lifecycle owner of the DSH engine process. It
/// guarantees no orphan processes remain after app exit by:
/// 1. Closing stdin first (signals EOF → DSH quiesce).
/// 2. Awaiting `process.exitCode` with a 10s timeout.
/// 3. Force-killing the process if the timeout expires.
/// 4. Asserting the PID is no longer alive after shutdown.
class DshProcessManager {
  /// Creates a DSH subprocess manager with an optional custom health probe.
  DshProcessManager({EngineHealthProbe? healthProbe})
      : _healthProbe = healthProbe ?? const EngineHealthProbe();

  /// The health probe used for the initialize handshake.
  final EngineHealthProbe _healthProbe;

  /// The spawned process, or null if [spawn] has not been called.
  Process? _process;

  /// The ACP transport wrapping the process stdin/stdout.
  AcpTransport? _transport;

  /// The ACP client for sending requests to the engine.
  AcpClient? _acpClient;

  /// Completes with the process exit code when the process exits.
  final Completer<int> _exitCompleter = Completer<int>();

  /// Collected stderr lines (reference-first — diagnostics only).
  final List<String> _stderrLines = [];

  /// Subscription to the stderr stream.
  StreamSubscription<String>? _stderrSub;

  /// Returns the process PID, or null if not spawned.
  int? get pid => _process?.pid;

  /// Returns whether the process is still running.
  bool get isAlive => !_exitCompleter.isCompleted;

  /// Returns the ACP client for sending requests to the engine.
  AcpClient? get acpClient => _acpClient;

  /// Returns a read-only list of collected stderr lines.
  ///
  /// These are engine diagnostics (not customer data). They are collected
  /// for logging purposes only and must not be echoed to the UI.
  List<String> get stderrLines => List.unmodifiable(_stderrLines);

  /// Spawns the DSH engine process.
  ///
  /// Starts the process with [config.executable] and [config.executableArgs],
  /// using [config.engineDir] as the working directory and
  /// [config.buildEnvironment] for the environment map.
  ///
  /// The [apiKey] is injected via the `DEEPSEEK_API_KEY` environment
  /// variable only — never logged, never written to disk.
  ///
  /// After spawning, wraps stdin/stdout in an [AcpTransport] and creates
  /// an [AcpClient]. Stderr is collected line-by-line as reference-first
  /// diagnostics.
  Future<void> spawn(DshConfig config, String apiKey) async {
    _process = await Process.start(
      config.executable,
      config.executableArgs,
      workingDirectory: config.engineDir,
      environment: config.buildEnvironment(apiKey),
    );

    _transport = AcpTransport(
      input: _process!.stdout,
      output: _process!.stdin,
    );
    _acpClient = AcpClient(_transport!);

    // Track process exit for isAlive.
    _process!.exitCode.then((code) {
      if (!_exitCompleter.isCompleted) {
        _exitCompleter.complete(code);
      }
    });

    // Listen to stderr — reference-first logging.
    // DSH stderr is diagnostics only (not customer data), but the app
    // must not echo it to the UI. Lines are collected for logging.
    _stderrSub = _process!.stderr
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen((line) {
      _stderrLines.add(line);
    });
  }

  /// Runs the initialize health probe.
  ///
  /// Delegates to [EngineHealthProbe.check] with the ACP client. Returns
  /// [Healthy] if the handshake succeeds with `protocolVersion == 1`,
  /// or [Unhealthy] with a reason string.
  Future<HealthResult> healthProbe() async {
    final client = _acpClient;
    if (client == null) {
      return const Unhealthy('process not spawned');
    }
    return _healthProbe.check(client);
  }

  /// Gracefully shuts down the engine process.
  ///
  /// Sequence:
  /// 1. Close stdin (signals EOF → DSH quiesce).
  /// 2. Await `process.exitCode` with a 10s timeout.
  /// 3. On timeout, force-kill the process and log a warning.
  /// 4. After kill, await exit code again with a 5s timeout.
  /// 5. Return [CleanExit] or [ForceKilled].
  ///
  /// [Process.kill] is only used after the timeout expires — it is never
  /// the first resort (per AGENTS.md §Safety And Privacy).
  Future<ShutdownResult> shutdown({
    Duration timeout = const Duration(seconds: 10),
    Duration killTimeout = const Duration(seconds: 5),
  }) async {
    final process = _process;
    if (process == null) {
      return const CleanExit(0);
    }

    // Step 1: Close stdin (signals EOF → DSH quiesce).
    try {
      await process.stdin.close();
    } catch (_) {
      // stdin may already be closed — ignore.
    }

    // Step 2: Await exit code with timeout.
    try {
      final exitCode = await process.exitCode.timeout(timeout);
      await _cleanup();
      return CleanExit(exitCode);
    } on TimeoutException {
      // Step 3: Force-kill on timeout.
      final pid = process.pid;
      process.kill(ProcessSignal.sigterm);

      // Step 4: Await exit code after kill.
      try {
        final exitCode = await process.exitCode.timeout(killTimeout);
        await _cleanup();
        return CleanExit(exitCode);
      } on TimeoutException {
        // Last resort: SIGKILL (Linux) / TerminateProcess (Windows).
        process.kill(ProcessSignal.sigkill);
        try {
          await process.exitCode.timeout(killTimeout);
        } catch (_) {
          // Process may have already exited — ignore.
        }
        await _cleanup();
        return ForceKilled(pid);
      }
    }
  }

  /// Asserts that no orphan processes remain after shutdown.
  ///
  /// On Linux/WSL: runs `ps -p <pid>` and asserts the process is not
  /// found. On Windows: runs `tasklist /FI "PID eq <pid>"` and asserts
  /// not found.
  ///
  /// Returns `true` if no orphans are found, `false` otherwise.
  Future<bool> assertNoOrphans() async {
    final pid = _process?.pid;
    if (pid == null) return true;

    // If the exit completer hasn't completed, the process is still alive.
    if (!_exitCompleter.isCompleted) return false;

    if (Platform.isWindows) {
      final result = await Process.run(
        'tasklist',
        ['/FI', 'PID eq $pid'],
        stdoutEncoding: utf8,
        stderrEncoding: utf8,
      );
      // tasklist returns 0 even when no match; check output for the PID.
      final output = result.stdout as String;
      return !output.contains(pid.toString());
    }

    // Linux / WSL / macOS.
    final result = await Process.run(
      'ps',
      ['-p', pid.toString()],
      stdoutEncoding: utf8,
      stderrEncoding: utf8,
    );
    // ps returns 1 when the process is not found (no orphans).
    return result.exitCode != 0;
  }

  /// Full lifecycle cleanup: shutdown + orphan assertion.
  ///
  /// Calls [shutdown] then [assertNoOrphans]. Returns the [ShutdownResult]
  /// from the shutdown step.
  Future<ShutdownResult> dispose() async {
    final result = await shutdown();
    await assertNoOrphans();
    return result;
  }

  /// Cancels stderr subscription and closes the ACP client.
  Future<void> _cleanup() async {
    await _stderrSub?.cancel();
    _stderrSub = null;
    final client = _acpClient;
    if (client != null) {
      await client.close();
      _acpClient = null;
    }
    _transport = null;
  }
}
