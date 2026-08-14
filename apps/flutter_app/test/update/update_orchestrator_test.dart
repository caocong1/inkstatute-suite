import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/update/update_models.dart';
import 'package:flutter_app/update/update_orchestrator.dart';

void main() {
  group('UpdateLayer', () {
    test('has three layers', () {
      expect(UpdateLayer.values.length, 3);
      expect(UpdateLayer.values, contains(UpdateLayer.app));
      expect(UpdateLayer.values, contains(UpdateLayer.engine));
      expect(UpdateLayer.values, contains(UpdateLayer.content));
    });
  });

  group('UpdateStatus', () {
    test('creates with all fields', () {
      const status = UpdateStatus(
        layer: UpdateLayer.app,
        updateAvailable: true,
        currentVersion: '1.0.0',
        latestVersion: '1.1.0',
        manifestUrl: 'https://example.com/manifest.json',
      );
      expect(status.layer, UpdateLayer.app);
      expect(status.updateAvailable, isTrue);
      expect(status.currentVersion, '1.0.0');
      expect(status.latestVersion, '1.1.0');
    });
  });

  group('UpdateResult', () {
    test('UpdateSuccess contains layer and version', () {
      const result = UpdateSuccess(UpdateLayer.app, '1.1.0');
      expect(result.layer, UpdateLayer.app);
      expect(result.newVersion, '1.1.0');
    });

    test('UpdateFailure contains layer and error', () {
      const result = UpdateFailure(UpdateLayer.engine, 'network error');
      expect(result.layer, UpdateLayer.engine);
      expect(result.error, 'network error');
    });

    test('UpdateSkipped contains layer and reason', () {
      const result = UpdateSkipped(UpdateLayer.engine, 'disabled');
      expect(result.layer, UpdateLayer.engine);
      expect(result.reason, 'disabled');
    });
  });

  group('ManifestInfo', () {
    test('fromJson parses correctly', () {
      final json = {
        'version': '1.2.0',
        'sha256': 'abc123',
        'downloadUrl': 'https://example.com/download',
        'builtAt': '2026-08-14',
      };
      final info = ManifestInfo.fromJson(json);
      expect(info.version, '1.2.0');
      expect(info.sha256, 'abc123');
      expect(info.downloadUrl, 'https://example.com/download');
      expect(info.builtAt, '2026-08-14');
    });

    test('fromJson uses defaults for missing fields', () {
      final info = ManifestInfo.fromJson({});
      expect(info.version, isEmpty);
      expect(info.sha256, isEmpty);
      expect(info.downloadUrl, isEmpty);
      expect(info.builtAt, isNull);
    });
  });

  group('UpdateOrchestrator', () {
    late UpdateOrchestrator orchestrator;

    setUp(() {
      orchestrator = UpdateOrchestrator(
        currentVersions: {
          UpdateLayer.app: '1.0.0',
          UpdateLayer.engine: '0.5.0',
          UpdateLayer.content: '2.0.0',
        },
      );
    });

    test('currentVersion returns stored version', () {
      expect(orchestrator.currentVersion(UpdateLayer.app), '1.0.0');
      expect(orchestrator.currentVersion(UpdateLayer.engine), '0.5.0');
      expect(orchestrator.currentVersion(UpdateLayer.content), '2.0.0');
    });

    test('currentVersion returns null for unset layer', () {
      final fresh = UpdateOrchestrator();
      expect(fresh.currentVersion(UpdateLayer.app), isNull);
    });

    test('setCurrentVersion updates version', () {
      orchestrator.setCurrentVersion(UpdateLayer.app, '2.0.0');
      expect(orchestrator.currentVersion(UpdateLayer.app), '2.0.0');
    });

    test('isEngineAutoUpdateEnabled is always false', () {
      expect(UpdateOrchestrator.isEngineAutoUpdateEnabled, isFalse);
    });

    test('shouldAutoUpdateEngine is always false', () {
      expect(orchestrator.shouldAutoUpdateEngine, isFalse);
    });

    test('shouldAutoUpdateContent is true', () {
      expect(orchestrator.shouldAutoUpdateContent, isTrue);
    });

    test('checkUpdates returns status for all three layers', () async {
      final statuses = await orchestrator.checkUpdates();
      expect(statuses.length, 3);
      expect(statuses.any((s) => s.layer == UpdateLayer.app), isTrue);
      expect(statuses.any((s) => s.layer == UpdateLayer.engine), isTrue);
      expect(statuses.any((s) => s.layer == UpdateLayer.content), isTrue);
    });

    test('updateEngine returns UpdateSkipped', () async {
      final result = await orchestrator.updateEngine();
      expect(result, isA<UpdateSkipped>());
      expect((result as UpdateSkipped).layer, UpdateLayer.engine);
      expect(result.reason, contains('disabled'));
    });

    test('updateApp returns UpdateSuccess', () async {
      final result = await orchestrator.updateApp();
      expect(result, isA<UpdateSuccess>());
      expect((result as UpdateSuccess).layer, UpdateLayer.app);
    });

    test('updateContent returns UpdateSuccess', () async {
      final result = await orchestrator.updateContent();
      expect(result, isA<UpdateSuccess>());
      expect((result as UpdateSuccess).layer, UpdateLayer.content);
    });

    test('engine update is never auto-enabled', () {
      // This is the critical safety assertion:
      // Engine auto-update must NEVER be enabled.
      expect(UpdateOrchestrator.isEngineAutoUpdateEnabled, isFalse,
          reason: 'Engine auto-update must be disabled per DSH-03');
    });
  });
}
