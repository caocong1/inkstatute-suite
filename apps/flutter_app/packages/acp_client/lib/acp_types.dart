/// ACP v1 method parameter and result types.
///
/// These types cover the ACP protocol methods used by the InkStatute V4 client.
/// All types are plain Dart classes with `fromJson` / `toJson` factories.
///
/// Protocol version: 1 (see [protocolVersion] in `acp_protocol.dart`).
library;

import 'acp_protocol.dart';

export 'acp_protocol.dart' show protocolVersion;

// ---------------------------------------------------------------------------
// initialize
// ---------------------------------------------------------------------------

/// Parameters for the `initialize` method.
///
/// Sent by the client to negotiate protocol version and advertise capabilities.
class InitializeParams {
  /// Creates initialize parameters.
  const InitializeParams();

  /// Serializes to a JSON map for the `initialize` request.
  Map<String, dynamic> toJson() {
    return {
      'protocolVersion': protocolVersion,
      'clientCapabilities': <String, dynamic>{},
    };
  }
}

/// Agent info advertised in the `initialize` result.
class AgentInfo {
  /// Creates agent info.
  const AgentInfo({required this.name, required this.version});

  /// Parses agent info from a decoded JSON map.
  factory AgentInfo.fromJson(Map<String, dynamic> json) {
    return AgentInfo(
      name: json['name'] as String,
      version: json['version'] as String,
    );
  }

  /// Agent name (e.g. `deepseek-harness-acp`).
  final String name;

  /// Agent version string.
  final String version;
}

/// Prompt capabilities advertised in the `initialize` result.
class PromptCapabilities {
  /// Creates prompt capabilities.
  const PromptCapabilities({
    required this.image,
    required this.audio,
    required this.embeddedContext,
  });

  /// Parses prompt capabilities from a decoded JSON map.
  factory PromptCapabilities.fromJson(Map<String, dynamic> json) {
    return PromptCapabilities(
      image: json['image'] as bool,
      audio: json['audio'] as bool,
      embeddedContext: json['embeddedContext'] as bool,
    );
  }

  /// Whether image content is supported.
  final bool image;

  /// Whether audio content is supported.
  final bool audio;

  /// Whether embedded context is supported.
  final bool embeddedContext;
}

/// Agent capabilities advertised in the `initialize` result.
class AgentCapabilities {
  /// Creates agent capabilities.
  const AgentCapabilities({required this.promptCapabilities});

  /// Parses agent capabilities from a decoded JSON map.
  factory AgentCapabilities.fromJson(Map<String, dynamic> json) {
    return AgentCapabilities(
      promptCapabilities: PromptCapabilities.fromJson(
        json['promptCapabilities'] as Map<String, dynamic>,
      ),
    );
  }

  /// Prompt capabilities.
  final PromptCapabilities promptCapabilities;
}

/// Result of the `initialize` method.
class InitializeResult {
  /// Creates an initialize result.
  const InitializeResult({
    required this.protocolVersion,
    required this.agentInfo,
    required this.agentCapabilities,
    required this.authMethods,
  });

  /// Parses an initialize result from a decoded JSON map.
  factory InitializeResult.fromJson(Map<String, dynamic> json) {
    return InitializeResult(
      protocolVersion: json['protocolVersion'] as int,
      agentInfo: AgentInfo.fromJson(
        json['agentInfo'] as Map<String, dynamic>,
      ),
      agentCapabilities: AgentCapabilities.fromJson(
        json['agentCapabilities'] as Map<String, dynamic>,
      ),
      authMethods: (json['authMethods'] as List<dynamic>).cast<String>(),
    );
  }

  /// Negotiated protocol version.
  final int protocolVersion;

  /// Agent info.
  final AgentInfo agentInfo;

  /// Agent capabilities.
  final AgentCapabilities agentCapabilities;

  /// Authentication methods (empty for automation-only servers).
  final List<String> authMethods;
}

// ---------------------------------------------------------------------------
// session/new
// ---------------------------------------------------------------------------

/// Parameters for the `session/new` method.
///
/// `cwd` must be an absolute path. `additionalDirectories` and `mcpServers`
/// must be empty (non-empty values are rejected by the ACP bridge).
class SessionNewParams {
  /// Creates session/new parameters.
  const SessionNewParams({
    required this.cwd,
    this.additionalDirectories = const [],
    this.mcpServers = const [],
  });

  /// Serializes to a JSON map for the `session/new` request.
  Map<String, dynamic> toJson() {
    return {
      'cwd': cwd,
      'mcpServers': mcpServers,
    };
  }

  /// Absolute working directory path.
  final String cwd;

  /// Additional directory roots (must be empty for V4 — server rejects
  /// non-empty values with -32602).
  final List<String> additionalDirectories;

  /// MCP server configurations (must be empty for V4).
  final List<Map<String, dynamic>> mcpServers;
}

/// Result of the `session/new` method.
class SessionNewResult {
  /// Creates a session/new result.
  const SessionNewResult({required this.sessionId});

  /// Parses a session/new result from a decoded JSON map.
  factory SessionNewResult.fromJson(Map<String, dynamic> json) {
    return SessionNewResult(sessionId: json['sessionId'] as String);
  }

  /// Unique session identifier.
  final String sessionId;
}

// ---------------------------------------------------------------------------
// session/prompt
// ---------------------------------------------------------------------------

/// A text block in a prompt.
class PromptTextBlock {
  /// Creates a text block.
  const PromptTextBlock(this.text);

  /// Serializes to a JSON map.
  Map<String, dynamic> toJson() {
    return {'type': 'text', 'text': text};
  }

  /// The text content.
  final String text;
}

/// Parameters for the `session/prompt` method.
class SessionPromptParams {
  /// Creates session/prompt parameters.
  const SessionPromptParams({required this.sessionId, required this.prompt});

  /// Serializes to a JSON map for the `session/prompt` request.
  Map<String, dynamic> toJson() {
    return {
      'sessionId': sessionId,
      'prompt': prompt.map((b) => b.toJson()).toList(),
    };
  }

  /// Session id to prompt.
  final String sessionId;

  /// Prompt content blocks (text only for V4).
  final List<PromptTextBlock> prompt;
}

/// Stop reason for a completed prompt.
enum StopReason {
  /// Agent finished its turn normally.
  endTurn('end_turn'),

  /// Prompt was cancelled.
  cancelled('cancelled'),

  /// Token limit reached.
  maxTokens('max_tokens');

  const StopReason(this.wire);

  /// Wire representation.
  final String wire;

  /// Parses a stop reason from its wire string.
  static StopReason fromString(String value) {
    return StopReason.values.firstWhere(
      (r) => r.wire == value,
      orElse: () => throw ArgumentError('Unknown stop reason: $value'),
    );
  }
}

/// Result of the `session/prompt` method.
class SessionPromptResult {
  /// Creates a session/prompt result.
  const SessionPromptResult({required this.stopReason});

  /// Parses a session/prompt result from a decoded JSON map.
  factory SessionPromptResult.fromJson(Map<String, dynamic> json) {
    return SessionPromptResult(
      stopReason: StopReason.fromString(json['stopReason'] as String),
    );
  }

  /// Why the prompt stopped.
  final StopReason stopReason;
}

// ---------------------------------------------------------------------------
// session/cancel
// ---------------------------------------------------------------------------

/// Parameters for the `session/cancel` notification.
class SessionCancelParams {
  /// Creates session/cancel parameters.
  const SessionCancelParams({required this.sessionId});

  /// Serializes to a JSON map for the `session/cancel` notification.
  Map<String, dynamic> toJson() {
    return {'sessionId': sessionId};
  }

  /// Session id to cancel.
  final String sessionId;
}

// ---------------------------------------------------------------------------
// session/update (notification, server → client)
// ---------------------------------------------------------------------------

/// Content type for a session update chunk.
class SessionUpdateContent {
  /// Creates session update content.
  const SessionUpdateContent({required this.type, required this.text});

  /// Parses session update content from a decoded JSON map.
  factory SessionUpdateContent.fromJson(Map<String, dynamic> json) {
    return SessionUpdateContent(
      type: json['type'] as String,
      text: json['text'] as String,
    );
  }

  /// Content type (always `text` for committed assistant messages).
  final String type;

  /// Text content.
  final String text;
}

/// Parameters for the `session/update` notification.
class SessionUpdateParams {
  /// Creates session/update parameters.
  const SessionUpdateParams({required this.sessionId, required this.update});

  /// Parses session/update parameters from a decoded JSON map.
  factory SessionUpdateParams.fromJson(Map<String, dynamic> json) {
    return SessionUpdateParams(
      sessionId: json['sessionId'] as String,
      update: SessionUpdate.fromJson(json['update'] as Map<String, dynamic>),
    );
  }

  /// Session id.
  final String sessionId;

  /// Update payload.
  final SessionUpdate update;
}

/// The update payload of a `session/update` notification.
class SessionUpdate {
  /// Creates a session update.
  const SessionUpdate({required this.sessionUpdate, required this.content});

  /// Parses a session update from a decoded JSON map.
  factory SessionUpdate.fromJson(Map<String, dynamic> json) {
    return SessionUpdate(
      sessionUpdate: json['sessionUpdate'] as String,
      content: SessionUpdateContent.fromJson(
        json['content'] as Map<String, dynamic>,
      ),
    );
  }

  /// Update type (e.g. `agent_message_chunk`).
  final String sessionUpdate;

  /// Content of the update.
  final SessionUpdateContent content;
}

// ---------------------------------------------------------------------------
// session/request_permission (server → client request)
// ---------------------------------------------------------------------------

/// A permission option offered by the server.
class PermissionOption {
  /// Creates a permission option.
  const PermissionOption({
    required this.optionId,
    required this.name,
    required this.kind,
  });

  /// Parses a permission option from a decoded JSON map.
  factory PermissionOption.fromJson(Map<String, dynamic> json) {
    return PermissionOption(
      optionId: json['optionId'] as String,
      name: json['name'] as String,
      kind: json['kind'] as String,
    );
  }

  /// Option identifier (e.g. `allow-once`, `reject-once`).
  final String optionId;

  /// Human-readable name.
  final String name;

  /// Option kind (e.g. `allow_once`, `reject_once`).
  final String kind;
}

/// Parameters for `session/request_permission` (server → client).
class RequestPermissionParams {
  /// Creates request_permission parameters.
  const RequestPermissionParams({
    required this.sessionId,
    required this.toolCallId,
    required this.options,
    this.toolName,
  });

  /// Parses request_permission parameters from a decoded JSON map.
  ///
  /// The `toolCall` object may carry an optional `toolName` field that
  /// indicates the tool kind (e.g. `terminal`, `execute_code`). The ACP
  /// protocol itself only sends `allow-once`/`reject-once` options — the
  /// tool kind is implicit in the approval request context (per RESEARCH.md
  /// §Approval Security Three-State nuance).
  factory RequestPermissionParams.fromJson(Map<String, dynamic> json) {
    final toolCall = json['toolCall'] as Map<String, dynamic>;
    return RequestPermissionParams(
      sessionId: json['sessionId'] as String,
      toolCallId: toolCall['toolCallId'] as String,
      toolName: toolCall['toolName'] as String?,
      options: (json['options'] as List<dynamic>)
          .map((e) => PermissionOption.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  /// Session id.
  final String sessionId;

  /// Tool call id that triggered the permission request.
  final String toolCallId;

  /// Optional tool name that indicates the permission kind.
  ///
  /// The ACP `session/request_permission` message does not formally carry
  /// tool-kind information — the kind is inferred from the approval request
  /// context. The mock server includes this field for testing; production
  /// code infers the kind from the tool call metadata or session context.
  final String? toolName;

  /// Available permission options.
  final List<PermissionOption> options;
}

/// Outcome of a permission request.
class PermissionOutcome {
  /// Creates a selected outcome.
  const PermissionOutcome.selected(this.optionId) : outcome = 'selected';

  /// Creates a cancelled outcome.
  const PermissionOutcome.cancelled()
      : optionId = null,
        outcome = 'cancelled';

  /// Outcome type (`selected` or `cancelled`).
  final String outcome;

  /// Selected option id (null if cancelled).
  final String? optionId;

  /// Serializes to a JSON map for the permission response.
  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{'outcome': outcome};
    if (optionId != null) {
      map['optionId'] = optionId;
    }
    return map;
  }
}

// ---------------------------------------------------------------------------
// Permission kind classification
// ---------------------------------------------------------------------------

/// Classification of a permission request by the tool kind that triggered it.
///
/// The ACP `session/request_permission` options only carry `allow-once`/
/// `reject-once` — the tool kind is implicit in the approval request context
/// (per RESEARCH.md §Approval Security Three-State nuance). The app infers
/// the kind from the tool call metadata or session context and passes it to
/// [ApprovalPolicy.evaluate].
enum PermissionKind {
  /// Terminal (bash/shell) tool — renders a user card.
  terminal('terminal'),

  /// Code execution tool — renders a user card.
  executeCode('execute_code'),

  /// Unrecognized tool kind — always denied, never shown to user.
  unknown('unknown');

  const PermissionKind(this.wire);

  /// Wire representation.
  final String wire;

  /// Parses a permission kind from a tool kind string.
  ///
  /// Returns [PermissionKind.unknown] for `null` or unrecognized values.
  /// This is the safe default — unknown kinds are always denied.
  static PermissionKind fromString(String? value) {
    if (value == null) return PermissionKind.unknown;
    return PermissionKind.values.firstWhere(
      (k) => k.wire == value,
      orElse: () => PermissionKind.unknown,
    );
  }
}

// ---------------------------------------------------------------------------
// Approval decision (three-state)
// ---------------------------------------------------------------------------

/// Sealed class representing the decision made by [ApprovalPolicy.evaluate].
///
/// There are exactly two subtypes:
/// - [AutoDeny]: The permission is denied immediately (reject-once). Used for
///   unknown kinds and for known kinds when no UI is connected (safe default).
/// - [RenderCard]: The permission request should be rendered as a user-facing
///   approval card. The decision is deferred to the user UI.
///
/// There is deliberately NO `AutoAllow` subtype — no permission kind is ever
/// auto-approved. Every known kind requires explicit user interaction.
sealed class ApprovalDecision {
  const ApprovalDecision();
}

/// The permission is denied immediately (reject-once).
///
/// Used for:
/// - Unknown permission kinds (always denied, never shown to user)
/// - Known kinds when no UI is connected (safe default)
final class AutoDeny extends ApprovalDecision {
  const AutoDeny();
}

/// The permission request should be rendered as a user-facing approval card.
///
/// The decision is deferred to the user UI. The user can then allow-once,
/// reject-once, or dismiss/cancel the card.
final class RenderCard extends ApprovalDecision {
  const RenderCard();
}

// ---------------------------------------------------------------------------
// Permission policy hook
// ---------------------------------------------------------------------------

/// Policy callback for `session/request_permission` server requests.
///
/// The app sets this on [AcpClient] to intercept permission requests from the
/// engine. The callback receives the parsed [RequestPermissionParams] and
/// returns a [PermissionOutcome]. If no policy is set, the client defaults to
/// `reject-once` (default deny).
typedef PermissionPolicy = PermissionOutcome Function(RequestPermissionParams);
