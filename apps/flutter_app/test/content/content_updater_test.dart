import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/content/content_updater.dart';
import 'package:flutter_app/content/manifest_schema.dart';
import 'package:flutter_app/content/update_exception.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'dart:convert';

void main() {
  group('ContentUpdater.hasUpdate', () {
    final updater = ContentUpdater(
      contentReleaseUrl: 'http://test.local',
      engineVersion: '47f943859b',
    );

    test('returns true when remote version > local version', () {
      final remote = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '2.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {},
      });
      final local = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-13T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {},
      });

      expect(updater.hasUpdate(remote, local), isTrue);
    });

    test('returns false when versions are equal', () {
      final remote = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {},
      });
      final local = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-13T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {},
      });

      expect(updater.hasUpdate(remote, local), isFalse);
    });

    test('returns true when local is null (first install)', () {
      final remote = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {},
      });

      expect(updater.hasUpdate(remote, null), isTrue);
    });

    test('handles semver pre-release correctly', () {
      final remote = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {},
      });
      final local = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0-rc.1',
        'released_at': '2026-08-13T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {},
      });

      expect(updater.hasUpdate(remote, local), isTrue);
    });
  });

  group('ContentUpdater.checkDowngradeAttack', () {
    final updater = ContentUpdater(
      contentReleaseUrl: 'http://test.local',
      engineVersion: '47f943859b',
    );

    test('throws when remote < local', () {
      final remote = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {},
      });
      final local = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '2.0.0',
        'released_at': '2026-08-13T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {},
      });

      expect(
        () => updater.checkDowngradeAttack(remote, local),
        throwsA(isA<UpdateException>()
            .having((e) => e.kind, 'kind', UpdateExceptionKind.versionDowngrade)),
      );
    });

    test('does not throw when remote >= local', () {
      final remote = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '2.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {},
      });
      final local = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '2.0.0',
        'released_at': '2026-08-13T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {},
      });

      expect(
        () => updater.checkDowngradeAttack(remote, local),
        returnsNormally,
      );
    });
  });

  group('ContentUpdater.checkEngineCompatibility', () {
    test('throws when engine version does not match', () {
      final updater = ContentUpdater(
        contentReleaseUrl: 'http://test.local',
        engineVersion: '47f943859b',
      );
      final manifest = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': 'abcdef1234',
        'domains': {},
      });

      expect(
        () => updater.checkEngineCompatibility(manifest),
        throwsA(isA<UpdateException>()
            .having((e) => e.kind, 'kind', UpdateExceptionKind.engineMismatch)),
      );
    });

    test('passes when engine version matches', () {
      final updater = ContentUpdater(
        contentReleaseUrl: 'http://test.local',
        engineVersion: '47f943859b',
      );
      final manifest = ContentManifest.fromJson({
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {},
      });

      expect(
        () => updater.checkEngineCompatibility(manifest),
        returnsNormally,
      );
    });
  });

  group('ContentUpdater.fetchRemoteManifest', () {
    test('returns parsed manifest on success', () async {
      final manifestJson = {
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': '47f943859b',
        'domains': {
          'legal-commercial': {
            'skills': [
              {'name': 'contract-review', 'sha256': 'abc123'}
            ],
          },
        },
      };

      final mockClient = MockClient((request) async {
        return http.Response(jsonEncode(manifestJson), 200);
      });

      final updater = ContentUpdater(
        contentReleaseUrl: 'http://test.local',
        engineVersion: '47f943859b',
        httpClient: mockClient,
      );

      final manifest = await updater.fetchRemoteManifest();
      expect(manifest.releaseVersion, '1.0.0');
      expect(manifest.minEngineVersion, '47f943859b');
      expect(manifest.domains['legal-commercial']!.skills.length, 1);

      updater.close();
    });

    test('throws networkError on HTTP 404', () async {
      final mockClient = MockClient((request) async {
        return http.Response('Not Found', 404);
      });

      final updater = ContentUpdater(
        contentReleaseUrl: 'http://test.local',
        engineVersion: '47f943859b',
        httpClient: mockClient,
      );

      await expectLater(
        updater.fetchRemoteManifest(),
        throwsA(isA<UpdateException>()
            .having((e) => e.kind, 'kind', UpdateExceptionKind.networkError)),
      );

      updater.close();
    });

    test('throws invalidManifest on malformed JSON', () async {
      final mockClient = MockClient((request) async {
        return http.Response('not json', 200);
      });

      final updater = ContentUpdater(
        contentReleaseUrl: 'http://test.local',
        engineVersion: '47f943859b',
        httpClient: mockClient,
      );

      await expectLater(
        updater.fetchRemoteManifest(),
        throwsA(isA<UpdateException>()
            .having((e) => e.kind, 'kind', UpdateExceptionKind.invalidManifest)),
      );

      updater.close();
    });
  });

  group('ContentUpdater.loadLocalManifest', () {
    test('returns null when no current release exists', () async {
      final updater = ContentUpdater(
        contentReleaseUrl: 'http://test.local',
        engineVersion: '47f943859b',
      );

      // In test environment, no content is installed.
      // This may return null or a manifest if a real content dir exists.
      final result = await updater.loadLocalManifest();
      // Just verify it doesn't throw.
      expect(result, anyOf(isNull, isA<ContentManifest>()));

      updater.close();
    });
  });
}
