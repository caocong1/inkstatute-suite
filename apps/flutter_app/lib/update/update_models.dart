/// Update models for the three-layer update system (PKG-02).
///
/// Defines update layers, status, and result types.
library;

/// Update layers in the three-layer update system.
enum UpdateLayer {
  /// App layer — installer self-update.
  app,

  /// Engine layer — zip atomic replace (DISABLED auto, only with app version).
  engine,

  /// Content pack layer — auto-update (only auto layer).
  content,
}

/// Status of an update check for a single layer.
class UpdateStatus {
  /// Creates an update status.
  const UpdateStatus({
    required this.layer,
    required this.updateAvailable,
    this.currentVersion,
    this.latestVersion,
    this.manifestUrl,
  });

  /// The update layer.
  final UpdateLayer layer;

  /// Whether an update is available.
  final bool updateAvailable;

  /// Current installed version.
  final String? currentVersion;

  /// Latest available version.
  final String? latestVersion;

  /// URL to the manifest file.
  final String? manifestUrl;
}

/// Result of an update operation.
sealed class UpdateResult {
  const UpdateResult();
}

/// Successful update.
class UpdateSuccess extends UpdateResult {
  /// Creates a success result.
  const UpdateSuccess(this.layer, this.newVersion);

  /// The layer that was updated.
  final UpdateLayer layer;

  /// The new version installed.
  final String newVersion;
}

/// Failed update.
class UpdateFailure extends UpdateResult {
  /// Creates a failure result.
  const UpdateFailure(this.layer, this.error);

  /// The layer that failed to update.
  final UpdateLayer layer;

  /// Error message.
  final String error;
}

/// Update was skipped (e.g., engine auto-update disabled).
class UpdateSkipped extends UpdateResult {
  /// Creates a skipped result.
  const UpdateSkipped(this.layer, this.reason);

  /// The layer that was skipped.
  final UpdateLayer layer;

  /// Reason for skipping.
  final String reason;
}

/// Parsed manifest information.
class ManifestInfo {
  /// Creates manifest info.
  const ManifestInfo({
    required this.version,
    required this.sha256,
    required this.downloadUrl,
    this.builtAt,
  });

  /// Version string.
  final String version;

  /// SHA-256 hash of the package.
  final String sha256;

  /// Download URL for the package.
  final String downloadUrl;

  /// Build timestamp.
  final String? builtAt;

  /// Parses from JSON map.
  static ManifestInfo fromJson(Map<String, dynamic> json) {
    return ManifestInfo(
      version: json['version'] as String? ?? '',
      sha256: json['sha256'] as String? ?? '',
      downloadUrl: json['downloadUrl'] as String? ?? '',
      builtAt: json['builtAt'] as String?,
    );
  }
}
