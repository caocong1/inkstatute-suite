// Tests for session/prompt: text block prompt, single in-flight rejection,
// stopReason assertion, concurrent prompts on different sessions.
import 'dart:io';

import 'package:acp_client/acp_client.dart';
import 'package:flutter_test/flutter_test.dart';

/// Resolves the path to the mock ACP server fixture.
String _mockServerPath() {
  final local = 'test/fixtures/mock_acp_server.dart';
  if (File(local).existsSync()) return local;
  return 'packages/acp_client/test/fixtures/mock_acp_server.dart';
}

/// Spawns the mock ACP server as a subprocess.
Future<Process> _spawnMockServer() {
  return Process.start(
    'dart',
    ['run', _mockServerPath()],
    workingDirectory: Directory.current.path,
  );
}

void main() {
  group('AcpClient.prompt', () {
    test('text prompt receives agent_message_chunk and returns end_turn',
        () async {
      final process = await _spawnMockServer();
      final client = AcpClient(
        AcpTransport(input: process.stdout, output: process.stdin),
      );

      // Collect text chunks from onUpdate stream.
      final chunks = <String>[];
      final sub = client.onUpdate.listen(chunks.add);

      await client.initialize();
      final session = await client.newSession('/tmp');
      final result = await client.prompt(
        session.sessionId,
        'Hello',
      ).timeout(
        const Duration(seconds: 10),
        onTimeout: () => fail('prompt timed out'),
      );

      expect(result.stopReason, StopReason.endTurn);
      expect(chunks, isNotEmpty);
      expect(chunks.first, 'Mock response');

      await sub.cancel();
      await client.close();
      await process.exitCode.timeout(const Duration(seconds: 10));
    });

    test('rejects second concurrent prompt for same session (DP-4)', () async {
      final process = await _spawnMockServer();
      final client = AcpClient(
        AcpTransport(input: process.stdout, output: process.stdin),
      );

      await client.initialize();
      final session = await client.newSession('/tmp');

      // Start the first prompt but don't await it yet.
      // The mock server has a 100ms delay before settling, so the first
      // prompt will be in-flight when we call the second.
      final firstPrompt = client.prompt(session.sessionId, 'First');

      // The second prompt should fail with StateError (DP-4 single in-flight).
      // In Dart, async functions catch synchronous throws and turn them into
      // Future errors, so we use expectLater with the Future.
      await expectLater(
        client.prompt(session.sessionId, 'Second'),
        throwsA(isA<StateError>()),
      );

      // Clean up: await the first prompt.
      await firstPrompt.timeout(
        const Duration(seconds: 10),
        onTimeout: () => fail('first prompt timed out'),
      );

      await client.close();
      await process.exitCode.timeout(const Duration(seconds: 10));
    });

    test('concurrent prompts on different sessions succeed', () async {
      final process = await _spawnMockServer();
      final client = AcpClient(
        AcpTransport(input: process.stdout, output: process.stdin),
      );

      await client.initialize();
      final session1 = await client.newSession('/tmp');
      final session2 = await client.newSession('/tmp');

      // Both prompts should complete successfully (different session ids).
      final results = await Future.wait([
        client.prompt(session1.sessionId, 'Hello from 1'),
        client.prompt(session2.sessionId, 'Hello from 2'),
      ]).timeout(
        const Duration(seconds: 10),
        onTimeout: () => fail('concurrent prompts timed out'),
      );

      expect(results[0].stopReason, StopReason.endTurn);
      expect(results[1].stopReason, StopReason.endTurn);

      await client.close();
      await process.exitCode.timeout(const Duration(seconds: 10));
    });
  });
}
