/// Scripted mock ACP server for testing [AcpClient].
///
/// This Dart script reads NDJSON from stdin, matches incoming requests by
/// method, and writes scripted NDJSON responses to stdout. On stdin close
/// it exits cleanly with code 0.
///
/// Run as: `dart run test/fixtures/mock_acp_server.dart`
///
/// Supports an optional `--mode` argument:
/// - `default` (no flag): standard initialize/session/new/session/prompt flow.
/// - `permission`: sends `session/request_permission` before the prompt
///   response, waits for the client's response, then sends the appropriate
///   `agent_message_chunk` and prompt result.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

/// Entry point for the mock ACP server.
Future<void> main(List<String> args) async {
  var mode = 'default';
  for (final arg in args) {
    if (arg.startsWith('--mode=')) {
      mode = arg.substring('--mode='.length);
    }
  }

  final mock = MockAcpServer(stdin, stdout, mode: mode);
  await mock.run();
}

/// A scripted mock ACP server that responds to ACP protocol methods.
///
/// Reads NDJSON from [input], dispatches by method, and writes NDJSON
/// responses to [output]. Exits on input close.
class MockAcpServer {
  /// Creates a mock ACP server.
  MockAcpServer(this.input, this.output, {this.mode = 'default'});

  /// Input stream (subprocess stdin).
  final Stream<List<int>> input;

  /// Output sink (subprocess stdout).
  final IOSink output;

  /// Server mode: `default` or `permission`.
  final String mode;

  /// Session counter for generating unique session ids.
  int _sessionCounter = 0;

  /// Maps session ids to their in-flight prompt request ids (for cancel
  /// settling).
  final Map<String, int> _inflightPrompts = {};

  /// Serialize writes to prevent concurrent IOSink access.
  Future<void> _writeQueue = Future.value();

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
    final hasMethod = method != null;
    final hasId = id != null;

    // Handle incoming responses (client → server responses to our server
    // requests, e.g. session/request_permission response).
    if (hasId && !hasMethod) {
      _handleClientResponse(request);
      return;
    }

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
        final params = request['params'] as Map<String, dynamic>? ?? {};

        // Reject non-empty additionalDirectories (server-side -32602).
        final additionalDirs = params['additionalDirectories'];
        if (additionalDirs is List && additionalDirs.isNotEmpty) {
          _send({
            'jsonrpc': '2.0',
            'id': id,
            'error': {
              'code': -32602,
              'message':
                  'Invalid params: additionalDirectories is not supported',
            },
          });
          return;
        }

        // Reject non-empty mcpServers (server-side -32602).
        final mcpServers = params['mcpServers'];
        if (mcpServers is List && mcpServers.isNotEmpty) {
          _send({
            'jsonrpc': '2.0',
            'id': id,
            'error': {
              'code': -32602,
              'message': 'Invalid params: mcpServers is not supported',
            },
          });
          return;
        }

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
        final params = request['params'] as Map<String, dynamic>? ?? {};
        final sessionId = params['sessionId'] as String? ?? 'unknown';
        final requestId = id as int;

        // Track the in-flight prompt for cancel settling.
        _inflightPrompts[sessionId] = requestId;

        if (mode == 'permission') {
          _handlePermissionPrompt(sessionId, requestId);
        } else {
          _handleDefaultPrompt(sessionId, requestId);
        }
      case 'session/cancel':
        final params = request['params'] as Map<String, dynamic>? ?? {};
        final sessionId = params['sessionId'] as String? ?? 'unknown';

        // Notification — no response. Settle any in-flight prompt as cancelled.
        final inflightId = _inflightPrompts.remove(sessionId);
        if (inflightId != null) {
          _send({
            'jsonrpc': '2.0',
            'id': inflightId,
            'result': {'stopReason': 'cancelled'},
          });
        }
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

  /// Handles a default prompt: sends agent_message_chunk then end_turn.
  ///
  /// A short delay before the prompt response gives cancel notifications
  /// time to arrive and settle the prompt as cancelled.
  void _handleDefaultPrompt(String sessionId, int requestId) {
    // Send an agent_message_chunk notification, then the prompt result.
    // Use .then() chaining to ensure the notification is flushed before
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
      // Delay before settling the prompt — gives cancel time to arrive.
      Future.delayed(const Duration(milliseconds: 100), () {
        // If the prompt was cancelled while waiting, it's already settled.
        if (!_inflightPrompts.containsKey(sessionId)) return;
        _inflightPrompts.remove(sessionId);
        _send({
          'jsonrpc': '2.0',
          'id': requestId,
          'result': {'stopReason': 'end_turn'},
        });
      });
    });
  }

  /// Handles a permission-mode prompt: sends session/request_permission,
  /// waits for the client's response, then sends the appropriate
  /// agent_message_chunk and prompt result.
  void _handlePermissionPrompt(String sessionId, int requestId) {
    // Send session/request_permission as a server request (id: 1).
    _send({
      'jsonrpc': '2.0',
      'id': 1,
      'method': 'session/request_permission',
      'params': {
        'sessionId': sessionId,
        'toolCall': {'toolCallId': 'call_001'},
        'options': [
          {
            'optionId': 'allow-once',
            'name': 'Allow once',
            'kind': 'allow_once',
          },
          {
            'optionId': 'reject-once',
            'name': 'Reject',
            'kind': 'reject_once',
          },
        ],
      },
    });
  }

  /// Handles an incoming response from the client (e.g. permission outcome).
  ///
  /// When the client responds to our `session/request_permission` (id: 1),
  /// we send the appropriate `agent_message_chunk` and then settle the
  /// pending prompt.
  void _handleClientResponse(Map<String, dynamic> response) {
    final id = response['id'] as int;

    if (id == 1) {
      // Permission response — check the outcome and send the appropriate
      // agent_message_chunk, then settle the prompt.
      final result = response['result'] as Map<String, dynamic>? ?? {};
      final outcome = result['outcome'] as Map<String, dynamic>? ?? {};
      final optionId = outcome['optionId'] as String?;

      final text = optionId == 'allow-once'
          ? 'DONE'
          : 'The user rejected the permission escalation, so this command cannot be run.';

      // Find the session id for the in-flight prompt.
      String? sessionId;
      _inflightPrompts.forEach((sid, reqId) {
        if (reqId != null) sessionId = sid;
      });
      final promptRequestId = _inflightPrompts.remove(sessionId ?? '');

      _send({
        'jsonrpc': '2.0',
        'method': 'session/update',
        'params': {
          'sessionId': sessionId,
          'update': {
            'sessionUpdate': 'agent_message_chunk',
            'content': {'type': 'text', 'text': text},
          },
        },
      }).then((_) {
        if (promptRequestId != null) {
          _send({
            'jsonrpc': '2.0',
            'id': promptRequestId,
            'result': {'stopReason': 'end_turn'},
          });
        }
      });
    }
  }

  /// Sends a single NDJSON message, awaiting the flush.
  ///
  /// Writes are serialized via a Future chain to prevent concurrent IOSink
  /// access when multiple delayed responses fire simultaneously.
  Future<void> _send(Map<String, dynamic> message) async {
    final completer = Completer<void>();
    _writeQueue = _writeQueue.then((_) async {
      output.writeln(jsonEncode(message));
      await output.flush();
      completer.complete();
    }).catchError((e) {
      completer.completeError(e as Object);
    });
    return completer.future;
  }
}
