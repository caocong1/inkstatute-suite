import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/telemetry/telemetry_collector.dart';
import 'package:flutter_app/telemetry/telemetry_models.dart';

void main() {
  group('TelemetryCollector', () {
    test('optIn is false by default', () {
      final collector = TelemetryCollector();
      expect(collector.optIn, isFalse);
    });

    test('enableOptIn sets optIn to true', () {
      final collector = TelemetryCollector();
      collector.enableOptIn();
      expect(collector.optIn, isTrue);
    });

    test('disableOptIn sets optIn to false', () {
      final collector = TelemetryCollector();
      collector.enableOptIn();
      collector.disableOptIn();
      expect(collector.optIn, isFalse);
    });

    test('recordEvent does nothing when optIn disabled', () {
      final collector = TelemetryCollector();
      collector.recordEvent(TelemetryEvent(
        type: TelemetryEventType.usage,
        timestamp: DateTime.now(),
        data: {},
      ));
      expect(collector.pendingEvents, isEmpty);
    });

    test('recordEvent stores event when optIn enabled', () {
      final collector = TelemetryCollector();
      collector.enableOptIn();
      collector.recordEvent(TelemetryEvent(
        type: TelemetryEventType.usage,
        timestamp: DateTime.now(),
        data: {'feature': 'chat'},
      ));
      expect(collector.pendingEvents.length, 1);
    });

    test('recordHealthCheck stores health check event', () {
      final collector = TelemetryCollector();
      collector.enableOptIn();
      collector.recordHealthCheck('healthy');
      expect(collector.pendingEvents.length, 1);
      expect(collector.pendingEvents.first.type, TelemetryEventType.healthCheck);
    });

    test('recordCrash stores desensitized crash event', () {
      final collector = TelemetryCollector();
      collector.enableOptIn();
      final testKey = 'sk-${'a' * 30}';
      collector.recordCrash('NullPointer', 'error with $testKey');
      expect(collector.pendingEvents.length, 1);
      final data = collector.pendingEvents.first.data;
      expect(data['errorType'], 'NullPointer');
      expect(data['errorMessage'], contains('[REDACTED_KEY]'));
    });

    test('recordUsage stores usage event', () {
      final collector = TelemetryCollector();
      collector.enableOptIn();
      collector.recordUsage('export_docx');
      expect(collector.pendingEvents.length, 1);
      expect(collector.pendingEvents.first.data['feature'], 'export_docx');
    });

    test('flush clears pending events and returns count', () async {
      final collector = TelemetryCollector();
      collector.enableOptIn();
      collector.recordUsage('feature1');
      collector.recordUsage('feature2');
      final count = await collector.flush();
      expect(count, 2);
      expect(collector.pendingEvents, isEmpty);
    });

    test('flush returns 0 when no pending events', () async {
      final collector = TelemetryCollector();
      final count = await collector.flush();
      expect(count, 0);
    });

    test('clear removes all pending events', () {
      final collector = TelemetryCollector();
      collector.enableOptIn();
      collector.recordUsage('feature1');
      collector.recordUsage('feature2');
      collector.clear();
      expect(collector.pendingEvents, isEmpty);
    });
  });

  group('TelemetryCollector.desensitize', () {
    test('removes API key patterns', () {
      final collector = TelemetryCollector();
      final testKey = 'sk-${'a' * 30}';
      final result = collector.desensitize('error: $testKey leaked');
      expect(result, contains('[REDACTED_KEY]'));
    });

    test('removes email addresses', () {
      final collector = TelemetryCollector();
      final result = collector.desensitize('contact: user@example.com');
      expect(result, contains('[REDACTED_EMAIL]'));
      expect(result, isNot(contains('user@example.com')));
    });

    test('removes Chinese phone numbers', () {
      final collector = TelemetryCollector();
      final result = collector.desensitize('call 13812345678 for help');
      expect(result, contains('[REDACTED_PHONE]'));
      expect(result, isNot(contains('13812345678')));
    });

    test('leaves normal text unchanged', () {
      final collector = TelemetryCollector();
      final result = collector.desensitize('engine started successfully');
      expect(result, 'engine started successfully');
    });
  });
}
