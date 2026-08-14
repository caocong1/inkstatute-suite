import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/content/hash_verifier.dart';
import 'package:flutter_app/content/manifest_schema.dart';
import 'package:flutter_app/content/update_exception.dart';
import 'dart:io';

void main() {
  late Directory tempDir;

  setUp(() {
    tempDir = Directory.systemTemp.createTempSync('hash_verifier_test');
  });

  tearDown(() {
    if (tempDir.existsSync()) tempDir.deleteSync(recursive: true);
  });

  group('HashVerifier.sha256File', () {
    test('returns correct hash for known content', () {
      final filePath = '${tempDir.path}/test.txt';
      File(filePath).writeAsStringSync('hello');

      // sha256("hello") = 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
      final hash = HashVerifier.sha256File(filePath);
      expect(hash, '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824');
    });

    test('returns 64-character hex string', () {
      final filePath = '${tempDir.path}/test2.txt';
      File(filePath).writeAsStringSync('some content here');

      final hash = HashVerifier.sha256File(filePath);
      expect(hash.length, 64);
      expect(RegExp(r'^[0-9a-f]{64}$').hasMatch(hash), isTrue);
    });
  });

  group('HashVerifier.verifyZipSha256', () {
    test('passes when hash matches', () {
      final filePath = '${tempDir.path}/test.txt';
      File(filePath).writeAsStringSync('hello');
      final expectedHash = HashVerifier.sha256File(filePath);

      // Should not throw
      HashVerifier.verifyZipSha256(filePath, expectedHash);
    });

    test('throws hashMismatch when hash does not match', () {
      final filePath = '${tempDir.path}/test.txt';
      File(filePath).writeAsStringSync('hello');

      expect(
        () => HashVerifier.verifyZipSha256(filePath, 'wronghash'),
        throwsA(isA<UpdateException>()
            .having((e) => e.kind, 'kind', UpdateExceptionKind.hashMismatch)),
      );
    });
  });

  group('HashVerifier.verifyZipSha256FromSidecar', () {
    test('parses sidecar format and verifies correctly', () {
      final zipPath = '${tempDir.path}/test.zip';
      File(zipPath).writeAsBytesSync([1, 2, 3, 4, 5]);
      final actualHash = HashVerifier.sha256File(zipPath);

      final sidecarPath = '${tempDir.path}/test.zip.sha256';
      File(sidecarPath).writeAsStringSync('$actualHash  test.zip\n');

      // Should not throw
      HashVerifier.verifyZipSha256FromSidecar(zipPath, sidecarPath);
    });

    test('throws when sidecar file is missing', () {
      final zipPath = '${tempDir.path}/test.zip';
      File(zipPath).writeAsBytesSync([1, 2, 3]);

      expect(
        () => HashVerifier.verifyZipSha256FromSidecar(
            zipPath, '${tempDir.path}/missing.sha256'),
        throwsA(isA<UpdateException>()
            .having((e) => e.kind, 'kind', UpdateExceptionKind.hashMismatch)),
      );
    });

    test('throws when sidecar hash does not match', () {
      final zipPath = '${tempDir.path}/test.zip';
      File(zipPath).writeAsBytesSync([1, 2, 3]);

      final sidecarPath = '${tempDir.path}/test.zip.sha256';
      File(sidecarPath).writeAsStringSync(
          '0000000000000000000000000000000000000000000000000000000000000000  test.zip\n');

      expect(
        () => HashVerifier.verifyZipSha256FromSidecar(zipPath, sidecarPath),
        throwsA(isA<UpdateException>()
            .having((e) => e.kind, 'kind', UpdateExceptionKind.hashMismatch)),
      );
    });
  });

  group('HashVerifier.verifySkillHashes', () {
    test('passes when all skill hashes match manifest', () async {
      // Create skill files
      final releaseDir = '${tempDir.path}/release';
      final skill1Path = '$releaseDir/legal-commercial/contract-review/SKILL.md';
      final skill2Path = '$releaseDir/legal-litigation/cold-start/SKILL.md';
      await Directory('$releaseDir/legal-commercial/contract-review')
          .create(recursive: true);
      await Directory('$releaseDir/legal-litigation/cold-start')
          .create(recursive: true);
      File(skill1Path).writeAsStringSync('skill 1 content');
      File(skill2Path).writeAsStringSync('skill 2 content');

      final hash1 = HashVerifier.sha256File(skill1Path);
      final hash2 = HashVerifier.sha256File(skill2Path);

      final manifest = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {
          'legal-commercial': {
            'skills': [
              {'name': 'contract-review', 'sha256': hash1},
            ],
          },
          'legal-litigation': {
            'skills': [
              {'name': 'cold-start', 'sha256': hash2},
            ],
          },
        },
      });

      // Should not throw
      await HashVerifier.verifySkillHashes(releaseDir, manifest);
    });

    test('throws on first hash mismatch', () async {
      final releaseDir = '${tempDir.path}/release';
      final skillPath = '$releaseDir/legal-commercial/contract-review/SKILL.md';
      await Directory('$releaseDir/legal-commercial/contract-review')
          .create(recursive: true);
      File(skillPath).writeAsStringSync('actual content');

      final manifest = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {
          'legal-commercial': {
            'skills': [
              {'name': 'contract-review', 'sha256': 'wronghash'},
            ],
          },
        },
      });

      await expectLater(
        HashVerifier.verifySkillHashes(releaseDir, manifest),
        throwsA(isA<UpdateException>()
            .having((e) => e.kind, 'kind', UpdateExceptionKind.hashMismatch)),
      );
    });

    test('throws when skill file is missing', () async {
      final releaseDir = '${tempDir.path}/release';
      // Don't create the skill file

      final manifest = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {
          'legal-commercial': {
            'skills': [
              {'name': 'missing-skill', 'sha256': 'anyhash'},
            ],
          },
        },
      });

      await expectLater(
        HashVerifier.verifySkillHashes(releaseDir, manifest),
        throwsA(isA<UpdateException>()
            .having((e) => e.kind, 'kind', UpdateExceptionKind.hashMismatch)),
      );
    });
  });
}
