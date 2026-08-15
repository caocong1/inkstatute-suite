/// Chat data models for the InkStatute session UI.
///
/// Defines the message hierarchy, citation/review/clarify structures,
/// and session container used by the chat UI (APP-02).
library;

/// A chat message in a session. Sealed hierarchy — exactly one subtype
/// per message kind.
sealed class ChatMessage {
  /// Creates a chat message.
  const ChatMessage({required this.timestamp});

  /// When the message was created.
  final DateTime timestamp;
}

/// A user-submitted prompt message.
final class UserMessage extends ChatMessage {
  /// Creates a user message.
  const UserMessage({required this.text, required super.timestamp});

  /// The user's prompt text.
  final String text;
}

/// An assistant response message with parsed citations and markers.
final class AssistantMessage extends ChatMessage {
  /// Creates an assistant message.
  const AssistantMessage({
    required this.text,
    required super.timestamp,
    this.citations = const [],
    this.humanReviewMarkers = const [],
    this.clarifyRequests = const [],
  });

  /// The assistant's response text (markers removed).
  final String text;

  /// Citations extracted from the response.
  final List<Citation> citations;

  /// Human review markers extracted from the response.
  final List<HumanReviewMarker> humanReviewMarkers;

  /// Clarification requests extracted from the response.
  final List<ClarifyRequest> clarifyRequests;
}

/// An approval card message for a tool permission request.
final class ApprovalMessage extends ChatMessage {
  /// Creates an approval message.
  const ApprovalMessage({
    required this.toolCallId,
    required this.toolName,
    required this.status,
    required super.timestamp,
  });

  /// The tool call ID from the ACP permission request.
  final String toolCallId;

  /// The tool name (e.g. "terminal", "execute_code").
  final String toolName;

  /// Current approval status.
  final ApprovalStatus status;
}

/// A clarification card message.
final class ClarifyMessage extends ChatMessage {
  /// Creates a clarification message.
  const ClarifyMessage({
    required this.clarifyText,
    required super.timestamp,
    this.userResponse,
  });

  /// The clarification question from `[CLARIFY: …]`.
  final String clarifyText;

  /// The user's supplementary response (null if not yet answered).
  final String? userResponse;
}

/// A system error message shown to the user.
final class SystemErrorMessage extends ChatMessage {
  /// Creates a system error message.
  const SystemErrorMessage({
    required this.errorType,
    required this.userMessage,
    required super.timestamp,
  });

  /// The categorized error type.
  final ErrorType errorType;

  /// User-readable error message in Chinese.
  final String userMessage;
}

/// A citation extracted from assistant text.
class Citation {
  /// Creates a citation.
  const Citation({
    required this.source,
    required this.citationType,
    required this.text,
  });

  /// The citation source identifier.
  final String source;

  /// The citation verification state.
  final CitationType citationType;

  /// The cited text or context.
  final String text;
}

/// Citation verification state (three-state per PRD).
enum CitationType {
  /// Verified by citation audit.
  verified('verified', '已验证'),

  /// Retrieved but not verified.
  retrieved('retrieved', '已检索'),

  /// Unverified — no source backing.
  unverified('unverified', '未验证');

  const CitationType(this.wire, this.displayName);

  /// Wire representation.
  final String wire;

  /// Chinese display name.
  final String displayName;

  /// Parses from wire string.
  static CitationType fromString(String value) {
    return CitationType.values.firstWhere(
      (c) => c.wire == value,
      orElse: () => CitationType.unverified,
    );
  }
}

/// A human review marker from `[HUMAN_REVIEW: …]`.
class HumanReviewMarker {
  /// Creates a human review marker.
  const HumanReviewMarker({required this.text});

  /// The review note text.
  final String text;
}

/// A clarification request from `[CLARIFY: …]`.
class ClarifyRequest {
  /// Creates a clarification request.
  const ClarifyRequest({required this.text});

  /// The clarification question.
  final String text;
}

/// Approval status for a permission request.
enum ApprovalStatus {
  /// Awaiting user decision.
  pending('pending'),

  /// User approved (allow-once).
  approved('approved'),

  /// User rejected (reject-once).
  rejected('rejected');

  const ApprovalStatus(this.wire);

  /// Wire representation.
  final String wire;
}

/// Error type categories for user-facing error messages (APP-05).
enum ErrorType {
  /// Engine process not started or connection refused.
  engineNotStarted('引擎未启动，请检查安装'),

  /// API rate limit hit.
  rateLimited('请求过于频繁，请稍后重试'),

  /// Authentication failure.
  authFailed('鉴权失败，请检查 API 密钥'),

  /// Request timeout.
  timeout('请求超时，请重试'),

  /// Unknown error.
  unknown('发生未知错误');

  const ErrorType(this.defaultMessage);

  /// Default user-readable message in Chinese.
  final String defaultMessage;
}

/// Processing status of the current session.
enum MessageStatus {
  /// Idle — no in-flight request.
  idle,

  /// Processing — prompt sent, awaiting response.
  processing,

  /// Completed — response received.
  completed,

  /// Cancelled — user cancelled the in-flight request.
  cancelled,

  /// Error — an error occurred.
  error,
}

/// A chat session containing messages and metadata.
class ChatSession {
  /// Creates a chat session.
  const ChatSession({
    required this.id,
    required this.providerName,
    required this.modelConfig,
    required this.title,
    required this.createdAt,
    this.messages = const [],
  });

  /// Unique session identifier.
  final String id;

  /// LLM provider display name (e.g. "DeepSeek").
  final String providerName;

  /// Model configuration (e.g. "deepseek-v4-flash").
  final String modelConfig;

  /// Session title.
  final String title;

  /// When the session was created.
  final DateTime createdAt;

  /// Messages in the session.
  final List<ChatMessage> messages;
}
