import 'package:flutter_test/flutter_test.dart';
import 'dart:io';
import 'package:flutter_app/security/engine_env.dart';

void main() {
  group('Zero-plaintext grep assertion (DSH-05)', () {
    test('no API key patterns in source files', () async {
      final srcDir = Directory('lib');
      final violations = <String>[];

      await for (final entity in srcDir.list(recursive: true)) {
        if (entity is File && entity.path.endsWith('.dart')) {
          final content = await entity.readAsString();
          final matches = EngineEnv.scanForKeyPatterns(content);
          if (matches.isNotEmpty) {
            violations.add('${entity.path}: ${matches.length} matches');
          }
        }
      }

      expect(violations, isEmpty,
          reason: 'No API key patterns should be in source files: $violations');
    });

    test('no API key patterns in test files', () async {
      final testDir = Directory('test');
      final violations = <String>[];

      await for (final entity in testDir.list(recursive: true)) {
        if (entity is File && entity.path.endsWith('.dart')) {
          final content = await entity.readAsString();
          final matches = EngineEnv.scanForKeyPatterns(content);
          if (matches.isNotEmpty) {
            violations.add('${entity.path}: ${matches.length} matches');
          }
        }
      }

      expect(violations, isEmpty,
          reason: 'No API key patterns should be in test files: $violations');
    });

    test('no API key patterns in config files', () async {
      final violations = <String>[];
      final configFiles = [
        'pubspec.yaml',
        'pubspec.lock',
        'analysis_options.yaml',
      ];

      for (final path in configFiles) {
        final file = File(path);
        if (await file.exists()) {
          final content = await file.readAsString();
          final matches = EngineEnv.scanForKeyPatterns(content);
          if (matches.isNotEmpty) {
            violations.add('$path: ${matches.length} matches');
          }
        }
      }

      expect(violations, isEmpty,
          reason: 'No API key patterns should be in config files: $violations');
    });

    test('no API key patterns in planning docs', () async {
      final planningDir = Directory('.planning');
      if (!planningDir.existsSync()) return;

      final violations = <String>[];

      await for (final entity in planningDir.list(recursive: true)) {
        if (entity is File && entity.path.endsWith('.md')) {
          final content = await entity.readAsString();
          final matches = EngineEnv.scanForKeyPatterns(content);
          if (matches.isNotEmpty) {
            violations.add('${entity.path}: ${matches.length} matches');
          }
        }
      }

      expect(violations, isEmpty,
          reason: 'No API key patterns should be in planning docs: $violations');
    });
  });
}
