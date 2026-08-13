/// NDJSON stdio framing for ACP over stdio.
///
/// ACP uses newline-delimited JSON (NDJSON): each JSON-RPC message is a single
/// compact JSON object terminated by `\n`. No LSP-style framing headers.
///
/// Verified from `@agentclientprotocol/sdk/dist/stream.js` — `ndJsonStream`:
/// - Writing: `JSON.stringify(message) + "\n"`
/// - Reading: split on `\n`, trim, parse each non-empty line as JSON
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

/// NDJSON transport over a pair of byte streams (stdin/stdout of a subprocess).
///
/// [AcpTransport.send] writes a JSON-RPC message as one NDJSON line to the
/// [IOSink]. [AcpTransport.messages] exposes a stream of parsed JSON-RPC
/// messages from the input byte stream.
///
/// Writes are serialized via a Future chain to prevent "StreamSink is bound"
/// errors when multiple sends race (e.g. prompt + cancel, or concurrent
/// prompts on different sessions).
class AcpTransport {
  /// Creates an ACP transport from a process's stdin/stdout.
  ///
  /// [input] is the subprocess's stdout (a `Stream<List<int>>`).
  /// [output] is the subprocess's stdin (an `IOSink`).
  AcpTransport({required this._input, required this._output});

  final Stream<List<int>> _input;
  final IOSink _output;

  /// Serialize writes to prevent concurrent IOSink access.
  Future<void> _writeQueue = Future.value();

  /// Cached single-subscription message stream.
  ///
  /// The input byte stream is single-subscription; building a new transform
  /// chain on every `messages` access would throw "Stream has already been
  /// listened to" on the second subscription. Cache it once so the contract
  /// is stable for any caller.
  late final Stream<Map<String, dynamic>> _messagesStream = _buildMessages();

  Stream<Map<String, dynamic>> _buildMessages() {
    return _input
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .where((line) => line.trim().isNotEmpty)
        .map((line) {
      try {
        return jsonDecode(line) as Map<String, dynamic>;
      } on FormatException {
        // T-112-01: validate each NDJSON line is valid JSON before parsing;
        // skip unparseable lines without crashing the client.
        return null;
      }
    }).where((m) => m != null).cast<Map<String, dynamic>>();
  }

  /// Sends a JSON-RPC message as one NDJSON line.
  ///
  /// Writes `jsonEncode(message) + "\n"` to the output sink and flushes.
  /// Returns a future that completes when the write is flushed to the OS.
  ///
  /// Writes are serialized: if a previous write is still flushing, this
  /// call waits for it to complete before writing.
  Future<void> send(Map<String, dynamic> message) async {
    final completer = Completer<void>();
    _writeQueue = _writeQueue.then((_) async {
      _output.writeln(jsonEncode(message));
      await _output.flush();
      completer.complete();
    }).catchError((e) {
      completer.completeError(e as Object);
    });
    return completer.future;
  }

  /// Stream of parsed JSON-RPC messages from the input.
  ///
  /// Transforms the raw byte stream with `utf8.decoder` → `LineSplitter` →
  /// filters empty lines → `jsonDecode` each line as `Map<String, dynamic>`.
  ///
  /// Lines that fail JSON parsing are skipped (T-112-01 mitigation: validate
  /// each line before parsing, handle errors gracefully without crashing).
  Stream<Map<String, dynamic>> get messages => _messagesStream;

  /// Closes the output sink (signals EOF to the subprocess).
  Future<void> close() async {
    await _output.flush();
    await _output.close();
  }
}
