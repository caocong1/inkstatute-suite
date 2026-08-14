import 'dart:convert';
import 'dart:io';

import 'package:flutter_app/content/content_paths.dart';
import 'package:flutter_app/content/manifest_schema.dart';
import 'package:flutter_app/content/update_exception.dart';
import 'package:http/http.dart' as http;
import 'package:pub_semver/pub_semver.dart';

/// Content package auto-updater (SKL-04).
///
/// Fetches remote content manifest, compares versions, downloads and
/// verifies content packages, and atomically switches the active
/// release. On failure, rolls back to the last-good release.
///
/// The updater is the ONLY automatic update layer in the system.
/// Engine and app updates are never automatic.
class ContentUpdater {
  /// Base URL for content releases.
  ///
  /// Defaults to `CONTENT_RELEASE_URL` env var or a placeholder.
  /// The manifest is fetched from `<contentReleaseUrl>/content-manifest.json`
  /// and the zip from `<contentReleaseUrl>/legal-skills-content-<version>.zip`.
  final String contentReleaseUrl;

  /// Current engine version for compatibility checking.
  ///
  /// Defaults to the DSH pin `47f943859b`.
  final String engineVersion;

  /// HTTP client for network requests (injectable for testing).
  final http.Client _httpClient;

  /// Creates a ContentUpdater.
  ///
  /// - [contentReleaseUrl]: Override the content release URL. Defaults
  ///   to `CONTENT_RELEASE_URL` env var or a placeholder.
  /// - [engineVersion]: Override the engine version for compatibility
  ///   checks. Defaults to `47f943859b`.
  /// - [httpClient]: Inject an HTTP client for testing.
  ContentUpdater({
    String? contentReleaseUrl,
    String? engineVersion,
    http.Client? httpClient,
  })  : contentReleaseUrl = contentReleaseUrl ??
            Platform.environment['CONTENT_RELEASE_URL'] ??
            'https://github.com/inkstatute/legal-skills-content/releases/latest/download',
        engineVersion = engineVersion ?? '47f943859b',
        _httpClient = httpClient ?? http.Client();

  /// Fetches the remote content manifest.
  ///
  /// Downloads `<contentReleaseUrl>/content-manifest.json` and parses
  /// it with [ContentManifest.fromJson].
  ///
  /// Throws [UpdateException] with kind [UpdateExceptionKind.networkError]
  /// on HTTP failure, or [UpdateExceptionKind.invalidManifest] on parse
  /// failure.
  Future<ContentManifest> fetchRemoteManifest() async {
    final url = Uri.parse('$contentReleaseUrl/content-manifest.json');
    final http.Response response;
    try {
      response = await _httpClient.get(url);
    } catch (e) {
      throw UpdateException(
        UpdateExceptionKind.networkError,
        'Failed to fetch manifest: $e',
      );
    }

    if (response.statusCode != 200) {
      throw UpdateException(
        UpdateExceptionKind.networkError,
        'Manifest fetch returned HTTP ${response.statusCode}',
      );
    }

    try {
      final json = jsonDecode(response.body) as Map<String, dynamic>;
      return ContentManifest.fromJson(json);
    } catch (e) {
      throw UpdateException(
        UpdateExceptionKind.invalidManifest,
        'Failed to parse manifest JSON: $e',
      );
    }
  }

  /// Loads the local manifest from the current release directory.
  ///
  /// Returns `null` if no current release is installed.
  ///
  /// Throws [UpdateException] with kind [UpdateExceptionKind.invalidManifest]
  /// if the manifest file exists but cannot be parsed.
  Future<ContentManifest?> loadLocalManifest() async {
    final currentPath = ContentPaths.getCurrentReleasePath();
    if (currentPath == null) return null;

    final manifestFile = File('$currentPath/content-manifest.json');
    if (!manifestFile.existsSync()) return null;

    try {
      final json =
          jsonDecode(manifestFile.readAsStringSync()) as Map<String, dynamic>;
      return ContentManifest.fromJson(json);
    } catch (e) {
      throw UpdateException(
        UpdateExceptionKind.invalidManifest,
        'Failed to parse local manifest: $e',
      );
    }
  }

  /// Returns true if the remote manifest represents a newer version
  /// than the local manifest.
  ///
  /// If [local] is null (first install), always returns true.
  bool hasUpdate(ContentManifest remote, ContentManifest? local) {
    if (local == null) return true;
    final remoteVersion = Version.parse(remote.releaseVersion);
    final localVersion = Version.parse(local.releaseVersion);
    return remoteVersion > localVersion;
  }

  /// Checks for a downgrade attack.
  ///
  /// Throws [UpdateException] with kind [UpdateExceptionKind.versionDowngrade]
  /// if the remote version is lower than the local version.
  void checkDowngradeAttack(ContentManifest remote, ContentManifest local) {
    final remoteVersion = Version.parse(remote.releaseVersion);
    final localVersion = Version.parse(local.releaseVersion);
    if (remoteVersion < localVersion) {
      throw UpdateException(
        UpdateExceptionKind.versionDowngrade,
        'Remote version ${remote.releaseVersion} < local version ${local.releaseVersion}',
      );
    }
  }

  /// Checks engine compatibility.
  ///
  /// Throws [UpdateException] with kind [UpdateExceptionKind.engineMismatch]
  /// if the manifest's min_engine_version doesn't match the current engine.
  void checkEngineCompatibility(ContentManifest manifest) {
    if (!manifest.isCompatibleWith(engineVersion)) {
      throw UpdateException(
        UpdateExceptionKind.engineMismatch,
        'Manifest requires engine ${manifest.minEngineVersion}, current is $engineVersion',
      );
    }
  }

  /// Checks for updates and applies them if available.
  ///
  /// Full flow:
  /// 1. Fetch remote manifest
  /// 2. Load local manifest (may be null)
  /// 3. Check engine compatibility
  /// 4. Check for downgrade attack
  /// 5. If no update, return [UpdateResultUpToDate]
  /// 6. Download zip, verify, extract, atomic switch (Plan 115-02)
  ///
  /// Currently implements steps 1-5. Step 6 (download/extract/switch)
  /// is implemented in Plan 115-02.
  Future<UpdateResult> checkAndUpdate() async {
    final remote = await fetchRemoteManifest();
    final local = await loadLocalManifest();

    checkEngineCompatibility(remote);

    if (local != null) {
      checkDowngradeAttack(remote, local);
    }

    if (!hasUpdate(remote, local)) {
      return UpdateResultUpToDate(remote.releaseVersion);
    }

    // Download + extract + verify + switch — implemented in Plan 115-02.
    // For now, return up-to-date as a stub.
    // TODO(115-02): Implement full download/extract/switch pipeline.
    return UpdateResultUpToDate(remote.releaseVersion);
  }

  /// Closes the HTTP client.
  void close() {
    _httpClient.close();
  }
}
