import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/content/content_updater.dart';
import 'package:flutter_app/content/update_exception.dart';
import 'package:flutter_app/content/update_status.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'dart:convert';

void main() {
  group('ContentUpdater.checkAndUpdateOfflineSafe', () {
    test('returns offline failure when network fails and current exists',
        () async {
      // This test verifies the offline-safe wrapper catches network errors.
      // Since we can't control ContentPaths in unit tests (it uses
      // Platform.environment), we test the wrapper logic by mocking
      // the HTTP client to return 404.
      final mockClient = MockClient((request) async {
        return http.Response('Not Found', 404);
      });

      final updater = ContentUpdater(
        contentReleaseUrl: 'http://test.local',
        engineVersion: '47f943859b',
        httpClient: mockClient,
      );

      // checkAndUpdateOfflineSafe should catch the network error
      // and return a failure result (not throw).
      final result = await updater.checkAndUpdateOfflineSafe();

      expect(result, isA<UpdateResultFailure>());
      final failure = result as UpdateResultFailure;
      expect(failure.isOffline, isTrue);
      expect(failure.exception.kind, UpdateExceptionKind.networkError);

      updater.close();
    });

    test('returns failure for non-network errors', () async {
      // Mock returns a manifest with wrong engine version.
      final manifest = {
        'schema_version': '1.0.0',
        'release_version': '1.0.0',
        'released_at': '2026-08-14T00:00:00Z',
        'min_engine_version': 'wrongengine',
        'domains': {},
      };

      final mockClient = MockClient((request) async {
        return http.Response(jsonEncode(manifest), 200);
      });

      final updater = ContentUpdater(
        contentReleaseUrl: 'http://test.local',
        engineVersion: '47f943859b',
        httpClient: mockClient,
      );

      final result = await updater.checkAndUpdateOfflineSafe();

      expect(result, isA<UpdateResultFailure>());
      final failure = result as UpdateResultFailure;
      expect(failure.isOffline, isFalse);
      expect(failure.exception.kind, UpdateExceptionKind.engineMismatch);

      updater.close();
    });
  });

  group('ContentUpdater.currentStatus', () {
    test('returns a valid UpdateStatus', () {
      final updater = ContentUpdater(
        contentReleaseUrl: 'http://test.local',
        engineVersion: '47f943859b',
      );

      final status = updater.currentStatus();
      expect(status, isA<UpdateStatus>());

      updater.close();
    });
  });
}
