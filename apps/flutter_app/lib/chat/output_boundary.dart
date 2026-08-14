/// Output boundary for the chat UI (APP-05).
///
/// Filters ACP session updates to ensure only committed assistant text
/// reaches the user interface. All DSH meta/system noise is blocked.
library;

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
