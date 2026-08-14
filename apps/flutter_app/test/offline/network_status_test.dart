import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/offline/network_status.dart';

void main() {
  group('NetworkStatusDetector', () {
    test('default status is online', () {
      final detector = NetworkStatusDetector();
      expect(detector.status, NetworkStatus.online);
      expect(detector.isOnline, isTrue);
      expect(detector.isOffline, isFalse);
    });

    test('setStatus updates status', () {
      final detector = NetworkStatusDetector();
      detector.setStatus(NetworkStatus.offline);
      expect(detector.status, NetworkStatus.offline);
      expect(detector.isOffline, isTrue);
      expect(detector.isOnline, isFalse);
    });

    test('initial status can be set', () {
      final detector = NetworkStatusDetector(initialStatus: NetworkStatus.offline);
      expect(detector.status, NetworkStatus.offline);
    });

    test('check returns current status', () async {
      final detector = NetworkStatusDetector();
      final status = await detector.check();
      expect(status, NetworkStatus.online);
    });

    test('statusMessage returns correct message', () {
      expect(NetworkStatusDetector.statusMessage(NetworkStatus.online), '网络正常');
      expect(NetworkStatusDetector.statusMessage(NetworkStatus.offline), '当前处于离线状态');
    });
  });
}
