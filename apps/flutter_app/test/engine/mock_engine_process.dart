/// Mock engine process for testing [DshProcessManager].
///
/// This Dart script simulates a DSH ACP server for testing. It reads
/// NDJSON from stdin, responds to `initialize` with the verified
/// response shape (protocolVersion 1, agentInfo, etc.), and exits with
/// code 0 on stdin close.
///
/// Run as: `dart run test/engine/mock_engine_process.dart [options]`
///
/// Options:
/// - `--hang`: Ignores stdin close, keeps running until killed
///   (simulates a hung engine for timeout/kill tests).
/// - `--stderr`: Writes a diagnostic line to stderr on startup
///   (for stderr handling tests).
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

/// Entry point for the mock engine process.
Future<void> main(List<String> args) async {
  var hang = false;
  var emitStderr = false;
  for (final arg in args) {
    if (arg == '--hang') {
      hang = true;
    } else if (arg == '--stderr') {
      emitStderr = true;
    }
  }

  final mock = MockEngineProcess(
    stdin,
    stdout,
    stderr,
    hang: hang,
    emitStderr: emitStderr,
  );
  await mock.run();
}

/// A mock DSH ACP server that responds to ACP protocol methods.
///
/// Reads NDJSON from [input], dispatches by method, and writes NDJSON
/// responses to [output]. Exits on input close (unless [hang] is true).
class MockEngineProcess {
  /// Creates a mock engine process.
  MockEngineProcess(
    this.input,
    this.output,
    this.errorOutput, {
    this.hang = false,
    this.emitStderr = false,
  });

  /// Input stream (subprocess stdin).
  final Stream<List<int>> input;

  /// Output sink (subprocess stdout — reserved for JSON-RPC).
  final IOSink output;

  /// Error output sink (subprocess stderr — diagnostics only).
  final IOSink errorOutput;

  /// When true, ignores stdin close and keeps running until killed.
  final bool hang;

  /// When true, writes a diagnostic line to stderr on startup.
  final bool emitStderr;

  /// Serialize writes to prevent concurrent IOSink access.
  Future<void> _writeQueue = Future.value();

  /// Starts the mock server loop.
  ///
  /// Reads NDJSON lines until input closes. In normal mode, exits with
  /// code 0 on input close. In [hang] mode, keeps running forever
  /// (until killed externally).
  Future<void> run() async {
    if (emitStderr) {
      await _writeStderr('mock-engine: startup diagnostic (not customer data)');
    }

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

    if (hang) {
      // Keep running forever — the process will be killed externally.
      await Completer<void>().future;
    }

    await output.flush();
    exit(0);
  }

  /// Handles an incoming JSON-RPC request.
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
            'agentInfo': {'name': 'mock-dsh-engine', 'version': '0.0.1'},
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
        _send({
          'jsonrpc': '2.0',
          'id': id,
          'result': {'sessionId': 'mock-session-001'},
        });
      case 'authenticate':
        _send({'jsonrpc': '2.0', 'id': id, 'result': <String, dynamic>{}});
      default:
        _send({
          'jsonrpc': '2.0',
          'id': id,
          'error': {'code': -32601, 'message': 'Method not found: $method'},
        });
    }
  }

  /// Sends a single NDJSON message to stdout.
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

  /// Writes a diagnostic line to stderr.
  Future<void> _writeStderr(String line) async {
    final completer = Completer<void>();
    _writeQueue = _writeQueue.then((_) async {
      errorOutput.writeln(line);
      await errorOutput.flush();
      completer.complete();
    }).catchError((e) {
      completer.completeError(e as Object);
    });
    return completer.future;
  }
}
