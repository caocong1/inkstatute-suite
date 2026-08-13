/// Health probe for the DSH engine subprocess.
///
/// [EngineHealthProbe.check] sends an ACP `initialize` request via
/// [AcpClient] and asserts that the response has `protocolVersion == 1`
/// and a non-empty agent name. Returns [HealthResult.healthy] or
/// [HealthResult.unhealthy] with a reason string.
library;

import 'dart:async';

import 'package:acp_client/acp_client.dart';

/// Result of an engine health probe.
sealed class HealthResult {
  const HealthResult();
}

/// The engine is healthy: initialize handshake succeeded with
/// `protocolVersion == 1`.
final class Healthy extends HealthResult {
  const Healthy();
}

/// The engine is unhealthy: the initialize handshake failed, timed out,
/// or returned an unexpected protocol version.
final class Unhealthy extends HealthResult {
  /// Creates an unhealthy result with a human-readable reason.
  const Unhealthy(this.reason);

  /// Why the engine is unhealthy.
  final String reason;
}

/// Health probe that sends an ACP `initialize` handshake and asserts
/// `protocolVersion == 1`.
///
/// The probe delegates to [AcpClient.initialize] and checks:
/// 1. `result.protocolVersion == 1`
/// 2. `result.agentInfo.name` is non-empty
///
/// If the handshake does not complete within [timeout], the probe
/// returns [Unhealthy] with a timeout reason.
class EngineHealthProbe {
  /// Creates a health probe with the given [timeout].
  const EngineHealthProbe({this.timeout = const Duration(seconds: 30)});

  /// Timeout for the initialize handshake.
  final Duration timeout;

  /// Sends an `initialize` request via [client] and checks the response.
  ///
  /// Returns [Healthy] if `protocolVersion == 1` and the agent name is
  /// non-empty. Returns [Unhealthy] with a reason string otherwise.
  Future<HealthResult> check(AcpClient client) async {
    try {
      final result = await client.initialize().timeout(timeout);
      if (result.protocolVersion != 1) {
        return Unhealthy(
          'protocol version mismatch: expected 1, got ${result.protocolVersion}',
        );
      }
      if (result.agentInfo.name.isEmpty) {
        return const Unhealthy('agent info name is empty');
      }
      return const Healthy();
    } on TimeoutException {
      return Unhealthy(
        'initialize handshake timed out after ${timeout.inSeconds}s',
      );
    } on AcpRpcException catch (e) {
      return Unhealthy('initialize RPC error: ${e.code} ${e.message}');
    } catch (e) {
      return Unhealthy('initialize failed: $e');
    }
  }
}
