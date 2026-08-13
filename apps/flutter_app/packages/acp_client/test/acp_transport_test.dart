// Unit tests for AcpTransport — NDJSON framing.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:acp_client/acp_transport.dart';
import 'package:flutter_test/flutter_test.dart';

/// A minimal [IOSink] that collects written strings for assertions.
///
/// All write methods are synchronous; [flush] and [close] complete immediately.
class _SyncSink implements IOSink {
  final List<String> lines = [];
  final StringBuffer _current = StringBuffer();

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

void main() {
  group('AcpTransport.send', () {
    test('writes JSON + newline to the output sink', () async {
      final output = _SyncSink();
      final transport = AcpTransport(
        input: const Stream<List<int>>.empty(),
        output: output,
      );

      await transport.send({'jsonrpc': '2.0', 'id': 1, 'method': 'test'});

      expect(output.lines, hasLength(1));
      final decoded = jsonDecode(output.lines.first) as Map<String, dynamic>;
      expect(decoded['jsonrpc'], '2.0');
      expect(decoded['id'], 1);
      expect(decoded['method'], 'test');
      expect(output.lines.first.endsWith('\n'), isTrue);
    });

    test('writes multiple messages as separate NDJSON lines', () async {
      final output = _SyncSink();
      final transport = AcpTransport(
        input: const Stream<List<int>>.empty(),
        output: output,
      );

      await transport.send({'id': 1});
      await transport.send({'id': 2});
      await transport.send({'id': 3});

      expect(output.lines, hasLength(3));
      expect(jsonDecode(output.lines[0])['id'], 1);
      expect(jsonDecode(output.lines[1])['id'], 2);
      expect(jsonDecode(output.lines[2])['id'], 3);
    });
  });

  group('AcpTransport.messages', () {
    test('parses NDJSON input lines into maps', () async {
      final controller = StreamController<List<int>>();
      final transport = AcpTransport(
        input: controller.stream,
        output: _SyncSink(),
      );

      final received = <Map<String, dynamic>>[];
      final sub = transport.messages.listen(received.add);

      controller.add(utf8.encode('{"id":1,"method":"a"}\n'));
      controller.add(utf8.encode('{"id":2,"method":"b"}\n'));
      await Future<void>.delayed(const Duration(milliseconds: 50));

      expect(received, hasLength(2));
      expect(received[0]['id'], 1);
      expect(received[0]['method'], 'a');
      expect(received[1]['id'], 2);
      expect(received[1]['method'], 'b');

      await sub.cancel();
      await controller.close();
    });

    test('skips empty lines', () async {
      final controller = StreamController<List<int>>();
      final transport = AcpTransport(
        input: controller.stream,
        output: _SyncSink(),
      );

      final received = <Map<String, dynamic>>[];
      final sub = transport.messages.listen(received.add);

      controller.add(utf8.encode('{"id":1}\n\n\n{"id":2}\n'));
      await Future<void>.delayed(const Duration(milliseconds: 50));

      expect(received, hasLength(2));

      await sub.cancel();
      await controller.close();
    });

    test('skips unparseable lines without crashing (T-112-01)', () async {
      final controller = StreamController<List<int>>();
      final transport = AcpTransport(
        input: controller.stream,
        output: _SyncSink(),
      );

      final received = <Map<String, dynamic>>[];
      final sub = transport.messages.listen(received.add);

      controller.add(
        utf8.encode('{"valid":true}\nnot json at all\n{"id":42}\n'),
      );
      await Future<void>.delayed(const Duration(milliseconds: 50));

      expect(received, hasLength(2));
      expect(received[0]['valid'], true);
      expect(received[1]['id'], 42);

      await sub.cancel();
      await controller.close();
    });
  });
}
