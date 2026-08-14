/// Clarification card widget (APP-02).
///
/// Renders a [ClarifyMessage] with a text input for the user's
/// supplementary response.
library;

import 'package:flutter/material.dart';
import 'package:flutter_app/chat/chat_models.dart';

/// Renders a [ClarifyMessage] as an interactive clarification card.
class ClarificationCardWidget extends StatefulWidget {
  /// Creates a clarification card.
  const ClarificationCardWidget({
    super.key,
    required this.message,
    this.onSubmit,
  });

  /// The clarification message to render.
  final ClarifyMessage message;

  /// Callback when the user submits their supplementary response.
  final void Function(String clarifyText, String userResponse)? onSubmit;

  @override
  State<ClarificationCardWidget> createState() =>
      _ClarificationCardWidgetState();
}

class _ClarificationCardWidgetState extends State<ClarificationCardWidget> {
  final _controller = TextEditingController();
  bool _submitted = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // If the message already has a user response, show it collapsed.
    if (widget.message.userResponse != null || _submitted) {
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
              Text(widget.message.clarifyText),
              const SizedBox(height: 8),
              Text(
                '补充: ${widget.message.userResponse ?? _controller.text}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
      );
    }

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
            Text(widget.message.clarifyText),
            const SizedBox(height: 12),
            TextField(
              controller: _controller,
              decoration: const InputDecoration(
                hintText: '请输入补充信息...',
                border: OutlineInputBorder(),
                isDense: true,
              ),
              maxLines: 3,
              minLines: 1,
            ),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton(
                onPressed: () {
                  final response = _controller.text.trim();
                  if (response.isEmpty) return;
                  setState(() => _submitted = true);
                  widget.onSubmit?.call(widget.message.clarifyText, response);
                },
                child: const Text('提交补充'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
