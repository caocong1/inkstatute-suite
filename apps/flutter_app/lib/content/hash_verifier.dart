import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter_app/content/manifest_schema.dart';
import 'package:flutter_app/content/update_exception.dart';

/// SHA-256 hash verification for content packages.
///
/// Provides two-level verification:
/// 1. Zip-level: verify the downloaded zip against a known hash
/// 2. Per-skill: verify each extracted SKILL.md against the manifest hash
class HashVerifier {
  const HashVerifier._();

  /// Computes the SHA-256 hash of a file.
  ///
  /// Returns the hex-encoded hash string (64 characters).
  static String sha256File(String filePath) {
    final bytes = File(filePath).readAsBytesSync();
    return sha256.convert(bytes).toString();
  }

  /// Computes the SHA-256 hash of a file asynchronously.
  static Future<String> sha256FileAsync(String filePath) async {
    final bytes = await File(filePath).readAsBytes();
    return sha256.convert(bytes).toString();
  }

  /// Verifies that the SHA-256 of [zipPath] matches [expectedSha256].
  ///
  /// Throws [UpdateException] with kind [UpdateExceptionKind.hashMismatch]
  /// if the hash does not match.
  static void verifyZipSha256(String zipPath, String expectedSha256) {
    final actualHash = sha256File(zipPath);
    if (actualHash != expectedSha256) {
      throw UpdateException(
        UpdateExceptionKind.hashMismatch,
        'Zip sha256 mismatch: expected $expectedSha256, got $actualHash',
      );
    }
  }

  /// Verifies SHA-256 of [zipPath] using a sidecar file.
  ///
  /// The sidecar file format is: `<hash>  <filename>` (standard
  /// sha256sum output format). Only the hash portion (first token)
  /// is used.
  ///
  /// Throws [UpdateException] with kind [UpdateExceptionKind.hashMismatch]
  /// if the hash does not match.
  /// Throws [UpdateException] with kind [UpdateExceptionKind.hashMismatch]
  /// if the sidecar file is missing or malformed.
  static void verifyZipSha256FromSidecar(String zipPath, String sidecarPath) {
    final sidecarFile = File(sidecarPath);
    if (!sidecarFile.existsSync()) {
      throw UpdateException(
        UpdateExceptionKind.hashMismatch,
        'Sidecar file not found: $sidecarPath',
      );
    }

    final sidecarContent = sidecarFile.readAsStringSync().trim();
    final parts = sidecarContent.split(RegExp(r'\s+'));
    if (parts.isEmpty || parts[0].length != 64) {
      throw UpdateException(
        UpdateExceptionKind.hashMismatch,
        'Invalid sidecar format: expected 64-char hash, got "${parts[0]}"',
      );
    }

    verifyZipSha256(zipPath, parts[0]);
  }

  /// Verifies SHA-256 hashes of all skills in [manifest] against the
  /// extracted files in [releaseDir].
  ///
  /// For each skill in the manifest, computes the SHA-256 of
  /// `<releaseDir>/<domain>/<skill-name>/SKILL.md` and compares it
  /// to the manifest's `sha256` field.
  ///
  /// Throws [UpdateException] with kind [UpdateExceptionKind.hashMismatch]
  /// on the first mismatch, including the skill name in the message.
  /// Throws [UpdateException] with kind [UpdateExceptionKind.hashMismatch]
  /// if a skill file is missing.
  static Future<void> verifySkillHashes(
    String releaseDir,
    ContentManifest manifest,
  ) async {
    for (final domainEntry in manifest.domains.entries) {
      final domain = domainEntry.key;
      for (final skill in domainEntry.value.skills) {
        final skillPath = '$releaseDir/$domain/${skill.name}/SKILL.md';
        final skillFile = File(skillPath);

        if (!skillFile.existsSync()) {
          throw UpdateException(
            UpdateExceptionKind.hashMismatch,
            'Skill file missing: $domain/${skill.name}',
          );
        }

        final actualHash = await sha256FileAsync(skillPath);
        if (actualHash != skill.sha256) {
          throw UpdateException(
            UpdateExceptionKind.hashMismatch,
            'Skill sha256 mismatch: $domain/${skill.name} '
            '(expected ${skill.sha256.substring(0, 8)}..., '
            'got ${actualHash.substring(0, 8)}...)',
          );
        }
      }
    }
  }
}
