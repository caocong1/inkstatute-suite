/// Chat message rendering widget (APP-02).
///
/// Renders each ChatMessage subtype with appropriate visual treatment.
library;

import 'package:flutter/material.dart';
import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/chat/citation_badge_widget.dart';
import 'package:flutter_app/chat/text_parser.dart';

/// Renders a [ChatMessage] in the chat view.
class ChatMessageWidget extends StatelessWidget {
  /// Creates a chat message widget.
  const ChatMessageWidget({super.key, required this.message});

  /// The message to render.
  final ChatMessage message;

  @override
  Widget build(BuildContext context) {
    return switch (message) {
      UserMessage _ => _buildUserMessage(context),
      AssistantMessage _ => _buildAssistantMessage(context),
      ApprovalMessage _ => _buildApprovalMessage(context),
      ClarifyMessage _ => _buildClarifyMessage(context),
      SystemErrorMessage _ => _buildSystemError(context),
    };
  }

  Widget _buildUserMessage(BuildContext context) {
    final msg = message as UserMessage;
    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.primaryContainer,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(msg.text, style: Theme.of(context).textTheme.bodyMedium),
      ),
    );
  }

  Widget _buildAssistantMessage(BuildContext context) {
    final msg = message as AssistantMessage;
    final parsed = TextParser.parse(msg.text);
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(parsed.cleanText, style: Theme.of(context).textTheme.bodyMedium),
            if (parsed.citations.isNotEmpty ||
                parsed.humanReviewMarkers.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 4,
                runSpacing: 4,
                children: [
                  for (final c in parsed.citations)
                    CitationBadgeWidget(citation: c),
                  for (final h in parsed.humanReviewMarkers)
                    CitationBadgeWidget.humanReview(marker: h),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildApprovalMessage(BuildContext context) {
    final msg = message as ApprovalMessage;
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
      child: ListTile(
        leading: Icon(
          msg.status == ApprovalStatus.approved
              ? Icons.check_circle
              : msg.status == ApprovalStatus.rejected
                  ? Icons.cancel
                  : Icons.pending,
          color: msg.status == ApprovalStatus.approved
              ? Colors.green
              : msg.status == ApprovalStatus.rejected
                  ? Colors.red
                  : Colors.orange,
        ),
        title: Text('工具审批: ${msg.toolName}'),
        subtitle: Text(
          msg.status == ApprovalStatus.pending
              ? '等待审批'
              : msg.status == ApprovalStatus.approved
                  ? '已允许'
                  : '已拒绝',
        ),
      ),
    );
  }

  Widget _buildClarifyMessage(BuildContext context) {
    final msg = message as ClarifyMessage;
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
      color: Theme.of(context).colorScheme.tertiaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.help_outline, size: 20),
                const SizedBox(width: 8),
                Text('需要澄清', style: Theme.of(context).textTheme.titleSmall),
              ],
            ),
            const SizedBox(height: 8),
            Text(msg.clarifyText),
            if (msg.userResponse != null) ...[
              const SizedBox(height: 8),
              Text('补充: ${msg.userResponse}',
                  style: Theme.of(context).textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSystemError(BuildContext context) {
    final msg = message as SystemErrorMessage;
    return Center(
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.red.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.red.withValues(alpha: 0.3)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, color: Colors.red, size: 20),
            const SizedBox(width: 8),
            Flexible(child: Text(msg.userMessage)),
          ],
        ),
      ),
    );
  }
}
