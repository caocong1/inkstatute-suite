import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/telemetry/engine_health_probe.dart';
import 'package:flutter_app/telemetry/telemetry_collector.dart';

void main() {
  group('EngineHealthProbe', () {
    test('check returns healthy by default', () async {
      final probe = EngineHealthProbe();
      final status = await probe.check();
      expect(status, HealthStatus.healthy);
    });

    test('check records health check event when collector provided', () async {
      final collector = TelemetryCollector();
      collector.enableOptIn();
      final probe = EngineHealthProbe(collector: collector);
      await probe.check();
      expect(collector.pendingEvents.length, 1);
    });

    test('check does not record when collector is null', () async {
      final probe = EngineHealthProbe();
      await probe.check();
      // No exception, no crash
    });

    test('check does not record when optIn disabled', () async {
      final collector = TelemetryCollector();
      final probe = EngineHealthProbe(collector: collector);
      await probe.check();
      expect(collector.pendingEvents, isEmpty);
    });
  });

  group('HealthStatus', () {
    test('statusMessage returns correct message for healthy', () {
      expect(EngineHealthProbe.statusMessage(HealthStatus.healthy), '引擎运行正常');
    });

    test('statusMessage returns correct message for degraded', () {
      expect(EngineHealthProbe.statusMessage(HealthStatus.degraded), '引擎响应缓慢');
    });

    test('statusMessage returns correct message for offline', () {
      expect(EngineHealthProbe.statusMessage(HealthStatus.offline), '引擎未启动或无响应');
    });
  });
}
