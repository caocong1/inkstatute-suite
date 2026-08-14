import 'package:flutter_test/flutter_test.dart';
import 'dart:io';
import 'package:flutter_app/offline/last_good_fallback.dart';

void main() {
  late Directory tempDir;
  late LastGoodFallback fallback;

  setUp(() async {
    tempDir = await Directory.systemTemp.createTemp('last_good_test_');
    fallback = LastGoodFallback(appDataDir: tempDir.path);
  });

  tearDown(() async {
    if (tempDir.existsSync()) {
      await tempDir.delete(recursive: true);
    }
  });

  group('LastGoodFallback', () {
    test('canStartOffline returns false when no engine/content', () async {
      expect(await fallback.canStartOffline(), isFalse);
    });

    test('canStartOffline returns true when engine and content exist', () async {
      await Directory('${tempDir.path}/engine').create();
      await Directory('${tempDir.path}/content').create();
      expect(await fallback.canStartOffline(), isTrue);
    });

    test('verifyLastGood returns false when engine missing', () async {
      await Directory('${tempDir.path}/content').create();
      expect(await fallback.verifyLastGood(), isFalse);
    });

    test('verifyLastGood returns false when content missing', () async {
      await Directory('${tempDir.path}/engine').create();
      expect(await fallback.verifyLastGood(), isFalse);
    });

    test('verifyLastGood returns true when both exist', () async {
      await Directory('${tempDir.path}/engine').create();
      await Directory('${tempDir.path}/content').create();
      expect(await fallback.verifyLastGood(), isTrue);
    });

    test('switchToLastGood returns true when resources available', () async {
      await Directory('${tempDir.path}/engine').create();
      await Directory('${tempDir.path}/content').create();
      expect(await fallback.switchToLastGood(), isTrue);
    });

    test('switchToLastGood returns false when resources missing', () async {
      expect(await fallback.switchToLastGood(), isFalse);
    });

    test('lastGoodEnginePath returns correct path', () {
      expect(fallback.lastGoodEnginePath, contains('engine'));
    });

    test('lastGoodContentPath returns correct path', () {
      expect(fallback.lastGoodContentPath, contains('content'));
    });

    test('newTasksRequireNetwork is true', () {
      expect(LastGoodFallback.newTasksRequireNetwork, isTrue);
    });
  });
}
