// Tests for session/new: absolute cwd success, relative cwd client-side
// rejection, additionalDirectories server rejection, mcpServers server
// rejection.
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
  group('AcpClient.newSession', () {
    test('absolute cwd returns a sessionId', () async {
      final process = await _spawnMockServer();
      final client = AcpClient(
        AcpTransport(input: process.stdout, output: process.stdin),
      );

      await client.initialize();
      final result = await client.newSession('/tmp').timeout(
        const Duration(seconds: 10),
        onTimeout: () => fail('newSession timed out'),
      );

      expect(result.sessionId, isNotEmpty);
      expect(result.sessionId, startsWith('mock-session-'));

      await client.close();
      final exitCode = await process.exitCode.timeout(
        const Duration(seconds: 10),
      );
      expect(exitCode, 0);
    });

    test('relative cwd throws ArgumentError client-side before sending',
        () async {
      final process = await _spawnMockServer();
      final client = AcpClient(
        AcpTransport(input: process.stdout, output: process.stdin),
      );

      await client.initialize();

      expect(
        () => client.newSession('relative/path'),
        throwsA(isA<ArgumentError>()),
      );

      await client.close();
      final exitCode = await process.exitCode.timeout(
        const Duration(seconds: 10),
      );
      expect(exitCode, 0);
    });

    test('non-empty additionalDirectories receives -32602 error from server',
        () async {
      final process = await _spawnMockServer();
      final client = AcpClient(
        AcpTransport(input: process.stdout, output: process.stdin),
      );

      await client.initialize();

      await expectLater(
        client.newSession(
          '/tmp',
          additionalDirectories: ['/extra'],
        ),
        throwsA(
          isA<AcpRpcException>().having(
            (e) => e.code,
            'code',
            -32602,
          ),
        ),
      );

      await client.close();
      await process.exitCode.timeout(
        const Duration(seconds: 10),
      );
    });

    test('non-empty mcpServers receives -32602 error from server', () async {
      final process = await _spawnMockServer();
      final client = AcpClient(
        AcpTransport(input: process.stdout, output: process.stdin),
      );

      await client.initialize();

      await expectLater(
        client.newSession(
          '/tmp',
          mcpServers: [
            {'name': 'test-server', 'transport': {'type': 'stdio'}},
          ],
        ),
        throwsA(
          isA<AcpRpcException>().having(
            (e) => e.code,
            'code',
            -32602,
          ),
        ),
      );

      await client.close();
      await process.exitCode.timeout(
        const Duration(seconds: 10),
      );
    });
  });
}
