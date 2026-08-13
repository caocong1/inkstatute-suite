/// Scripted mock ACP server for testing [AcpClient].
///
/// This Dart script reads NDJSON from stdin, matches incoming requests by
/// method, and writes scripted NDJSON responses to stdout. On stdin close
/// it exits cleanly with code 0.
///
/// Run as: `dart run test/fixtures/mock_acp_server.dart`
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

/// Entry point for the mock ACP server.
Future<void> main() async {
  final mock = MockAcpServer(stdin, stdout);
  await mock.run();
}

/// A scripted mock ACP server that responds to `initialize` and `session/new`.
///
/// Reads NDJSON from [input], dispatches by method, and writes NDJSON
/// responses to [output]. Exits on input close.
class MockAcpServer {
  /// Creates a mock ACP server.
  MockAcpServer(this.input, this.output);

  /// Input stream (subprocess stdin).
  final Stream<List<int>> input;

  /// Output sink (subprocess stdout).
  final IOSink output;

  /// Session counter for generating unique session ids.
  int _sessionCounter = 0;

  /// Starts the mock server loop.
  ///
  /// Reads NDJSON lines until input closes, then exits.
  Future<void> run() async {
    final completer = Completer<void>();

    final sub = input
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .where((line) => line.trim().isNotEmpty)
        .listen(
          (line) {
            try {
              final request = jsonDecode(line) as Map<String, dynamic>;
              _handleRequest(request);
            } on FormatException {
              // Skip unparseable lines.
            }
          },
          onDone: () => completer.complete(),
          onError: (e) => completer.complete(),
        );

    await completer.future;
    await sub.cancel();
    await output.flush();
  }

  void _handleRequest(Map<String, dynamic> request) {
    final method = request['method'] as String?;
    final id = request['id'];

    switch (method) {
      case 'initialize':
        _send({
          'jsonrpc': '2.0',
          'id': id,
          'result': {
            'protocolVersion': 1,
            'agentInfo': {'name': 'mock-acp', 'version': '0.0.1'},
            'agentCapabilities': {
              'promptCapabilities': {
                'image': false,
                'audio': false,
                'embeddedContext': false,
              },
            },
            'authMethods': <dynamic>[],
          },
        });
      case 'session/new':
        _sessionCounter++;
        _send({
          'jsonrpc': '2.0',
          'id': id,
          'result': {
            'sessionId':
                'mock-session-${_sessionCounter.toString().padLeft(3, '0')}',
          },
        });
      case 'session/prompt':
        final params = request['params'] as Map<String, dynamic>?;
        final sessionId = params?['sessionId'] as String? ?? 'unknown';
        // Send an agent_message_chunk notification, then the prompt result.
        // Use scheduleMicrotask to ensure the notification is flushed before
        // the response is written (IOSink.flush is async).
        _send({
          'jsonrpc': '2.0',
          'method': 'session/update',
          'params': {
            'sessionId': sessionId,
            'update': {
              'sessionUpdate': 'agent_message_chunk',
              'content': {'type': 'text', 'text': 'Mock response'},
            },
          },
        }).then((_) {
          _send({
            'jsonrpc': '2.0',
            'id': id,
            'result': {'stopReason': 'end_turn'},
          });
        });
      case 'session/cancel':
        // Notification — no response.
        break;
      case 'authenticate':
        _send({'jsonrpc': '2.0', 'id': id, 'result': <String, dynamic>{}});
      default:
        // Method not found.
        _send({
          'jsonrpc': '2.0',
          'id': id,
          'error': {
            'code': -32601,
            'message': 'Method not found: $method',
          },
        });
    }
  }

  /// Sends a single NDJSON message, awaiting the flush.
  Future<void> _send(Map<String, dynamic> message) async {
    output.writeln(jsonEncode(message));
    await output.flush();
  }
}
