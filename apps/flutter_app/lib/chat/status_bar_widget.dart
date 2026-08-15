/// Status bar widget (APP-02).
///
/// Displays the current session processing status and LLM provider/model.
library;

import 'package:flutter/material.dart';
import 'package:flutter_app/chat/chat_models.dart';

/// Renders the session status bar with processing indicator and cancel button.
class StatusBarWidget extends StatelessWidget {
  /// Creates a status bar.
  const StatusBarWidget({
    super.key,
    required this.status,
    this.providerName,
    this.modelConfig,
    this.onCancel,
  });

  /// Current message processing status.
  final MessageStatus status;

  /// LLM provider display name (e.g. "DeepSeek").
  final String? providerName;

  /// Model configuration (e.g. "deepseek-v4-flash").
  final String? modelConfig;

  /// Callback when the cancel button is pressed.
  final VoidCallback? onCancel;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).dividerColor,
            width: 0.5,
          ),
        ),
      ),
      child: Row(
        children: [
          if (providerName != null) ...[
            Icon(Icons.cloud, size: 14, color: Colors.grey[600]),
            const SizedBox(width: 4),
            Text(
              providerName!,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            if (modelConfig != null && modelConfig!.isNotEmpty) ...[
              const SizedBox(width: 8),
              Text(
                modelConfig!,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: Colors.grey[600],
                    ),
              ),
            ],
            const SizedBox(width: 16),
          ],
          Expanded(child: _buildStatusText(context)),
          if (status == MessageStatus.processing && onCancel != null)
            TextButton.icon(
              onPressed: onCancel,
              icon: const Icon(Icons.cancel, size: 18),
              label: const Text('取消'),
            ),
        ],
      ),
    );
  }

  Widget _buildStatusText(BuildContext context) {
    return switch (status) {
      MessageStatus.idle => const SizedBox.shrink(),
      MessageStatus.processing => Row(
          children: [
            const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            const SizedBox(width: 8),
            Text('处理中...', style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      MessageStatus.completed => const SizedBox.shrink(),
      MessageStatus.cancelled => Text(
          '已取消',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Colors.grey,
              ),
        ),
      MessageStatus.error => Row(
          children: [
            Icon(Icons.error_outline,
                size: 16, color: Theme.of(context).colorScheme.error),
            const SizedBox(width: 8),
            Text('发生错误',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.error,
                    )),
          ],
        ),
    };
  }
}
