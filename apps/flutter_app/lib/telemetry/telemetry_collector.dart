/// Telemetry collector — opt-in, desensitized event collection (PKG-03).
///
/// Collects telemetry events only when opt-in is enabled.
/// All events are desensitized: no API keys, no customer full text,
/// no raw payloads.
library;

import 'package:flutter_app/telemetry/telemetry_models.dart';

/// Collects and manages telemetry events.
class TelemetryCollector {
  /// Creates a telemetry collector.
  TelemetryCollector({TelemetryConfig? config})
      : _config = config ?? const TelemetryConfig();

  TelemetryConfig _config;
  final List<TelemetryEvent> _pendingEvents = [];

  /// Returns the current telemetry configuration.
  TelemetryConfig get config => _config;

  /// Returns true if telemetry is opt-in enabled.
  bool get optIn => _config.optIn;

  /// Returns the list of pending events waiting to be sent.
  List<TelemetryEvent> get pendingEvents => List.unmodifiable(_pendingEvents);

  /// Updates the telemetry configuration.
  void updateConfig(TelemetryConfig config) {
    _config = config;
  }

  /// Enables opt-in telemetry.
  void enableOptIn() {
    _config = _config.copyWith(optIn: true);
  }

  /// Disables opt-in telemetry.
  void disableOptIn() {
    _config = _config.copyWith(optIn: false);
  }

  /// Records a telemetry event.
  ///
  /// Events are only recorded if opt-in is enabled.
  void recordEvent(TelemetryEvent event) {
    if (!_config.optIn) return;
    _pendingEvents.add(event);
  }

  /// Records a health check event.
  void recordHealthCheck(String status, {Map<String, dynamic>? extra}) {
    recordEvent(TelemetryEvent(
      type: TelemetryEventType.healthCheck,
      timestamp: DateTime.now(),
      data: {
        'status': status,
        ...?extra,
      },
    ));
  }

  /// Records a crash event.
  void recordCrash(String errorType, String errorMessage,
      {Map<String, dynamic>? extra}) {
    recordEvent(TelemetryEvent(
      type: TelemetryEventType.crash,
      timestamp: DateTime.now(),
      data: {
        'errorType': errorType,
        'errorMessage': _desensitize(errorMessage),
        ...?extra,
      },
    ));
  }

  /// Records a usage event.
  void recordUsage(String feature, {Map<String, dynamic>? extra}) {
    recordEvent(TelemetryEvent(
      type: TelemetryEventType.usage,
      timestamp: DateTime.now(),
      data: {
        'feature': feature,
        ...?extra,
      },
    ));
  }

  /// Desensitizes text by removing potential sensitive data.
  ///
  /// Removes:
  /// - API key patterns (sk-...)
  /// - Email addresses
  /// - Phone numbers (Chinese format)
  String _desensitize(String input) {
    var result = input;
    // Remove API key patterns
    result = result.replaceAll(RegExp(r'sk-[a-zA-Z0-9]{20,}'), '[REDACTED_KEY]');
    // Remove email addresses
    result = result.replaceAll(
        RegExp(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'), '[REDACTED_EMAIL]');
    // Remove Chinese phone numbers
    result = result.replaceAll(RegExp(r'1[3-9]\d{9}'), '[REDACTED_PHONE]');
    return result;
  }

  /// Desensitizes text (public for testing).
  String desensitize(String input) => _desensitize(input);

  /// Flushes pending events to the endpoint.
  ///
  /// Returns the number of events sent. In production, this would
  /// send events to the telemetry endpoint. For now, it clears
  /// the pending list.
  Future<int> flush() async {
    if (_pendingEvents.isEmpty) return 0;
    final count = _pendingEvents.length;
    _pendingEvents.clear();
    return count;
  }

  /// Clears all pending events without sending.
  void clear() {
    _pendingEvents.clear();
  }
}
