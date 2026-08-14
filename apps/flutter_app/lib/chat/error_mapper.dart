/// Error mapping for user-readable error messages (APP-05).
///
/// Maps engine exceptions to [SystemErrorMessage] instances with
/// lawyer-readable Chinese text. Raw stack traces are logged locally
/// only and never exposed to the UI.
library;

import 'dart:async';

import 'package:flutter_app/chat/chat_models.dart';

/// Maps exceptions to user-readable system error messages.
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
