/// Main chat view widget (APP-02).
///
/// Renders the message list, input field, and status bar.
/// Input is disabled when a prompt is in-flight (single in-flight).
library;

import 'package:flutter/material.dart';
import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/chat/chat_message_widget.dart';
import 'package:flutter_app/chat/approval_card_widget.dart';
import 'package:flutter_app/chat/clarification_card_widget.dart';
import 'package:flutter_app/chat/status_bar_widget.dart';

/// The main chat view with message list, input, and status.
class ChatView extends StatefulWidget {
  /// Creates a chat view.
  const ChatView({
    super.key,
    required this.messages,
    required this.status,
    this.practiceArea,
    this.onSendPrompt,
    this.onCancel,
    this.onAllowApproval,
    this.onRejectApproval,
    this.onClarifySubmit,
  });

  /// The list of chat messages to display.
  final List<ChatMessage> messages;

  /// Current processing status.
  final MessageStatus status;

  /// Practice area label.
  final String? practiceArea;

  /// Callback when the user sends a prompt.
  final void Function(String text)? onSendPrompt;

  /// Callback when the user cancels an in-flight request.
  final VoidCallback? onCancel;

  /// Callback when the user approves a tool request.
  final void Function(String toolCallId)? onAllowApproval;

  /// Callback when the user rejects a tool request.
  final void Function(String toolCallId)? onRejectApproval;

  /// Callback when the user submits a clarification response.
  final void Function(String clarifyText, String userResponse)? onClarifySubmit;

  @override
  State<ChatView> createState() => _ChatViewState();
}

class _ChatViewState extends State<ChatView> {
  final _inputController = TextEditingController();
  final _scrollController = ScrollController();

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _send() {
    final text = _inputController.text.trim();
    if (text.isEmpty) return;
    if (widget.status == MessageStatus.processing) return;
    widget.onSendPrompt?.call(text);
    _inputController.clear();
  }

  @override
  Widget build(BuildContext context) {
    final isProcessing = widget.status == MessageStatus.processing;

    return Column(
      children: [
        StatusBarWidget(
          status: widget.status,
          practiceArea: widget.practiceArea,
          onCancel: widget.onCancel,
        ),
        Expanded(
          child: ListView.builder(
            controller: _scrollController,
            padding: const EdgeInsets.symmetric(vertical: 8),
            itemCount: widget.messages.length,
            itemBuilder: (context, index) {
              final msg = widget.messages[index];
              return switch (msg) {
                ApprovalMessage m => ApprovalCardWidget(
                    message: m,
                    onAllow: widget.onAllowApproval,
                    onReject: widget.onRejectApproval,
                  ),
                ClarifyMessage m => ClarificationCardWidget(
                    message: m,
                    onSubmit: widget.onClarifySubmit,
                  ),
                _ => ChatMessageWidget(message: msg),
              };
            },
          ),
        ),
        // Input area
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            border: Border(
              top: BorderSide(
                color: Theme.of(context).dividerColor,
                width: 0.5,
              ),
            ),
          ),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _inputController,
                  enabled: !isProcessing,
                  decoration: InputDecoration(
                    hintText: isProcessing ? '处理中...' : '输入您的问题...',
                    border: const OutlineInputBorder(),
                    isDense: true,
                  ),
                  onSubmitted: (_) => _send(),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(
                onPressed: isProcessing ? null : _send,
                icon: const Icon(Icons.send),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
