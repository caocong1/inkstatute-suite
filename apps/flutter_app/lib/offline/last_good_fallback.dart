/// Last-good fallback — offline mode with last-good engine+content (PKG-04).
///
/// When offline, the app can start with the last-good engine and content
/// pack, allowing users to view history. New tasks require network.
library;

import 'dart:io';

/// Manages last-good engine and content pack for offline use.
class LastGoodFallback {
  /// Creates a last-good fallback manager.
  LastGoodFallback({
    required this.appDataDir,
  });

  /// The app's data directory.
  final String appDataDir;

  /// Returns the path to the last-good engine directory.
  String get lastGoodEnginePath => '$appDataDir/engine';

  /// Returns the path to the last-good content pack directory.
  String get lastGoodContentPath => '$appDataDir/content';

  /// Returns true if the app can start offline with last-good resources.
  Future<bool> canStartOffline() async {
    return await verifyLastGood();
  }

  /// Verifies that last-good engine and content are available.
  Future<bool> verifyLastGood() async {
    final engineDir = Directory(lastGoodEnginePath);
    final contentDir = Directory(lastGoodContentPath);
    return engineDir.existsSync() && contentDir.existsSync();
  }

  /// Switches to last-good engine and content.
  ///
  /// In production, this would swap the active engine and content
  /// to the last-good versions. For now, it verifies availability.
  Future<bool> switchToLastGood() async {
    return await verifyLastGood();
  }

  /// Returns true if a new task can be started (requires network).
  ///
  /// Offline mode only supports viewing history, not new tasks.
  static const bool newTasksRequireNetwork = true;
}
