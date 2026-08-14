import 'package:flutter_app/content/content_paths.dart';

/// Status of the content update system for UI consumption.
///
/// Provides human-readable status messages in Chinese for the
/// lawyer-facing settings page.
class UpdateStatus {
  /// True if current version matches the latest checked version.
  final bool isUpToDate;

  /// Current installed release version, or null if no content installed.
  final String? currentVersion;

  /// Latest version from the last successful check, or null if check
  /// has not been performed or failed.
  final String? latestCheckedVersion;

  /// Timestamp of the last update check, or null if never checked.
  final DateTime? lastCheckedAt;

  /// True if the last check failed due to network/offline error.
  final bool isOffline;

  /// Error message from the last failed check, or null if no error.
  final String? errorMessage;

  const UpdateStatus({
    required this.isUpToDate,
    this.currentVersion,
    this.latestCheckedVersion,
    this.lastCheckedAt,
    this.isOffline = false,
    this.errorMessage,
  });

  /// Creates a status representing "no content installed".
  factory UpdateStatus.noContent() {
    return const UpdateStatus(
      isUpToDate: false,
      currentVersion: null,
      latestCheckedVersion: null,
      isOffline: false,
    );
  }

  /// Creates a status representing "up to date".
  factory UpdateStatus.upToDate(String version) {
    return UpdateStatus(
      isUpToDate: true,
      currentVersion: version,
      latestCheckedVersion: version,
      lastCheckedAt: DateTime.now(),
    );
  }

  /// Creates a status representing "offline, using existing content".
  factory UpdateStatus.offline(String? currentVersion) {
    return UpdateStatus(
      isUpToDate: false,
      currentVersion: currentVersion,
      latestCheckedVersion: null,
      lastCheckedAt: DateTime.now(),
      isOffline: true,
    );
  }

  /// Creates a status representing "update failed, rolled back".
  factory UpdateStatus.failed(String? rolledBackTo, String errorMessage) {
    return UpdateStatus(
      isUpToDate: false,
      currentVersion: rolledBackTo,
      latestCheckedVersion: null,
      lastCheckedAt: DateTime.now(),
      isOffline: false,
      errorMessage: errorMessage,
    );
  }

  /// Human-readable status message in Chinese (lawyer-facing).
  String get displayMessage {
    if (isOffline) {
      if (currentVersion != null) {
        return '技能更新不可用（离线模式），当前版本 v$currentVersion';
      }
      return '技能更新不可用（离线模式），未安装技能内容包';
    }

    if (currentVersion == null) {
      return '未安装技能内容包';
    }

    if (errorMessage != null) {
      return '技能更新失败，已回退到 v$currentVersion';
    }

    if (isUpToDate) {
      return '技能内容已是最新版本 (v$currentVersion)';
    }

    if (latestCheckedVersion != null) {
      return '发现新版本 v$latestCheckedVersion，正在更新...';
    }

    return '当前版本 v$currentVersion';
  }

  /// Gets the current status by inspecting the local content state.
  ///
  /// This is a snapshot — it reads the current pointer and checks
  /// if a release directory exists. Does not perform network checks.
  static UpdateStatus current() {
    final version = ContentPaths.getCurrentReleaseVersion();
    if (version == null) {
      return UpdateStatus.noContent();
    }
    return UpdateStatus.upToDate(version);
  }

  @override
  String toString() =>
      'UpdateStatus(upToDate: $isUpToDate, current: $currentVersion, '
      'latest: $latestCheckedVersion, offline: $isOffline)';
}
