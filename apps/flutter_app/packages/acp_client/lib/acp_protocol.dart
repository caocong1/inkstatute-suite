/// JSON-RPC 2.0 message types for ACP over stdio.
///
/// ACP uses newline-delimited JSON (NDJSON) framing. Each message is a
/// JSON-RPC 2.0 object: a request (id + method), a response (id + result/error),
/// or a notification (method, no id).
///
/// Protocol version: 1 (verified from `@agentclientprotocol/sdk` schema).
library;

/// ACP protocol version constant.
///
/// Verified from `@agentclientprotocol/sdk/dist/schema/index.js`:
/// `PROTOCOL_VERSION = 1`.
const int protocolVersion = 1;

/// JSON-RPC 2.0 request (client → server or server → client).
///
/// Has `id`, `method`, and optional `params`.
class JsonRpcRequest {
  /// Creates a JSON-RPC request.
  JsonRpcRequest({
    required this.id,
    required this.method,
    this.params,
  });

  /// Parses a JSON-RPC request from a decoded JSON map.
  factory JsonRpcRequest.fromJson(Map<String, dynamic> json) {
    return JsonRpcRequest(
      id: json['id'] as int,
      method: json['method'] as String,
      params: json['params'] as Map<String, dynamic>?,
    );
  }

  /// Request id (integer for client requests).
  final int id;

  /// Method name (e.g. `initialize`, `session/new`).
  final String method;

  /// Optional parameters.
  final Map<String, dynamic>? params;

  /// Serializes to a JSON-RPC map.
  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{
      'jsonrpc': '2.0',
      'id': id,
      'method': method,
    };
    if (params != null) {
      map['params'] = params;
    }
    return map;
  }
}

/// JSON-RPC 2.0 response (server → client for a prior request).
///
/// Has `id` and either `result` or `error`.
class JsonRpcResponse {
  /// Creates a JSON-RPC response with a result.
  JsonRpcResponse({required this.id, this.result, this.error})
      : assert(
          (result != null) != (error != null),
          'Exactly one of result or error must be non-null',
        );

  /// Parses a JSON-RPC response from a decoded JSON map.
  factory JsonRpcResponse.fromJson(Map<String, dynamic> json) {
    return JsonRpcResponse(
      id: json['id'] as int,
      result: json['result'] as Map<String, dynamic>?,
      error: json['error'] != null
          ? JsonRpcError.fromJson(json['error'] as Map<String, dynamic>)
          : null,
    );
  }

  /// Request id this response corresponds to.
  final int id;

  /// Result payload (present on success).
  final Map<String, dynamic>? result;

  /// Error payload (present on failure).
  final JsonRpcError? error;

  /// Whether this response carries an error.
  bool get isError => error != null;

  /// Serializes to a JSON-RPC map.
  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{'jsonrpc': '2.0', 'id': id};
    if (error != null) {
      map['error'] = error!.toJson();
    } else {
      map['result'] = result;
    }
    return map;
  }
}

/// JSON-RPC 2.0 notification (no id, no response expected).
///
/// Has `method` and optional `params`.
class JsonRpcNotification {
  /// Creates a JSON-RPC notification.
  JsonRpcNotification({required this.method, this.params});

  /// Parses a JSON-RPC notification from a decoded JSON map.
  factory JsonRpcNotification.fromJson(Map<String, dynamic> json) {
    return JsonRpcNotification(
      method: json['method'] as String,
      params: json['params'] as Map<String, dynamic>?,
    );
  }

  /// Method name (e.g. `session/update`).
  final String method;

  /// Optional parameters.
  final Map<String, dynamic>? params;

  /// Serializes to a JSON-RPC map.
  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{'jsonrpc': '2.0', 'method': method};
    if (params != null) {
      map['params'] = params;
    }
    return map;
  }
}

/// JSON-RPC 2.0 error object.
class JsonRpcError {
  /// Creates a JSON-RPC error.
  JsonRpcError({required this.code, required this.message, this.data});

  /// Parses a JSON-RPC error from a decoded JSON map.
  factory JsonRpcError.fromJson(Map<String, dynamic> json) {
    return JsonRpcError(
      code: json['code'] as int,
      message: json['message'] as String,
      data: json['data'],
    );
  }

  /// Error code (e.g. -32602 for invalid params).
  final int code;

  /// Human-readable error message.
  final String message;

  /// Optional additional data.
  final dynamic data;

  /// Serializes to a JSON-RPC error map.
  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{'code': code, 'message': message};
    if (data != null) {
      map['data'] = data;
    }
    return map;
  }
}
