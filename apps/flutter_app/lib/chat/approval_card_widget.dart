/// Approval card widget (APP-02).
///
/// Renders a tool permission request as an allow/reject card.
/// No batch approval control — one card per request.
library;

import 'package:flutter/material.dart';
import 'package:flutter_app/chat/chat_models.dart';

/// Renders an [ApprovalMessage] as an interactive approval card.
class ApprovalCardWidget extends StatelessWidget {
  /// Creates an approval card.
  const ApprovalCardWidget({
    super.key,
    required this.message,
    this.onAllow,
    this.onReject,
  });

  /// The approval message to render.
  final ApprovalMessage message;

  /// Callback when the user clicks "允许".
  final void Function(String toolCallId)? onAllow;

  /// Callback when the user clicks "拒绝".
  final void Function(String toolCallId)? onReject;

  @override
  Widget build(BuildContext context) {
    final isPending = message.status == ApprovalStatus.pending;
    final borderColor = switch (message.status) {
      ApprovalStatus.pending => Colors.orange,
      ApprovalStatus.approved => Colors.green,
      ApprovalStatus.rejected => Colors.red,
    };

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: BorderSide(color: borderColor.withValues(alpha: 0.5), width: 2),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  message.status == ApprovalStatus.approved
                      ? Icons.check_circle
                      : message.status == ApprovalStatus.rejected
                          ? Icons.cancel
                          : Icons.pending_actions,
                  color: borderColor,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Text(
                  '工具审批请求',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text('工具: ${message.toolName}'),
            const SizedBox(height: 4),
            Text('调用 ID: ${message.toolCallId}',
                style: Theme.of(context).textTheme.bodySmall),
            if (isPending) ...[
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: onReject != null
                        ? () => onReject!(message.toolCallId)
                        : null,
                    child: const Text('拒绝'),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                    onPressed: onAllow != null
                        ? () => onAllow!(message.toolCallId)
                        : null,
                    child: const Text('允许'),
                  ),
                ],
              ),
            ] else ...[
              const SizedBox(height: 8),
              Text(
                message.status == ApprovalStatus.approved ? '已允许' : '已拒绝',
                style: TextStyle(color: borderColor, fontSize: 13),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
