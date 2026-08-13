/// ACP v1 client — initialize handshake, session management, ID correlation.
///
/// [AcpClient] wraps an [AcpTransport] and provides typed methods for the
/// ACP protocol. It tracks pending requests by ID and completes them when
/// matching responses arrive. Notifications and server requests are dispatched
/// to handler callbacks.
///
/// This is the tracer implementation: `initialize` and `newSession` are
/// fully implemented. Full method coverage expands in Wave 2.
library;

import 'dart:async';

import 'acp_protocol.dart';
import 'acp_transport.dart';
import 'acp_types.dart';

// Re-export types so consumers can import a single entry point.
export 'acp_protocol.dart';
export 'acp_transport.dart';
export 'acp_types.dart';

/// Callback for server → client notifications (no id, has method).
typedef NotificationHandler = void Function(JsonRpcNotification notification);

/// Callback for server → client requests (has id + method, expects a response).
typedef ServerRequestHandler = Future<Map<String, dynamic>> Function(
  JsonRpcRequest request,
);

/// ACP v1 client with ID correlation and pending request tracking.
class AcpClient {
  /// Creates an ACP client connected to the given [transport].
  AcpClient(this._transport) {
    _subscription = _transport.messages.listen(_handleMessage, onError: (e) {
      // Drain errors to prevent unhandled stream errors; callers handle
      // failures via pending completers or close detection.
    });
  }

  final AcpTransport _transport;
  StreamSubscription<Map<String, dynamic>>? _subscription;

  int _nextId = 1;
  final Map<int, Completer<Map<String, dynamic>>> _pending = {};

  /// Handler for server → client notifications.
  ///
  /// Set by the caller to receive `session/update` and other notifications.
  NotificationHandler? onNotification;

  /// Handler for server → client requests.
  ///
  /// Set by the caller to handle `session/request_permission`.
  /// The returned map is sent as the response result.
  ServerRequestHandler? onServerRequest;

  /// Sends an `initialize` request and returns the typed result.
  ///
  /// Sends:
  /// ```json
  /// {"jsonrpc":"2.0","id":<id>,"method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{}}}
  /// ```
  ///
  /// Returns an [InitializeResult] with `protocolVersion == 1`.
  Future<InitializeResult> initialize() async {
    final result = await _call('initialize', const InitializeParams().toJson());
    return InitializeResult.fromJson(result);
  }

  /// Sends a `session/new` request with an absolute [cwd].
  ///
  /// Returns a [SessionNewResult] with the new session id.
  Future<SessionNewResult> newSession(String cwd) async {
    final result = await _call(
      'session/new',
      SessionNewParams(cwd: cwd).toJson(),
    );
    return SessionNewResult.fromJson(result);
  }

  /// Sends a `session/prompt` request.
  ///
  /// [sessionId] must be from a prior [newSession] call.
  /// [text] is the prompt text (concatenated into one user message).
  Future<SessionPromptResult> prompt(String sessionId, String text) async {
    final result = await _call(
      'session/prompt',
      SessionPromptParams(
        sessionId: sessionId,
        prompt: [PromptTextBlock(text)],
      ).toJson(),
    );
    return SessionPromptResult.fromJson(result);
  }

  /// Sends a `session/cancel` notification (no response expected).
  Future<void> cancel(String sessionId) async {
    await _transport.send({
      'jsonrpc': '2.0',
      'method': 'session/cancel',
      'params': SessionCancelParams(sessionId: sessionId).toJson(),
    });
  }

  /// Sends an `authenticate` request (no-op for servers with no auth methods).
  Future<void> authenticate() async {
    await _call('authenticate', null);
  }

  /// Sends a response to a server → client request (e.g. permission response).
  Future<void> sendResponse(int id, Map<String, dynamic> result) async {
    await _transport.send({'jsonrpc': '2.0', 'id': id, 'result': result});
  }

  /// Closes the transport (signals EOF to the subprocess).
  Future<void> close() async {
    await _subscription?.cancel();
    await _transport.close();
  }

  /// Sends a JSON-RPC request and returns the result map.
  ///
  /// Assigns an auto-incrementing id, creates a completer, sends the request,
  /// and returns the completer's future. The future completes when a matching
  /// response arrives (or errors on a JSON-RPC error response).
  Future<Map<String, dynamic>> _call(
    String method,
    Map<String, dynamic>? params,
  ) async {
    final id = _nextId++;
    final completer = Completer<Map<String, dynamic>>();
    _pending[id] = completer;

    final request = <String, dynamic>{
      'jsonrpc': '2.0',
      'id': id,
      'method': method,
    };
    if (params != null) {
      request['params'] = params;
    }

    await _transport.send(request);

    return completer.future;
  }

  /// Handles an incoming JSON-RPC message.
  ///
  /// Distinguishes:
  /// - (a) response: has `id`, no `method` → complete pending future
  /// - (b) notification: has `method`, no `id` → dispatch to [onNotification]
  /// - (c) server request: has `id` + `method` → dispatch to [onServerRequest]
  void _handleMessage(Map<String, dynamic> message) {
    final hasId = message.containsKey('id');
    final hasMethod = message.containsKey('method');

    if (hasId && !hasMethod) {
      // (a) Response — complete the pending future.
      _handleResponse(message);
    } else if (hasMethod && !hasId) {
      // (b) Notification — dispatch to handler.
      final notification = JsonRpcNotification.fromJson(message);
      onNotification?.call(notification);
    } else if (hasId && hasMethod) {
      // (c) Server request — dispatch to handler and send response.
      _handleServerRequest(message);
    }
  }

  void _handleResponse(Map<String, dynamic> message) {
    final id = message['id'] as int;
    final completer = _pending.remove(id);
    if (completer == null) {
      // No pending request for this id — ignore (stale or duplicate).
      return;
    }

    if (message.containsKey('error')) {
      final error = JsonRpcError.fromJson(
        message['error'] as Map<String, dynamic>,
      );
      completer.completeError(
        AcpRpcException(error.code, error.message),
      );
    } else {
      final result = message['result'] as Map<String, dynamic>? ?? {};
      completer.complete(result);
    }
  }

  Future<void> _handleServerRequest(Map<String, dynamic> message) async {
    final request = JsonRpcRequest.fromJson(message);
    try {
      final result = await (onServerRequest?.call(request) ??
          Future.value(<String, dynamic>{}));
      await sendResponse(request.id, result);
    } catch (e) {
      await _transport.send({
        'jsonrpc': '2.0',
        'id': request.id,
        'error': {'code': -32603, 'message': e.toString()},
      });
    }
  }
}

/// Exception thrown when a JSON-RPC response carries an error.
class AcpRpcException implements Exception {
  /// Creates an ACP RPC exception.
  const AcpRpcException(this.code, this.message);

  /// JSON-RPC error code.
  final int code;

  /// Error message.
  final String message;

  @override
  String toString() => 'AcpRpcException($code): $message';
}
