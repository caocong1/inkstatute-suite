import 'dart:io';

/// Content package directory path resolution.
///
/// Resolves paths for the skill content auto-update system (SKL-04).
/// All content lives under a single base directory to guarantee
/// same-filesystem atomic renames.
///
/// Directory structure:
/// ```
/// <contentDir>/
///   skills/
///     1.0.0/
///       content-manifest.json
///       legal-commercial/
///         contract-review/SKILL.md
///         ...
///     1.1.0/
///       ...
///     current         -> pointer file containing "1.1.0"
///     last-good       -> pointer file containing "1.0.0"
/// ```
///
/// On Windows: `%LOCALAPPDATA%\InkStatute\content`
/// On Linux/WSL: `~/.local/share/InkStatute/content`
class ContentPaths {
  const ContentPaths._();

  /// Resolves the base content directory.
  ///
  /// Follows the same pattern as [DshPaths.resolveDshHome]:
  /// - Windows: `%LOCALAPPDATA%\InkStatute\content`
  /// - Linux/WSL: `~/.local/share/InkStatute/content`
  static String resolveContentDir() {
    if (Platform.isWindows) {
      final localAppData = Platform.environment['LOCALAPPDATA'];
      if (localAppData != null && localAppData.isNotEmpty) {
        return '$localAppData\\InkStatute\\content';
      }
      final userProfile =
          Platform.environment['USERPROFILE'] ?? r'C:\Users\Default';
      return '$userProfile\\AppData\\Local\\InkStatute\\content';
    }
    final home = Platform.environment['HOME'] ?? '/';
    return '$home/.local/share/InkStatute/content';
  }

  /// Returns the skills directory: `<contentDir>/skills`.
  static String resolveSkillsDir() {
    return '${resolveContentDir()}/skills';
  }

  /// Returns the release directory for a given version: `<skillsDir>/<version>`.
  static String resolveReleaseDir(String version) {
    return '${resolveSkillsDir()}/$version';
  }

  /// Returns the staging directory for a given version:
  /// `<skillsDir>/<version>-staging`.
  ///
  /// Used during atomic update: extract here, validate, then rename to
  /// [resolveReleaseDir].
  static String resolveStagingDir(String version) {
    return '${resolveSkillsDir()}/$version-staging';
  }

  /// Returns the path to the `current` pointer file.
  ///
  /// This file contains the version string of the active release.
  static String resolveCurrentPointer() {
    return '${resolveSkillsDir()}/current';
  }

  /// Returns the path to the `last-good` pointer file.
  ///
  /// This file contains the version string of the previous successful
  /// release, used for rollback.
  static String resolveLastGoodPointer() {
    return '${resolveSkillsDir()}/last-good';
  }

  /// Reads the `current` pointer file and returns the version string.
  ///
  /// Returns `null` if the pointer file does not exist (first install
  /// or clean state).
  static String? getCurrentReleaseVersion() {
    final pointerFile = File(resolveCurrentPointer());
    if (!pointerFile.existsSync()) return null;
    final version = pointerFile.readAsStringSync().trim();
    return version.isEmpty ? null : version;
  }

  /// Returns the path to the current release directory based on the
  /// `current` pointer.
  ///
  /// Returns `null` if no current release is set.
  static String? getCurrentReleasePath() {
    final version = getCurrentReleaseVersion();
    if (version == null) return null;
    return resolveReleaseDir(version);
  }

  /// Reads the `last-good` pointer file and returns the version string.
  ///
  /// Returns `null` if the pointer file does not exist.
  static String? getLastGoodReleaseVersion() {
    final pointerFile = File(resolveLastGoodPointer());
    if (!pointerFile.existsSync()) return null;
    final version = pointerFile.readAsStringSync().trim();
    return version.isEmpty ? null : version;
  }

  /// Returns the path to the last-good release directory.
  ///
  /// Returns `null` if no last-good release is set.
  static String? getLastGoodReleasePath() {
    final version = getLastGoodReleaseVersion();
    if (version == null) return null;
    return resolveReleaseDir(version);
  }
}
