/// Exception types for content package update failures.
///
/// Categorizes update failures for appropriate user-facing messages
/// and rollback decisions.
class UpdateException implements Exception {
  /// The category of update failure.
  final UpdateExceptionKind kind;

  /// Human-readable error message.
  final String message;

  UpdateException(this.kind, this.message);

  @override
  String toString() => 'UpdateException($kind): $message';
}

/// Categories of update exceptions.
enum UpdateExceptionKind {
  /// Network request failed (timeout, DNS, connection refused, HTTP error).
  networkError,

  /// SHA-256 hash verification failed (zip or per-skill).
  hashMismatch,

  /// Remote manifest version is lower than local (downgrade attack).
  versionDowngrade,

  /// Manifest min_engine_version doesn't match current engine version.
  engineMismatch,

  /// Zip extraction failed (corrupted archive, I/O error).
  extractionFailed,

  /// Pointer file update failed (atomic rename failed).
  pointerUpdateFailed,

  /// No current release installed (first install or clean state).
  noCurrentRelease,

  /// No last-good release available for rollback.
  noLastGood,

  /// Manifest JSON is invalid or missing required fields.
  invalidManifest,

  /// Zip entry contains path traversal pattern (security violation).
  pathTraversal,
}

/// Result of a content update check.
///
/// Sealed class hierarchy — exactly one of these is returned by
/// [ContentUpdater.checkAndUpdate].
sealed class UpdateResult {}

/// No update available — current version matches latest checked version.
class UpdateResultUpToDate extends UpdateResult {
  /// The current version that is up to date.
  final String currentVersion;

  UpdateResultUpToDate(this.currentVersion);

  @override
  String toString() => 'UpdateResultUpToDate($currentVersion)';
}

/// Update applied successfully.
class UpdateResultSuccess extends UpdateResult {
  /// The new version that was installed.
  final String newVersion;

  /// The previous version that was replaced (null on first install).
  final String? previousVersion;

  UpdateResultSuccess(this.newVersion, this.previousVersion);

  @override
  String toString() =>
      'UpdateResultSuccess(new: $newVersion, prev: $previousVersion)';
}

/// Update failed — may have rolled back to a previous version.
class UpdateResultFailure extends UpdateResult {
  /// The exception that caused the failure.
  final UpdateException exception;

  /// The version rolled back to, if any. null if no rollback occurred
  /// (e.g., failure before pointer update, or first install with no
  /// previous version).
  final String? rolledBackTo;

  /// True if the failure was due to offline/network error.
  final bool isOffline;

  UpdateResultFailure(
    this.exception, {
    this.rolledBackTo,
    this.isOffline = false,
  });

  @override
  String toString() =>
      'UpdateResultFailure(${exception.kind}, rolledBackTo: $rolledBackTo, offline: $isOffline)';
}
