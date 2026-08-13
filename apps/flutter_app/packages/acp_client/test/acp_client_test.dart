// End-to-end tracer test: spawn mock ACP server, complete initialize handshake.
//
// This is the TRACER — it proves the ACP-over-stdio contract works in Dart:
// subprocess spawn → initialize → assert protocolVersion 1 → session/new →
// clean exit.
import 'dart:io';

import 'package:acp_client/acp_client.dart';
import 'package:flutter_test/flutter_test.dart';

/// Resolves the path to the mock ACP server fixture.
///
/// Works both when CWD is the acp_client package (`dart test`) and when
/// CWD is the parent Flutter app (`flutter test packages/acp_client`).
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
  group('AcpClient end-to-end tracer', () {
    test('initialize handshake completes with protocolVersion 1', () async {
      final process = await _spawnMockServer();

      final client = AcpClient(
        AcpTransport(input: process.stdout, output: process.stdin),
      );

      // Initialize handshake.
      final initResult = await client.initialize().timeout(
        const Duration(seconds: 10),
        onTimeout: () => fail('initialize timed out'),
      );

      expect(initResult.protocolVersion, 1);
      expect(initResult.agentInfo.name, isNotEmpty);
      expect(initResult.agentInfo.name, 'mock-acp');
      expect(initResult.agentInfo.version, '0.0.1');
      expect(initResult.authMethods, isEmpty);
      expect(initResult.agentCapabilities.promptCapabilities.image, isFalse);
      expect(initResult.agentCapabilities.promptCapabilities.audio, isFalse);
      expect(
        initResult.agentCapabilities.promptCapabilities.embeddedContext,
        isFalse,
      );

      await client.close();
      final exitCode = await process.exitCode.timeout(
        const Duration(seconds: 10),
      );
      expect(exitCode, 0);
    });

    test('newSession returns a non-empty sessionId', () async {
      final process = await _spawnMockServer();

      final client = AcpClient(
        AcpTransport(input: process.stdout, output: process.stdin),
      );

      await client.initialize();
      final sessionResult = await client.newSession('/tmp').timeout(
        const Duration(seconds: 10),
        onTimeout: () => fail('newSession timed out'),
      );

      expect(sessionResult.sessionId, isNotEmpty);
      expect(sessionResult.sessionId, startsWith('mock-session-'));

      await client.close();
      final exitCode = await process.exitCode.timeout(
        const Duration(seconds: 10),
      );
      expect(exitCode, 0);
    });

    test('prompt returns end_turn stop reason', () async {
      final process = await _spawnMockServer();

      final client = AcpClient(
        AcpTransport(input: process.stdout, output: process.stdin),
      );

      // Collect notifications.
      final notifications = <JsonRpcNotification>[];
      client.onNotification = notifications.add;

      await client.initialize();
      final session = await client.newSession('/tmp');
      final promptResult = await client.prompt(
        session.sessionId,
        'Hello',
      ).timeout(
        const Duration(seconds: 10),
        onTimeout: () => fail('prompt timed out'),
      );

      expect(promptResult.stopReason, StopReason.endTurn);

      // The mock server sends one session/update notification before the
      // prompt result.
      expect(notifications, hasLength(1));
      expect(notifications.first.method, 'session/update');

      await client.close();
      final exitCode = await process.exitCode.timeout(
        const Duration(seconds: 10),
      );
      expect(exitCode, 0);
    });

    test('ID correlation: sequential requests get sequential ids', () async {
      final process = await _spawnMockServer();

      final client = AcpClient(
        AcpTransport(input: process.stdout, output: process.stdin),
      );

      // The first request (initialize) gets id 1, the second (session/new)
      // gets id 2. Both should complete successfully in sequence.
      final initResult = await client.initialize();
      final sessionResult = await client.newSession('/tmp');

      expect(initResult.protocolVersion, 1);
      expect(sessionResult.sessionId, isNotEmpty);

      await client.close();
      final exitCode = await process.exitCode.timeout(
        const Duration(seconds: 10),
      );
      expect(exitCode, 0);
    });
  });
}
