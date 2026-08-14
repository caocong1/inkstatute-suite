import 'dart:convert';
import 'dart:io';

import 'package:flutter_app/content/content_paths.dart';
import 'package:flutter_app/content/hash_verifier.dart';
import 'package:flutter_app/content/manifest_schema.dart';
import 'package:flutter_app/content/update_exception.dart';
import 'package:flutter_app/content/zip_extractor.dart';
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
  /// 6. Download zip to temp file
  /// 7. Verify zip sha256 (from sidecar)
  /// 8. Extract to staging dir
  /// 9. Verify per-skill sha256 hashes
  /// 10. Atomic rename staging → release dir
  /// 11. Update last-good pointer to previous version
  /// 12. Update current pointer to new version
  /// 13. Cleanup old releases (keep current + last-good)
  ///
  /// On any failure: delete staging dir, keep current pointer unchanged,
  /// return [UpdateResultFailure].
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

    final newVersion = remote.releaseVersion;
    final previousVersion = local?.releaseVersion;
    final stagingDir = ContentPaths.resolveStagingDir(newVersion);
    final releaseDir = ContentPaths.resolveReleaseDir(newVersion);

    String? tempZipPath;
    try {
      // Step 6: Download zip
      tempZipPath = await _downloadZip(newVersion);

      // Step 7: Verify zip sha256 from sidecar
      final sidecarPath = '$tempZipPath.sha256';
      final sidecarFile = File(sidecarPath);
      if (sidecarFile.existsSync()) {
        HashVerifier.verifyZipSha256FromSidecar(tempZipPath, sidecarPath);
      }

      // Step 8: Extract to staging
      await ZipExtractor.extract(tempZipPath, stagingDir);

      // Step 9: Verify per-skill sha256
      await HashVerifier.verifySkillHashes(stagingDir, remote);

      // Step 10: Atomic rename staging → release
      await _atomicRename(stagingDir, releaseDir);

      // Step 11: Update last-good pointer
      if (previousVersion != null) {
        await _updatePointer(
          ContentPaths.resolveLastGoodPointer(),
          previousVersion,
        );
      }

      // Step 12: Update current pointer
      await _updatePointer(
        ContentPaths.resolveCurrentPointer(),
        newVersion,
      );

      // Step 13: Cleanup old releases
      await _cleanupOldReleases(newVersion, previousVersion);

      return UpdateResultSuccess(newVersion, previousVersion);
    } on UpdateException catch (e) {
      // Clean up staging dir if it exists
      final stagingDirObj = Directory(stagingDir);
      if (stagingDirObj.existsSync()) {
        stagingDirObj.deleteSync(recursive: true);
      }
      // Clean up temp zip
      if (tempZipPath != null) {
        final zipFile = File(tempZipPath);
        if (zipFile.existsSync()) zipFile.deleteSync();
      }
      // Current pointer unchanged — no rollback needed unless it was updated
      return UpdateResultFailure(e, rolledBackTo: previousVersion);
    } catch (e) {
      // Clean up on unexpected errors
      final stagingDirObj = Directory(stagingDir);
      if (stagingDirObj.existsSync()) {
        stagingDirObj.deleteSync(recursive: true);
      }
      if (tempZipPath != null) {
        final zipFile = File(tempZipPath);
        if (zipFile.existsSync()) zipFile.deleteSync();
      }
      return UpdateResultFailure(
        UpdateException(UpdateExceptionKind.extractionFailed, e.toString()),
        rolledBackTo: previousVersion,
      );
    }
  }

  /// Downloads the content zip for [version] to a temp file.
  ///
  /// Returns the path to the downloaded temp file.
  ///
  /// Throws [UpdateException] with kind [UpdateExceptionKind.networkError]
  /// on HTTP failure.
  Future<String> _downloadZip(String version) async {
    final zipUrl = Uri.parse(
      '$contentReleaseUrl/legal-skills-content-$version.zip',
    );
    final sidecarUrl = Uri.parse(
      '$contentReleaseUrl/legal-skills-content-$version.zip.sha256',
    );

    final http.Response zipResponse;
    try {
      zipResponse = await _httpClient.get(zipUrl);
    } catch (e) {
      throw UpdateException(
        UpdateExceptionKind.networkError,
        'Failed to download zip: $e',
      );
    }

    if (zipResponse.statusCode != 200) {
      throw UpdateException(
        UpdateExceptionKind.networkError,
        'Zip download returned HTTP ${zipResponse.statusCode}',
      );
    }

    // Write zip to temp file
    final tempDir = Directory.systemTemp;
    final tempZip = File('${tempDir.path}/legal-skills-$version.zip');
    await tempZip.writeAsBytes(zipResponse.bodyBytes);

    // Try to download sidecar (optional — may not exist)
    try {
      final sidecarResponse = await _httpClient.get(sidecarUrl);
      if (sidecarResponse.statusCode == 200) {
        final tempSidecar = File('${tempZip.path}.sha256');
        await tempSidecar.writeAsString(sidecarResponse.body);
      }
    } catch (_) {
      // Sidecar is optional — skip if unavailable
    }

    return tempZip.path;
  }

  /// Atomically renames [from] to [to].
  ///
  /// Deletes [to] if it already exists (for re-runs), then renames.
  /// Both paths must be on the same filesystem for atomicity.
  Future<void> _atomicRename(String from, String to) async {
    final fromDir = Directory(from);
    final toDir = Directory(to);

    if (!fromDir.existsSync()) {
      throw UpdateException(
        UpdateExceptionKind.extractionFailed,
        'Staging directory does not exist: $from',
      );
    }

    // Delete target if it exists (for re-runs)
    if (toDir.existsSync()) {
      toDir.deleteSync(recursive: true);
    }

    try {
      await fromDir.rename(to);
    } catch (e) {
      throw UpdateException(
        UpdateExceptionKind.pointerUpdateFailed,
        'Atomic rename failed: $from → $to: $e',
      );
    }
  }

  /// Atomically updates a pointer file.
  ///
  /// Writes the version to a temp file, then renames it to [pointerPath].
  Future<void> _updatePointer(String pointerPath, String version) async {
    final tempPath = '$pointerPath.tmp';
    final tempFile = File(tempPath);

    try {
      await tempFile.writeAsString(version);
      await tempFile.rename(pointerPath);
    } catch (e) {
      // Clean up temp file if rename failed
      if (tempFile.existsSync()) tempFile.deleteSync();
      throw UpdateException(
        UpdateExceptionKind.pointerUpdateFailed,
        'Failed to update pointer $pointerPath: $e',
      );
    }
  }

  /// Cleans up old release directories, keeping only [currentVersion]
  /// and [lastGoodVersion] (if non-null).
  Future<void> _cleanupOldReleases(
    String currentVersion,
    String? lastGoodVersion,
  ) async {
    final skillsDir = Directory(ContentPaths.resolveSkillsDir());
    if (!skillsDir.existsSync()) return;

    final keepVersions = {currentVersion};
    if (lastGoodVersion != null) keepVersions.add(lastGoodVersion);

    for (final entry in skillsDir.listSync()) {
      if (entry is! Directory) continue;
      final name = entry.path.split('/').last;
      // Skip staging dirs and pointer files
      if (name.endsWith('-staging')) continue;
      if (!keepVersions.contains(name)) {
        // Only delete version-like directories (semver pattern)
        if (RegExp(r'^\d+\.\d+\.\d+').hasMatch(name)) {
          entry.deleteSync(recursive: true);
        }
      }
    }
  }

  /// Closes the HTTP client.
  void close() {
    _httpClient.close();
  }
}
