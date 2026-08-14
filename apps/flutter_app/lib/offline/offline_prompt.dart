/// Offline prompt widget — shows when user tries new task offline (PKG-04).
library;

import 'package:flutter/material.dart';

/// Widget that prompts the user when they try to start a new task offline.
class OfflinePrompt extends StatelessWidget {
  /// Creates an offline prompt.
  const OfflinePrompt({
    super.key,
    required this.onViewHistory,
    required this.onRetry,
  });

  /// Called when the user chooses to view history.
  final VoidCallback onViewHistory;

  /// Called when the user chooses to retry (check network again).
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('离线提示'),
      content: const Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.wifi_off, color: Colors.orange),
              SizedBox(width: 8),
              Text('当前处于离线状态'),
            ],
          ),
          SizedBox(height: 16),
          Text(
            '新任务需要联网才能使用。您可以查看历史会话，或检查网络后重试。',
            style: TextStyle(fontSize: 14),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: onRetry,
          child: const Text('重试'),
        ),
        ElevatedButton(
          onPressed: onViewHistory,
          child: const Text('查看历史'),
        ),
      ],
    );
  }

  /// Returns the offline status message.
  static String get message => '当前处于离线状态，新任务需要联网。您可以查看历史会话。';
}
