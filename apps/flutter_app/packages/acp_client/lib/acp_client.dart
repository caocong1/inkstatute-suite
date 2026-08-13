/// ACP v1 client — full method coverage with ID correlation, in-flight
/// tracking, text aggregation, and permission policy hook.
///
/// [AcpClient] wraps an [AcpTransport] and provides typed methods for the
/// ACP protocol. It tracks pending requests by ID and completes them when
/// matching responses arrive. Notifications are dispatched to the [onUpdate]
/// stream (for `agent_message_chunk` text) and the [onNotification] callback
/// (for all notifications). Server requests for `session/request_permission`
/// are routed through the pluggable [PermissionPolicy] callback.
library;

import 'dart:async';
import 'dart:io';

import 'acp_protocol.dart';
import 'acp_transport.dart';
import 'acp_types.dart';

// Re-export types so consumers can import a single entry point.
export 'acp_protocol.dart';
export 'acp_transport.dart';
export 'acp_types.dart';
export 'approval_policy.dart';

/// Callback for server → client notifications (no id, has method).
typedef NotificationHandler = void Function(JsonRpcNotification notification);

/// ACP v1 client with ID correlation, in-flight tracking, and text aggregation.
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

  /// Session ids that currently have an in-flight `session/prompt` request.
  ///
  /// Enforces DP-4 (single in-flight per session): a second prompt for the
  /// same session is rejected client-side before sending.
  final Set<String> _inflightSessions = {};

  /// Stream controller for committed assistant text chunks from
  /// `session/update` `agent_message_chunk` notifications.
  final StreamController<String> _updateController =
      StreamController<String>.broadcast();

  /// Pluggable permission policy for `session/request_permission` requests.
  ///
  /// When set, the client calls this callback with the parsed
  /// [RequestPermissionParams] and sends the returned [PermissionOutcome]
  /// as the JSON-RPC response. When unset, the client defaults to
  /// `reject-once` (default deny).
  PermissionPolicy? _permissionPolicy;

  /// Handler for server → client notifications (all notification types).
  ///
  /// Set by the caller to receive raw notifications in addition to the
  /// [onUpdate] stream. `session/update` notifications are always processed
  /// for text aggregation regardless of this handler.
  NotificationHandler? onNotification;

  /// Exposes the stream of committed assistant text chunks.
  ///
  /// Each `agent_message_chunk` with `content.type == 'text'` adds its text
  /// to this stream. Unknown `sessionUpdate` types do not emit to this stream
  /// (output boundary — only committed assistant text reaches the app).
  Stream<String> get onUpdate => _updateController.stream;

  /// Sets the permission policy callback for `session/request_permission`.
  void setPermissionPolicy(PermissionPolicy policy) {
    _permissionPolicy = policy;
  }

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
  /// [cwd] must be an absolute path — non-absolute values are rejected
  /// client-side with an [ArgumentError] before any message is sent.
  ///
  /// [additionalDirectories] and [mcpServers] must be empty (the ACP bridge
  /// rejects non-empty values with -32602). They are accepted as parameters
  /// so the client can surface the server error in tests.
  Future<SessionNewResult> newSession(
    String cwd, {
    List<String> additionalDirectories = const [],
    List<Map<String, dynamic>> mcpServers = const [],
  }) async {
    // Client-side validation: cwd must be absolute (ACP contract).
    if (!File(cwd).isAbsolute) {
      throw ArgumentError('cwd must be an absolute path');
    }

    final params = SessionNewParams(
      cwd: cwd,
      additionalDirectories: additionalDirectories,
      mcpServers: mcpServers,
    );

    // Include additionalDirectories in the wire payload so the server can
    // reject it with -32602. The toJson() method omits additionalDirectories
    // (it's always empty in production), so we add it here when non-empty.
    final wireParams = params.toJson();
    if (additionalDirectories.isNotEmpty) {
      wireParams['additionalDirectories'] = additionalDirectories;
    }

    final result = await _call('session/new', wireParams);
    return SessionNewResult.fromJson(result);
  }

  /// Sends a `session/prompt` request.
  ///
  /// [sessionId] must be from a prior [newSession] call.
  /// [text] is the prompt text (sent as a single text block).
  ///
  /// Enforces DP-4 (single in-flight per session): if a prompt is already
  /// in-flight for [sessionId], throws [StateError] before sending.
  Future<SessionPromptResult> prompt(String sessionId, String text) async {
    // DP-4: single in-flight per session — client-side guard.
    if (_inflightSessions.contains(sessionId)) {
      throw StateError('a prompt is already in flight for this session');
    }

    _inflightSessions.add(sessionId);

    try {
      final result = await _call(
        'session/prompt',
        SessionPromptParams(
          sessionId: sessionId,
          prompt: [PromptTextBlock(text)],
        ).toJson(),
      );
      return SessionPromptResult.fromJson(result);
    } finally {
      // Remove from in-flight set on both success and error.
      _inflightSessions.remove(sessionId);
    }
  }

  /// Sends a `session/cancel` notification (no response expected).
  ///
  /// Cancels the in-flight prompt for [sessionId]. The pending prompt
  /// settles with `stopReason: "cancelled"`. Unknown session ids are
  /// no-ops (no error).
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

  /// Closes the transport and stream controllers (signals EOF to subprocess).
  Future<void> close() async {
    await _subscription?.cancel();
    await _updateController.close();
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
  ///   and process for text aggregation
  /// - (c) server request: has `id` + `method` → dispatch to handler
  void _handleMessage(Map<String, dynamic> message) {
    final hasId = message.containsKey('id');
    final hasMethod = message.containsKey('method');

    if (hasId && !hasMethod) {
      // (a) Response — complete the pending future.
      _handleResponse(message);
    } else if (hasMethod && !hasId) {
      // (b) Notification — process and dispatch.
      final notification = JsonRpcNotification.fromJson(message);
      _handleNotification(notification);
    } else if (hasId && hasMethod) {
      // (c) Server request — dispatch to handler and send response.
      _handleServerRequest(message);
    }
  }

  void _handleResponse(Map<String, dynamic> message) {
    // Wire-boundary validation: JSON-RPC 2.0 permits string/number/null ids.
    // We only correlate integer ids (DSH uses integers); silently drop others
    // so a malformed server response cannot crash the stream listener.
    final id = message['id'];
    if (id is! int) {
      return;
    }
    final completer = _pending.remove(id);
    if (completer == null) {
      // No pending request for this id — ignore (stale or duplicate).
      return;
    }

    if (message.containsKey('error')) {
      try {
        final error = JsonRpcError.fromJson(
          message['error'] as Map<String, dynamic>,
        );
        completer.completeError(
          AcpRpcException(error.code, error.message),
        );
      } catch (e) {
        completer.completeError(AcpRpcException(-32603, e.toString()));
      }
    } else {
      final result = message['result'] as Map<String, dynamic>? ?? {};
      completer.complete(result);
    }
  }

  /// Processes a notification: extracts text from `agent_message_chunk`
  /// for the [onUpdate] stream, then dispatches to [onNotification].
  void _handleNotification(JsonRpcNotification notification) {
    if (notification.method == 'session/update' && notification.params != null) {
      _processSessionUpdate(notification.params!);
    }
    // Always dispatch raw notification to the handler.
    onNotification?.call(notification);
  }

  /// Extracts text from a `session/update` notification's `agent_message_chunk`
  /// and adds it to the [onUpdate] stream.
  ///
  /// Unknown `sessionUpdate` types are ignored (output boundary — only
  /// committed assistant text reaches the app).
  void _processSessionUpdate(Map<String, dynamic> params) {
    try {
      final updateParams = SessionUpdateParams.fromJson(params);
      if (updateParams.update.sessionUpdate == 'agent_message_chunk' &&
          updateParams.update.content.type == 'text') {
        _updateController.add(updateParams.update.content.text);
      }
      // Unknown sessionUpdate types: ignore (output boundary).
    } on Exception {
      // Malformed update — ignore gracefully (untrusted input from server).
    }
  }

  Future<void> _handleServerRequest(Map<String, dynamic> message) async {
    // Wire-boundary defense: parse failures (non-integer id, malformed
    // method/params) must not become unhandled async errors or hang the
    // server. We send a JSON-RPC error response when id is recoverable,
    // otherwise drop silently.
    int? id;
    try {
      final rawId = message['id'];
      if (rawId is! int) {
        return;
      }
      id = rawId;
      final request = JsonRpcRequest.fromJson(message);

      // Route session/request_permission through the policy hook.
      if (request.method == 'session/request_permission' &&
          request.params != null) {
        await _handlePermissionRequest(request);
        return;
      }

      // Other server requests: send empty result response.
      await sendResponse(request.id, <String, dynamic>{});
    } catch (e) {
      // Best-effort error response — id may be null if the parse failed
      // before assignment; in that case the server's request is dropped.
      if (id != null) {
        try {
          await _transport.send({
            'jsonrpc': '2.0',
            'id': id,
            'error': {'code': -32603, 'message': e.toString()},
          });
        } catch (_) {
          // Transport closed — nothing more we can do.
        }
      }
    }
  }

  /// Handles a `session/request_permission` server request via the policy hook.
  ///
  /// If no policy is set, defaults to `reject-once` (default deny). Any
  /// parse failure or policy-callback throw also defaults to `reject-once`
  /// (safe default per AGENTS.md: unknown conditions always deny).
  Future<void> _handlePermissionRequest(JsonRpcRequest request) async {
    PermissionOutcome outcome;
    try {
      final params = RequestPermissionParams.fromJson(request.params!);
      outcome = _permissionPolicy?.call(params) ??
          const PermissionOutcome.selected('reject-once');
    } catch (_) {
      // Parse failure or policy throw → safe default: reject-once.
      outcome = const PermissionOutcome.selected('reject-once');
    }

    await sendResponse(request.id, {'outcome': outcome.toJson()});
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
