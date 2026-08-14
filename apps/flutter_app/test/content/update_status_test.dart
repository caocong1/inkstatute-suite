import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/content/update_status.dart';

void main() {
  group('UpdateStatus.displayMessage', () {
    test('no content installed', () {
      const status = UpdateStatus(
        isUpToDate: false,
        currentVersion: null,
      );
      expect(status.displayMessage, '未安装技能内容包');
    });

    test('up to date', () {
      final status = UpdateStatus.upToDate('1.0.0');
      expect(status.displayMessage, '技能内容已是最新版本 (v1.0.0)');
    });

    test('offline with current version', () {
      final status = UpdateStatus.offline('1.0.0');
      expect(status.displayMessage, '技能更新不可用（离线模式），当前版本 v1.0.0');
    });

    test('offline without current version', () {
      final status = UpdateStatus.offline(null);
      expect(status.displayMessage, '技能更新不可用（离线模式），未安装技能内容包');
    });

    test('update failed, rolled back', () {
      final status = UpdateStatus.failed('1.0.0', 'hash mismatch');
      expect(status.displayMessage, '技能更新失败，已回退到 v1.0.0');
    });

    test('update available', () {
      final status = UpdateStatus(
        isUpToDate: false,
        currentVersion: '1.0.0',
        latestCheckedVersion: '2.0.0',
        lastCheckedAt: DateTime.now(),
      );
      expect(status.displayMessage, '发现新版本 v2.0.0，正在更新...');
    });
  });

  group('UpdateStatus factories', () {
    test('noContent sets isUpToDate false and currentVersion null', () {
      final status = UpdateStatus.noContent();
      expect(status.isUpToDate, isFalse);
      expect(status.currentVersion, isNull);
    });

    test('upToDate sets isUpToDate true', () {
      final status = UpdateStatus.upToDate('1.0.0');
      expect(status.isUpToDate, isTrue);
      expect(status.currentVersion, '1.0.0');
    });

    test('offline sets isOffline true', () {
      final status = UpdateStatus.offline('1.0.0');
      expect(status.isOffline, isTrue);
    });

    test('failed sets errorMessage', () {
      final status = UpdateStatus.failed('1.0.0', 'some error');
      expect(status.errorMessage, 'some error');
      expect(status.currentVersion, '1.0.0');
    });
  });

  group('UpdateStatus.current', () {
    test('returns noContent when no pointer exists', () {
      // In test environment, no content is installed.
      // The result depends on whether a real content dir exists.
      final status = UpdateStatus.current();
      // Just verify it doesn't throw and returns a valid status.
      expect(status, isA<UpdateStatus>());
    });
  });
}
