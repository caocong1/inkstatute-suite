/// Session repository for CRUD operations on the local session store (APP-03).
///
/// Provides methods for creating, reading, updating, deleting, and
/// exporting chat sessions with their messages, citations, and approvals.
/// Uses raw SQL via drift's QueryExecutor with raw bound parameters.
library;

import 'dart:convert';

import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/chat/session_database.dart';

/// Repository for managing chat sessions in the local database.
class SessionRepository {
  /// Creates a session repository.
  SessionRepository(this._db);

  final SessionDatabase _db;

  /// Creates a new session with its initial messages.
  Future<void> createSession(ChatSession session) async {
    await _db.exec(
      'INSERT INTO sessions (id, provider_name, model_config, title, created_at) VALUES (?, ?, ?, ?, ?)',
      [
        session.id,
        session.providerName,
        session.modelConfig,
        session.title,
        session.createdAt.millisecondsSinceEpoch,
      ],
    );

    for (var i = 0; i < session.messages.length; i++) {
      await _insertMessage(session.id, session.messages[i], i);
    }
  }

  /// Loads a session with all its messages and citations.
  Future<ChatSession?> getSession(String id) async {
    final rows = await _db.select(
      'SELECT * FROM sessions WHERE id = ?',
      [id],
    );
    if (rows.isEmpty) return null;
    final s = rows.first;
    return ChatSession(
      id: s['id'] as String,
      providerName: s['provider_name'] as String? ?? 'DeepSeek',
      modelConfig: s['model_config'] as String? ?? 'deepseek-chat',
      title: s['title'] as String,
      createdAt: DateTime.fromMillisecondsSinceEpoch(s['created_at'] as int),
      messages: await _loadMessages(id),
    );
  }

  /// Lists all sessions, optionally filtered by provider.
  Future<List<ChatSession>> listSessions({String? providerName}) async {
    List<Map<String, dynamic>> rows;
    if (providerName != null) {
      rows = await _db.select(
        'SELECT * FROM sessions WHERE provider_name = ? ORDER BY created_at DESC',
        [providerName],
      );
    } else {
      rows = await _db.select(
        'SELECT * FROM sessions ORDER BY created_at DESC',
      );
    }

    final sessions = <ChatSession>[];
    for (final row in rows) {
      sessions.add(ChatSession(
        id: row['id'] as String,
        providerName: row['provider_name'] as String? ?? 'DeepSeek',
        modelConfig: row['model_config'] as String? ?? 'deepseek-chat',
        title: row['title'] as String,
        createdAt: DateTime.fromMillisecondsSinceEpoch(row['created_at'] as int),
        messages: await _loadMessages(row['id'] as String),
      ));
    }
    return sessions;
  }

  /// Appends a message to an existing session.
  Future<void> addMessage(String sessionId, ChatMessage message) async {
    final countRows = await _db.select(
      'SELECT COUNT(*) as cnt FROM messages WHERE session_id = ?',
      [sessionId],
    );
    final sortOrder = countRows.first['cnt'] as int;
    await _insertMessage(sessionId, message, sortOrder);
  }

  /// Updates an approval status.
  Future<void> updateApproval(
    String sessionId,
    String toolCallId,
    ApprovalStatus status,
  ) async {
    await _db.exec(
      'UPDATE approvals SET status = ? WHERE session_id = ? AND tool_call_id = ?',
      [status.wire, sessionId, toolCallId],
    );
  }

  /// Deletes a session and all related records (cascade).
  Future<void> deleteSession(String id) async {
    await _db.exec(
      'DELETE FROM citations WHERE message_id IN (SELECT id FROM messages WHERE session_id = ?)',
      [id],
    );
    await _db.exec('DELETE FROM messages WHERE session_id = ?', [id]);
    await _db.exec('DELETE FROM approvals WHERE session_id = ?', [id]);
    await _db.exec('DELETE FROM sessions WHERE id = ?', [id]);
  }

  /// Exports a session as a JSON string (for privacy/data export).
  Future<String> exportSession(String id) async {
    final session = await getSession(id);
    if (session == null) return '{}';

    final messagesJson = session.messages.map((msg) {
      return switch (msg) {
        UserMessage m => {
            'role': 'user',
            'text': m.text,
            'timestamp': m.timestamp.toIso8601String(),
          },
        AssistantMessage m => {
            'role': 'assistant',
            'text': m.text,
            'timestamp': m.timestamp.toIso8601String(),
            'citations': m.citations
                .map((c) => {
                      'source': c.source,
                      'type': c.citationType.wire,
                      'text': c.text,
                    })
                .toList(),
            'humanReviewMarkers':
                m.humanReviewMarkers.map((h) => h.text).toList(),
            'clarifyRequests': m.clarifyRequests.map((c) => c.text).toList(),
          },
        ApprovalMessage m => {
            'role': 'approval',
            'toolCallId': m.toolCallId,
            'toolName': m.toolName,
            'status': m.status.wire,
            'timestamp': m.timestamp.toIso8601String(),
          },
        ClarifyMessage m => {
            'role': 'clarify',
            'clarifyText': m.clarifyText,
            'userResponse': m.userResponse,
            'timestamp': m.timestamp.toIso8601String(),
          },
        SystemErrorMessage m => {
            'role': 'error',
            'errorType': m.errorType.name,
            'userMessage': m.userMessage,
            'timestamp': m.timestamp.toIso8601String(),
          },
      };
    }).toList();

    return jsonEncode({
      'id': session.id,
      'providerName': session.providerName,
      'modelConfig': session.modelConfig,
      'title': session.title,
      'createdAt': session.createdAt.toIso8601String(),
      'messages': messagesJson,
    });
  }

  /// Lists distinct providers that have sessions.
  Future<List<String>> listProviders() async {
    final rows = await _db.select(
      'SELECT DISTINCT provider_name FROM sessions',
    );
    return rows.map((r) => r['provider_name'] as String? ?? 'DeepSeek').toList();
  }

  // -- Helpers --

  Future<List<ChatMessage>> _loadMessages(String sessionId) async {
    final msgRows = await _db.select(
      'SELECT * FROM messages WHERE session_id = ? ORDER BY sort_order',
      [sessionId],
    );

    final messages = <ChatMessage>[];
    for (final row in msgRows) {
      final role = row['role'] as String;
      final text = row['text'] as String;
      final createdAt =
          DateTime.fromMillisecondsSinceEpoch(row['created_at'] as int);
      final msgId = row['id'] as String;

      List<Citation> citations = [];
      if (role == 'assistant') {
        final citeRows = await _db.select(
          'SELECT * FROM citations WHERE message_id = ?',
          [msgId],
        );
        citations = citeRows
            .map((c) => Citation(
                  source: c['source'] as String,
                  citationType:
                      CitationType.fromString(c['citation_type'] as String),
                  text: c['text'] as String,
                ))
            .toList();
      }

      messages.add(_rowToMessage(role, text, createdAt, citations));
    }
    return messages;
  }

  Future<void> _insertMessage(
    String sessionId,
    ChatMessage message,
    int sortOrder,
  ) async {
    final (role, text) = _messageToRow(message);
    final msgId =
        '${sessionId}_${sortOrder}_${DateTime.now().millisecondsSinceEpoch}';

    await _db.exec(
      'INSERT INTO messages (id, session_id, role, text, created_at, sort_order) VALUES (?, ?, ?, ?, ?, ?)',
      [
        msgId,
        sessionId,
        role,
        text,
        message.timestamp.millisecondsSinceEpoch,
        sortOrder,
      ],
    );

    if (message is AssistantMessage) {
      for (final citation in message.citations) {
        await _db.exec(
          'INSERT INTO citations (id, message_id, source, citation_type, text) VALUES (?, ?, ?, ?, ?)',
          [
            '${msgId}_cite_${citation.source.hashCode.abs()}',
            msgId,
            citation.source,
            citation.citationType.wire,
            citation.text,
          ],
        );
      }
    }
  }

  (String, String) _messageToRow(ChatMessage message) {
    return switch (message) {
      UserMessage m => ('user', m.text),
      AssistantMessage m => ('assistant', m.text),
      ApprovalMessage m =>
        ('approval', '${m.toolName}:${m.toolCallId}:${m.status.wire}'),
      ClarifyMessage m => ('clarify', m.clarifyText),
      SystemErrorMessage m => ('error', m.userMessage),
    };
  }

  ChatMessage _rowToMessage(
    String role,
    String text,
    DateTime createdAt,
    List<Citation> citations,
  ) {
    switch (role) {
      case 'user':
        return UserMessage(text: text, timestamp: createdAt);
      case 'assistant':
        return AssistantMessage(
            text: text, timestamp: createdAt, citations: citations);
      case 'approval':
        final parts = text.split(':');
        return ApprovalMessage(
          toolCallId: parts.length > 1 ? parts[1] : '',
          toolName: parts.isNotEmpty ? parts[0] : '',
          status: parts.length > 2
              ? ApprovalStatus.values.firstWhere(
                  (s) => s.wire == parts[2],
                  orElse: () => ApprovalStatus.pending,
                )
              : ApprovalStatus.pending,
          timestamp: createdAt,
        );
      case 'clarify':
        return ClarifyMessage(clarifyText: text, timestamp: createdAt);
      case 'error':
        return SystemErrorMessage(
          errorType: ErrorType.unknown,
          userMessage: text,
          timestamp: createdAt,
        );
      default:
        return UserMessage(text: text, timestamp: createdAt);
    }
  }
}
