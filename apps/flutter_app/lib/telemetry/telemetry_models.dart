/// Telemetry models — opt-in, desensitized events (PKG-03).
///
/// No API keys, no customer full text, no raw payloads in events.
library;

/// Type of telemetry event.
enum TelemetryEventType {
  /// Engine health check result.
  healthCheck,

  /// App crash report.
  crash,

  /// Usage statistics (e.g., session count, feature usage).
  usage,

  /// Error report (non-crash).
  error,
}

/// A desensitized telemetry event.
class TelemetryEvent {
  /// Creates a telemetry event.
  const TelemetryEvent({
    required this.type,
    required this.timestamp,
    required this.data,
  });

  /// Event type.
  final TelemetryEventType type;

  /// Event timestamp.
  final DateTime timestamp;

  /// Desensitized event data (no keys, no customer text, no raw payloads).
  final Map<String, dynamic> data;

  /// Converts to JSON map.
  Map<String, dynamic> toJson() => {
        'type': type.name,
        'timestamp': timestamp.toIso8601String(),
        'data': data,
      };
}

/// Telemetry configuration.
class TelemetryConfig {
  /// Creates telemetry config.
  const TelemetryConfig({
    this.optIn = false,
    this.endpointUrl,
    this.maxBatchSize = 10,
    this.flushIntervalSeconds = 60,
  });

  /// Whether telemetry is enabled (opt-in, default: false).
  final bool optIn;

  /// Endpoint URL for sending telemetry.
  final String? endpointUrl;

  /// Maximum events per batch.
  final int maxBatchSize;

  /// Flush interval in seconds.
  final int flushIntervalSeconds;

  /// Returns a copy with updated fields.
  TelemetryConfig copyWith({
    bool? optIn,
    String? endpointUrl,
    int? maxBatchSize,
    int? flushIntervalSeconds,
  }) {
    return TelemetryConfig(
      optIn: optIn ?? this.optIn,
      endpointUrl: endpointUrl ?? this.endpointUrl,
      maxBatchSize: maxBatchSize ?? this.maxBatchSize,
      flushIntervalSeconds: flushIntervalSeconds ?? this.flushIntervalSeconds,
    );
  }
}
