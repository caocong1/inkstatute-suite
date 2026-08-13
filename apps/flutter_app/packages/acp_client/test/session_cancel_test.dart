// Tests for session/cancel: notification sent (no id), in-flight prompt
// settles as cancelled, cancel unknown sessionId is no-op.
import 'dart:async';
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
  group('AcpClient.cancel', () {
    test('cancel settles in-flight prompt as cancelled', () async {
      final process = await _spawnMockServer();
      final client = AcpClient(
        AcpTransport(input: process.stdout, output: process.stdin),
      );

      await client.initialize();
      final session = await client.newSession('/tmp');

      // Start a prompt but don't await it yet.
      final promptFuture = client.prompt(session.sessionId, 'Hello');

      // Send cancel — the mock server settles the prompt as cancelled.
      await client.cancel(session.sessionId);

      final result = await promptFuture.timeout(
        const Duration(seconds: 10),
        onTimeout: () => fail('prompt did not settle after cancel'),
      );

      expect(result.stopReason, StopReason.cancelled);

      await client.close();
      final exitCode = await process.exitCode.timeout(
        const Duration(seconds: 10),
      );
      expect(exitCode, 0);
    });

    test('cancel with unknown sessionId is a no-op (no error)', () async {
      final process = await _spawnMockServer();
      final client = AcpClient(
        AcpTransport(input: process.stdout, output: process.stdin),
      );

      await client.initialize();

      // Cancel a non-existent session — should not throw.
      await client.cancel('nonexistent-session-id').timeout(
        const Duration(seconds: 10),
        onTimeout: () => fail('cancel timed out'),
      );

      // Client should still be functional.
      final session = await client.newSession('/tmp');
      expect(session.sessionId, isNotEmpty);

      await client.close();
      final exitCode = await process.exitCode.timeout(
        const Duration(seconds: 10),
      );
      expect(exitCode, 0);
    });
  });
}
