/// Output boundary for the chat UI (APP-05).
///
/// Filters ACP session updates to ensure only committed assistant text
/// reaches the user interface. All DSH meta/system noise is blocked.
/// Maps exceptions to user-readable error messages.
library;

import 'dart:async';

import 'package:flutter_app/chat/chat_models.dart';
import 'package:acp_client/acp_client.dart';

/// Filters and transforms ACP updates for UI consumption.
///
/// The output boundary is the single enforcement point that prevents
/// non-assistant noise (meta, system, tool activity) from reaching
/// the user interface.
class OutputBoundary {
  const OutputBoundary._();

  /// Returns true if the session update should be rendered in the UI.
  ///
  /// Only `agent_message_chunk` with `content.type == 'text'` passes
  /// the boundary. All other update types are filtered out:
  /// - meta updates (tool activity, internal state)
  /// - system notifications
  /// - non-text content types
  static bool shouldRender(SessionUpdate update) {
    if (update.sessionUpdate != 'agent_message_chunk') return false;
    if (update.content.type != 'text') return false;
    return true;
  }

  /// Extracts the committed text from a renderable update.
  ///
  /// Returns null if the update should not be rendered.
  static String? extractText(SessionUpdate update) {
    if (!shouldRender(update)) return null;
    return update.content.text;
  }
}

/// Maps exceptions to user-readable system error messages.
///
/// Raw stack traces are never included in the user message — they
/// are logged locally only via [ErrorMapper.logStackTrace].
class ErrorMapper {
  const ErrorMapper._();

  /// Maps an exception to a [SystemErrorMessage] with a user-readable
  /// message in Chinese.
  static SystemErrorMessage map(Exception error) {
    final errorString = error.toString();

    if (error is TimeoutException) {
      return SystemErrorMessage(
        errorType: ErrorType.timeout,
        userMessage: ErrorType.timeout.defaultMessage,
        timestamp: DateTime.now(),
      );
    }

    // Process/connection errors → engine not started
    if (errorString.contains('ProcessException') ||
        errorString.contains('Connection refused') ||
        errorString.contains('connection refused') ||
        errorString.contains('Failed to spawn') ||
        errorString.contains('No such file or directory')) {
      return SystemErrorMessage(
        errorType: ErrorType.engineNotStarted,
        userMessage: ErrorType.engineNotStarted.defaultMessage,
        timestamp: DateTime.now(),
      );
    }

    // Rate limiting
    if (errorString.contains('429') ||
        errorString.contains('rate limit') ||
        errorString.contains('Rate limit') ||
        errorString.contains('too many requests')) {
      return SystemErrorMessage(
        errorType: ErrorType.rateLimited,
        userMessage: ErrorType.rateLimited.defaultMessage,
        timestamp: DateTime.now(),
      );
    }

    // Authentication
    if (errorString.contains('401') ||
        errorString.contains('Unauthorized') ||
        errorString.contains('unauthorized') ||
        errorString.contains('authentication') ||
        errorString.contains('Authentication')) {
      return SystemErrorMessage(
        errorType: ErrorType.authFailed,
        userMessage: ErrorType.authFailed.defaultMessage,
        timestamp: DateTime.now(),
      );
    }

    // Default: unknown error
    return SystemErrorMessage(
      errorType: ErrorType.unknown,
      userMessage: ErrorType.unknown.defaultMessage,
      timestamp: DateTime.now(),
    );
  }

  /// Logs a stack trace to local storage only.
  ///
  /// This never returns the stack trace to the UI. In production,
  /// this writes to a local log file. In tests, it's a no-op.
  static void logStackTrace(Exception error, StackTrace stack) {
    // Local logging only — never exposed to UI.
    // Production implementation writes to a log file in the app data dir.
    // For now, this is a no-op stub; Phase 119 (packaging) will wire
    // the actual file logger.
  }
}
