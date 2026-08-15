/// Engine environment injection (DSH-05).
///
/// Builds environment variables for the DSH engine process.
/// The API key is injected as an environment variable and never
/// written to files, logs, or telemetry.
library;

import 'package:flutter_app/wizard/llm_provider.dart';

/// Builds environment variables for the DSH engine process.
class EngineEnv {
  /// Creates an engine environment builder.
  const EngineEnv();

  /// Builds the environment map for the engine process.
  ///
  /// [apiKey] is injected using the provider's [LlmProvider.apiKeyEnvVar].
  /// [baseUrl] is optionally injected using the provider's
  /// [LlmProvider.baseUrlEnvVar] (if the provider supports one).
  /// Returns a map suitable for `Process.start(environment: ...)`.
  Map<String, String> buildEnv({
    required String apiKey,
    required LlmProvider provider,
    String? baseUrl,
    Map<String, String>? base,
  }) {
    final env = <String, String>{...?base};
    env[provider.apiKeyEnvVar] = apiKey;
    if (provider.baseUrlEnvVar != null && baseUrl != null) {
      env[provider.baseUrlEnvVar!] = baseUrl;
    }
    return env;
  }

  /// Asserts that the given output contains no plaintext API key.
  ///
  /// Returns true if the output is clean (no API key found).
  /// Returns false if the output contains the API key.
  bool zeroPlaintextAssert(String output, String apiKey) {
    if (apiKey.isEmpty) return true;
    return !output.contains(apiKey);
  }

  /// Scans text for potential API key patterns.
  ///
  /// Returns a list of matches found. An empty list means clean.
  static List<String> scanForKeyPatterns(String text) {
    final pattern = RegExp(r'sk-[a-zA-Z0-9]{20,}');
    return pattern.allMatches(text).map((m) => m.group(0)!).toList();
  }
}
