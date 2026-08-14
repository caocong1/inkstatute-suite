import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/telemetry/telemetry_models.dart';

void main() {
  group('TelemetryEvent', () {
    test('creates with all fields', () {
      final event = TelemetryEvent(
        type: TelemetryEventType.healthCheck,
        timestamp: DateTime(2026, 8, 14),
        data: {'status': 'healthy'},
      );
      expect(event.type, TelemetryEventType.healthCheck);
      expect(event.data['status'], 'healthy');
    });

    test('toJson serializes correctly', () {
      final event = TelemetryEvent(
        type: TelemetryEventType.crash,
        timestamp: DateTime(2026, 8, 14, 10, 0),
        data: {'errorType': 'NullPointer'},
      );
      final json = event.toJson();
      expect(json['type'], 'crash');
      expect(json['data']['errorType'], 'NullPointer');
    });
  });

  group('TelemetryConfig', () {
    test('default config has optIn false', () {
      const config = TelemetryConfig();
      expect(config.optIn, isFalse);
    });

    test('copyWith updates fields', () {
      const config = TelemetryConfig();
      final updated = config.copyWith(optIn: true, endpointUrl: 'https://example.com');
      expect(updated.optIn, isTrue);
      expect(updated.endpointUrl, 'https://example.com');
    });
  });
}
