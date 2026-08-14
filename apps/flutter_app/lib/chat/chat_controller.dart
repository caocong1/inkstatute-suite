/// Chat controller connecting ACP client to the chat UI (APP-02, APP-05).
///
/// Manages session state, streams ACP updates through the output boundary,
/// parses assistant text, handles approvals/clarifications, and persists
/// messages to the local session store.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:acp_client/acp_client.dart';
import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/chat/error_mapper.dart';
import 'package:flutter_app/chat/text_parser.dart';
import 'package:flutter_app/chat/session_repository.dart';

/// Controller for the chat session, bridging ACP and UI.
class ChatController extends ChangeNotifier {
  /// Creates a chat controller.
  ChatController({
    required this._client,
    required SessionRepository repository,
    required this._sessionId,
    required this._practiceArea,
  })  : _repo = repository {
    _updateSubscription = _client.onUpdate.listen(_handleUpdate);
  }

  final AcpClient _client;
  final SessionRepository _repo;
  final String _sessionId;
  final String _practiceArea;

  StreamSubscription<String>? _updateSubscription;
  final StringBuffer _pendingText = StringBuffer();

  /// Current messages in the session.
  final List<ChatMessage> _messages = [];

  /// Read-only access to messages.
  List<ChatMessage> get messages => List.unmodifiable(_messages);

  /// Current processing status.
  MessageStatus _status = MessageStatus.idle;

  /// Current processing status.
  MessageStatus get status => _status;

  /// Practice area for this session.
  String get practiceArea => _practiceArea;

  /// Session ID.
  String get sessionId => _sessionId;

  /// Whether input is currently disabled (during processing).
  bool get inputDisabled => _status == MessageStatus.processing;

  /// Handles an ACP update chunk through the output boundary.
  void _handleUpdate(String chunk) {
    // Only committed assistant text reaches here (filtered by AcpClient).
    _pendingText.write(chunk);
    notifyListeners();
  }

  /// Sends a prompt to the engine.
  ///
  /// Rejects if a prompt is already in-flight (single in-flight enforcement).
  Future<void> sendPrompt(String text) async {
    if (_status == MessageStatus.processing) {
      throw StateError('A prompt is already in-flight');
    }

    final userMsg = UserMessage(text: text, timestamp: DateTime.now());
    _messages.add(userMsg);
    _status = MessageStatus.processing;
    _pendingText.clear();
    notifyListeners();

    try {
      await _repo.addMessage(_sessionId, userMsg);
      await _client.prompt(_sessionId, text);

      // After prompt completes, finalize the assistant message
      final rawText = _pendingText.toString();
      if (rawText.isNotEmpty) {
        final parsed = TextParser.parse(rawText);
        final assistantMsg = AssistantMessage(
          text: parsed.cleanText,
          timestamp: DateTime.now(),
          citations: parsed.citations,
          humanReviewMarkers: parsed.humanReviewMarkers,
          clarifyRequests: parsed.clarifyRequests,
        );
        _messages.add(assistantMsg);
        await _repo.addMessage(_sessionId, assistantMsg);

        // If there are clarify requests, add clarify messages
        for (final cr in parsed.clarifyRequests) {
          _messages.add(ClarifyMessage(
            clarifyText: cr.text,
            timestamp: DateTime.now(),
          ));
        }
      }

      _status = MessageStatus.completed;
    } on Exception catch (e, st) {
      ErrorMapper.logStackTrace(e, st);
      final errorMsg = ErrorMapper.map(e);
      _messages.add(errorMsg);
      _status = MessageStatus.error;
    } finally {
      notifyListeners();
    }
  }

  /// Cancels the in-flight request.
  Future<void> cancelInFlight() async {
    if (_status != MessageStatus.processing) return;

    try {
      await _client.cancel(_sessionId);
    } finally {
      _status = MessageStatus.cancelled;
      notifyListeners();
    }
  }

  /// Handles an approval decision (allow or reject).
  Future<void> handleApproval(String toolCallId, bool allow) async {
    final status =
        allow ? ApprovalStatus.approved : ApprovalStatus.rejected;
    await _repo.updateApproval(
      _sessionId,
      toolCallId,
      status,
    );

    // Update the approval message in the list
    for (var i = _messages.length - 1; i >= 0; i--) {
      final msg = _messages[i];
      if (msg is ApprovalMessage && msg.toolCallId == toolCallId) {
        _messages[i] = ApprovalMessage(
          toolCallId: msg.toolCallId,
          toolName: msg.toolName,
          status: status,
          timestamp: msg.timestamp,
        );
        break;
      }
    }
    notifyListeners();
  }

  /// Handles a clarification response by sending it as a new prompt.
  Future<void> handleClarifyResponse(String clarifyText, String userResponse) async {
    // Update the clarify message with the user's response
    for (var i = _messages.length - 1; i >= 0; i--) {
      final msg = _messages[i];
      if (msg is ClarifyMessage && msg.clarifyText == clarifyText) {
        _messages[i] = ClarifyMessage(
          clarifyText: msg.clarifyText,
          timestamp: msg.timestamp,
          userResponse: userResponse,
        );
        break;
      }
    }
    notifyListeners();

    // Submit the clarification as a new prompt
    await sendPrompt(userResponse);
  }

  @override
  void dispose() {
    _updateSubscription?.cancel();
    super.dispose();
  }
}
