// Wire-boundary defense tests for AcpClient.
//
// Covers CR-01, CR-02, WR-02, WR-03 from the Phase 112 code review:
// - CR-01: a throwing permission policy callback must default to reject-once
//   rather than hanging the in-flight prompt.
// - CR-02: a malformed server request (non-integer id, missing method) must
//   not become an unhandled async error or hang the server.
// - WR-02: a response with a non-integer id must be dropped silently rather
//   than throwing TypeError inside the stream listener.
// - WR-03: JsonRpcRequest.fromJson / JsonRpcResponse.fromJson throw
//   FormatException (not TypeError) on non-integer ids.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:acp_client/acp_client.dart';
import 'package:flutter_test/flutter_test.dart';

/// A minimal [IOSink] that collects written strings for assertions.
class _SyncSink implements IOSink {
  final StringBuffer _current = StringBuffer();
  final List<String> lines = [];

  @override
  void writeln([Object? obj = '']) {
    _current.write(obj);
    _current.write('\n');
    lines.add(_current.toString());
    _current.clear();
  }

  @override
  void write(Object? obj) => _current.write(obj);

  @override
  void writeAll(Iterable<dynamic> objects, [String separator = '']) =>
      _current.writeAll(objects, separator);

  @override
  void writeCharCode(int charCode) => _current.writeCharCode(charCode);

  @override
  void add(List<int> data) {}

  @override
  void addError(Object error, [StackTrace? stackTrace]) {}

  @override
  Future<void> addStream(Stream<List<int>> stream) async {}

  @override
  Future<void> get done async => Future<void>.value();

  @override
  Future<void> flush() async => Future<void>.value();

  @override
  Future<void> close() async => Future<void>.value();

  @override
  Encoding get encoding => utf8;

  @override
  set encoding(Encoding value) {}
}

/// A test harness that wraps a real [AcpTransport] with a controllable
/// input stream and a capturing output sink.
class _Harness {
  _Harness() {
    transport = AcpTransport(
      input: inputController.stream,
      output: output,
    );
    client = AcpClient(transport);
  }

  final StreamController<List<int>> inputController =
      StreamController<List<int>>();
  final _SyncSink output = _SyncSink();
  late final AcpTransport transport;
  late final AcpClient client;

  /// Injects a decoded JSON message into the client's input stream.
  void inject(Map<String, dynamic> message) {
    inputController.add(utf8.encode('${jsonEncode(message)}\n'));
  }

  /// Returns all outgoing messages decoded from the output sink.
  List<Map<String, dynamic>> get sent => output.lines
      .map((l) => jsonDecode(l) as Map<String, dynamic>)
      .toList();

  Future<void> close() async {
    await client.close();
    await inputController.close();
  }
}

void main() {
  group('CR-01: throwing permission policy defaults to reject-once', () {
    test('policy callback throw → reject-once response sent, no hang', () async {
      final h = _Harness();

      // Policy that always throws (simulates a UI-layer bug).
      h.client.setPermissionPolicy(
        (_) => throw StateError('policy boom'),
      );

      // Inject a session/request_permission server request.
      h.inject({
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'session/request_permission',
        'params': {
          'sessionId': 's1',
          'toolCall': {'toolCallId': 'c1', 'toolName': 'terminal'},
          'options': [
            {'optionId': 'allow-once', 'name': 'Allow', 'kind': 'allow_once'},
            {'optionId': 'reject-once', 'name': 'Reject', 'kind': 'reject_once'},
          ],
        },
      });

      // Wait for the client to process and respond.
      await Future<void>.delayed(const Duration(milliseconds: 100));

      // The client must have sent a reject-once response, not hung.
      final permissionResponses =
          h.sent.where((m) => m['id'] == 1 && m.containsKey('result')).toList();
      expect(permissionResponses, hasLength(1),
          reason: 'client must respond to the permission request');
      final outcome = permissionResponses.first['result']['outcome'];
      expect(outcome['optionId'], 'reject-once');

      await h.close();
    });

    test('malformed permission params → reject-once response, no hang',
        () async {
      final h = _Harness();

      // Inject a permission request with malformed params (missing toolCall).
      h.inject({
        'jsonrpc': '2.0',
        'id': 2,
        'method': 'session/request_permission',
        'params': {'sessionId': 's1'},
      });

      await Future<void>.delayed(const Duration(milliseconds: 100));

      final responses =
          h.sent.where((m) => m['id'] == 2 && m.containsKey('result')).toList();
      expect(responses, hasLength(1),
          reason: 'client must default to reject-once on parse failure');
      expect(responses.first['result']['outcome']['optionId'], 'reject-once');

      await h.close();
    });
  });

  group('CR-02: malformed server request does not hang or crash', () {
    test('server request with non-integer id is dropped silently', () async {
      final h = _Harness();

      // Inject a server request with a string id — JsonRpcRequest.fromJson
      // should reject this, and the handler should drop it without sending
      // a response (no recoverable id).
      h.inject({
        'jsonrpc': '2.0',
        'id': 'not-an-int',
        'method': 'session/request_permission',
        'params': {},
      });

      await Future<void>.delayed(const Duration(milliseconds: 100));

      // No response should be sent (id was not recoverable).
      final responses = h.sent
          .where((m) => m.containsKey('result') || m.containsKey('error'))
          .toList();
      expect(responses, isEmpty,
          reason: 'non-integer id → dropped, no response possible');

      await h.close();
    });

    test(
        'server request with integer id but non-string method → error response',
        () async {
      final h = _Harness();

      // Inject a server request with a valid id but a non-string method.
      // The router sees both `id` and `method` keys present, so it dispatches
      // to _handleServerRequest. JsonRpcRequest.fromJson throws
      // FormatException on the non-string method, and the handler sends a
      // -32603 error response for the recoverable id.
      h.inject({
        'jsonrpc': '2.0',
        'id': 7,
        'method': 42,
        'params': {},
      });

      await Future<void>.delayed(const Duration(milliseconds: 100));

      // The handler should send a -32603 error response for id 7.
      final errorResponses =
          h.sent.where((m) => m['id'] == 7 && m.containsKey('error')).toList();
      expect(errorResponses, hasLength(1),
          reason: 'recoverable id → JSON-RPC error response');
      expect(errorResponses.first['error']['code'], -32603);

      await h.close();
    });
  });

  group('WR-02: response with non-integer id is dropped silently', () {
    test('string id response does not crash the stream listener', () async {
      final h = _Harness();

      // Inject a response with a string id. The client should drop it
      // silently rather than throwing TypeError inside the stream onData.
      h.inject({'jsonrpc': '2.0', 'id': 'abc', 'result': {}});

      // If the stream listener threw, the subscription's onError would fire
      // and the client would be in a broken state. We verify by sending a
      // subsequent well-formed request and confirming the client still works.
      await Future<void>.delayed(const Duration(milliseconds: 50));

      // Now send a real request and a matching response.
      final initFuture = h.client.initialize();
      await Future<void>.delayed(const Duration(milliseconds: 50));
      // The client sent initialize with id 1; inject the matching response.
      h.inject({
        'jsonrpc': '2.0',
        'id': 1,
        'result': {
          'protocolVersion': 1,
          'agentInfo': {'name': 'test', 'version': '0.0.1'},
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

      final result = await initFuture.timeout(const Duration(seconds: 5));
      expect(result.protocolVersion, 1,
          reason: 'client must still function after dropping a bad-id response');

      await h.close();
    });
  });

  group('WR-03: fromJson factories throw FormatException on bad ids', () {
    test('JsonRpcRequest.fromJson rejects non-integer id', () {
      expect(
        () => JsonRpcRequest.fromJson({'id': 'x', 'method': 'foo'}),
        throwsA(isA<FormatException>()),
      );
    });

    test('JsonRpcRequest.fromJson rejects non-string method', () {
      expect(
        () => JsonRpcRequest.fromJson({'id': 1, 'method': 42}),
        throwsA(isA<FormatException>()),
      );
    });

    test('JsonRpcResponse.fromJson rejects non-integer id', () {
      expect(
        () => JsonRpcResponse.fromJson({'id': 'x', 'result': {}}),
        throwsA(isA<FormatException>()),
      );
    });
  });
}
