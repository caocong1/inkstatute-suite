import 'package:flutter_test/flutter_test.dart';
import 'dart:async';
import 'package:flutter_app/chat/error_mapper.dart';
import 'package:flutter_app/chat/chat_models.dart';

void main() {
  group('ErrorMapper.map', () {
    test('maps TimeoutException to timeout error', () {
      final error = TimeoutException('timed out', Duration(seconds: 30));
      final result = ErrorMapper.map(error);
      expect(result.errorType, ErrorType.timeout);
      expect(result.userMessage, '请求超时，请重试');
    });

    test('maps ProcessException to engineNotStarted', () {
      final error = Exception('ProcessException: Failed to spawn node');
      final result = ErrorMapper.map(error);
      expect(result.errorType, ErrorType.engineNotStarted);
      expect(result.userMessage, '引擎未启动，请检查安装');
    });

    test('maps connection refused to engineNotStarted', () {
      final error = Exception('Connection refused by host');
      final result = ErrorMapper.map(error);
      expect(result.errorType, ErrorType.engineNotStarted);
    });

    test('maps 429 to rateLimited', () {
      final error = Exception('HTTP 429: too many requests');
      final result = ErrorMapper.map(error);
      expect(result.errorType, ErrorType.rateLimited);
      expect(result.userMessage, '请求过于频繁，请稍后重试');
    });

    test('maps 401 to authFailed', () {
      final error = Exception('HTTP 401: Unauthorized');
      final result = ErrorMapper.map(error);
      expect(result.errorType, ErrorType.authFailed);
      expect(result.userMessage, '鉴权失败，请检查 API 密钥');
    });

    test('maps unknown error to unknown type', () {
      final error = Exception('something weird happened');
      final result = ErrorMapper.map(error);
      expect(result.errorType, ErrorType.unknown);
      expect(result.userMessage, '发生未知错误');
    });

    test('never includes raw stack trace in user message', () {
      final error = Exception('detailed internal error with stack: #0 #1 #2');
      final result = ErrorMapper.map(error);
      expect(result.userMessage, isNot(contains('stack')));
      expect(result.userMessage, isNot(contains('#0')));
    });
  });

  group('ErrorMapper.logStackTrace', () {
    test('does not throw', () {
      try {
        ErrorMapper.logStackTrace(
          Exception('test'),
          StackTrace.current,
        );
      } catch (e) {
        fail('logStackTrace should not throw: $e');
      }
    });
  });
}
