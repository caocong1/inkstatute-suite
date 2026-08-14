import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/security/engine_env.dart';

void main() {
  const engineEnv = EngineEnv();

  group('EngineEnv.buildEnv', () {
    test('injects API key as DEEPSEEK_API_KEY', () {
      final env = engineEnv.buildEnv(apiKey: 'sk-test-key');
      expect(env[EngineEnv.apiKeyEnvVar], 'sk-test-key');
    });

    test('injects base URL when provided', () {
      final env = engineEnv.buildEnv(
        apiKey: 'sk-test',
        baseUrl: 'https://api.deepseek.com',
      );
      expect(env[EngineEnv.baseUrlEnvVar], 'https://api.deepseek.com');
    });

    test('does not inject base URL when not provided', () {
      final env = engineEnv.buildEnv(apiKey: 'sk-test');
      expect(env.containsKey(EngineEnv.baseUrlEnvVar), isFalse);
    });

    test('preserves base environment variables', () {
      final env = engineEnv.buildEnv(
        apiKey: 'sk-test',
        base: {'PATH': '/usr/bin', 'HOME': '/home/user'},
      );
      expect(env['PATH'], '/usr/bin');
      expect(env['HOME'], '/home/user');
      expect(env[EngineEnv.apiKeyEnvVar], 'sk-test');
    });
  });

  group('EngineEnv.zeroPlaintextAssert', () {
    test('returns true when output does not contain key', () {
      expect(engineEnv.zeroPlaintextAssert('some log output', 'test-key-value'), isTrue);
    });

    test('returns false when output contains key', () {
      expect(engineEnv.zeroPlaintextAssert('error: test-key-value leaked', 'test-key-value'),
          isFalse);
    });

    test('returns true when key is empty', () {
      expect(engineEnv.zeroPlaintextAssert('some output', ''), isTrue);
    });
  });

  group('EngineEnv.scanForKeyPatterns', () {
    test('finds API key patterns in text', () {
      // Use a pattern that matches the sk- format with 20+ chars
      final testKey = 'sk-${'a' * 30}';
      final matches = EngineEnv.scanForKeyPatterns('config: $testKey');
      expect(matches.length, 1);
      expect(matches.first, startsWith('sk-'));
    });

    test('finds multiple patterns', () {
      final key1 = 'sk-${'a' * 30}';
      final key2 = 'sk-${'b' * 30}';
      final matches = EngineEnv.scanForKeyPatterns('key1: $key1 key2: $key2');
      expect(matches.length, 2);
    });

    test('returns empty list for clean text', () {
      final matches = EngineEnv.scanForKeyPatterns('no keys here');
      expect(matches, isEmpty);
    });

    test('does not match short strings', () {
      final matches = EngineEnv.scanForKeyPatterns('sk-short');
      expect(matches, isEmpty);
    });
  });
}
