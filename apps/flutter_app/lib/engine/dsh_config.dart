/// DSH configuration: path resolution and environment construction.
///
/// [DshPaths] provides static helpers for resolving the DSH_HOME runtime
/// directory, the bundled engine directory, and the engine's bin/config
/// paths. [DshConfig] holds the spawn command and builds the environment
/// map for [Process.start].
///
/// The API key is injected via the environment map only — it is never
/// written to disk, never logged, and never persisted beyond the returned
/// [Map]. See AGENTS.md §Safety And Privacy.
library;

import 'dart:io';

/// Static helpers for DSH path resolution.
///
/// All paths are platform-aware: Windows uses `%LOCALAPPDATA%`, Linux/WSL
/// uses `~/.local/share`.
class DshPaths {
  const DshPaths._();

  /// Resolves the DSH_HOME runtime directory.
  ///
  /// On Windows: `%LOCALAPPDATA%\\InkStatute\\runtime\\.dsh`.
  /// On Linux/WSL: `~/.local/share/InkStatute/runtime/.dsh`.
  static String resolveDshHome() {
    if (Platform.isWindows) {
      final localAppData = Platform.environment['LOCALAPPDATA'];
      if (localAppData != null && localAppData.isNotEmpty) {
        return '$localAppData\\InkStatute\\runtime\\.dsh';
      }
      // Fallback: construct from USERPROFILE if LOCALAPPDATA is unset.
      final userProfile = Platform.environment['USERPROFILE'] ?? r'C:\Users\Default';
      return '$userProfile\\AppData\\Local\\InkStatute\\runtime\\.dsh';
    }
    // Linux / WSL / macOS dev.
    final home = Platform.environment['HOME'] ?? '/';
    return '$home/.local/share/InkStatute/runtime/.dsh';
  }

  /// Resolves the bundled engine directory for a given engine version.
  ///
  /// Returns `<appDir>/engine/<version>`. The app directory is the current
  /// working directory in dev; in production it is the executable's
  /// directory (finalized when the engine release pipeline, DSH-03, is
  /// built).
  static String resolveEngineDir(String engineVersion) {
    return '${Directory.current.path}/engine/$engineVersion';
  }

  /// Returns the engine bin path: `[engineDir]/lib/bin.js`.
  static String engineBinPath(String engineDir) {
    return '$engineDir/lib/bin.js';
  }

  /// Returns the engine ACP composition config path: `[engineDir]/acp.cordis.yml`.
  static String engineConfigPath(String engineDir) {
    return '$engineDir/acp.cordis.yml';
  }
}

/// DSH subprocess configuration.
///
/// Holds the spawn command (executable + arguments), engine directory,
/// and builds the environment map for [Process.start].
///
/// The API key is passed through [buildEnvironment] only — it exists in
/// the returned [Map] for the child process and is never written to disk,
/// never logged, and never persisted elsewhere.
class DshConfig {
  /// Creates a DshConfig with an explicit executable and arguments.
  const DshConfig._({
    required this.engineDir,
    required this.executable,
    required this.executableArgs,
  });

  /// Production configuration: spawns `node [engineDir]/lib/bin.js
  /// --config [engineDir]/acp.cordis.yml`.
  factory DshConfig.forEngine(String engineDir) {
    return DshConfig._(
      engineDir: engineDir,
      executable: 'node',
      executableArgs: [
        DshPaths.engineBinPath(engineDir),
        '--config',
        DshPaths.engineConfigPath(engineDir),
      ],
    );
  }

  /// Test configuration: spawns a custom executable with custom arguments.
  ///
  /// Used by engine tests to spawn the mock engine process instead of the
  /// real DSH engine. Not intended for production use.
  factory DshConfig.test({
    required String executable,
    required List<String> executableArgs,
    String engineDir = '.',
  }) {
    return DshConfig._(
      engineDir: engineDir,
      executable: executable,
      executableArgs: executableArgs,
    );
  }

  /// The engine directory (used as the working directory for [Process.start]).
  final String engineDir;

  /// The executable to spawn (e.g. `node` or `dart`).
  final String executable;

  /// Arguments to pass to the executable.
  final List<String> executableArgs;

  /// Returns the engine bin path: `[engineDir]/lib/bin.js`.
  String get engineBinPath => DshPaths.engineBinPath(engineDir);

  /// Returns the engine config path: `<engineDir>/acp.cordis.yml`.
  String get engineConfigPath => DshPaths.engineConfigPath(engineDir);

  /// Builds the environment map for [Process.start].
  ///
  /// Returns a [Map] containing:
  /// - `DSH_HOME`: the platform-appropriate runtime path (or [dshHome]
  ///   override).
  /// - `DEEPSEEK_API_KEY`: the API key (injected via environment only).
  /// - `DSH_PERMISSION_MODE`: the sandbox permission mode.
  /// - All inherited environment variables (PATH, SYSTEMROOT, HOME, etc.).
  ///
  /// The API key is passed through only — never logged, never persisted
  /// to disk. This method is pure: it reads [Platform.environment] and
  /// returns a new [Map] with no side effects.
  Map<String, String> buildEnvironment(
    String apiKey, {
    String? dshHome,
    String permissionMode = 'workspace-write',
  }) {
    final env = Map<String, String>.from(Platform.environment);
    env['DSH_HOME'] = dshHome ?? DshPaths.resolveDshHome();
    env['DEEPSEEK_API_KEY'] = apiKey;
    env['DSH_PERMISSION_MODE'] = permissionMode;
    return env;
  }
}
