/// Change list parser — extracts JSON change lists from assistant text (APP-04).
///
/// The model produces a JSON change list in a fenced ```json block
/// or in a `[CHANGE_LIST: ...]` block. This parser extracts and
/// validates the change list from the assistant message.
library;

import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/export/change_list_schema.dart';

/// Parses change lists from assistant messages.
class ChangeListParser {
  const ChangeListParser._();

  /// Extracts a change list from an assistant message.
  ///
  /// Returns null if no valid change list is found.
  static ChangeList? extractFromMessage(AssistantMessage message) {
    return extractFromText(message.text);
  }

  /// Extracts a change list from raw text.
  ///
  /// Looks for:
  /// 1. A fenced ```json ... ``` block containing a change list
  /// 2. A `[CHANGE_LIST: {...}]` block
  ///
  /// Returns null if no valid change list is found.
  static ChangeList? extractFromText(String text) {
    // Try fenced json block first
    final jsonBlock = _extractFencedJson(text);
    if (jsonBlock != null) {
      final list = ChangeList.fromJson(jsonBlock);
      if (list != null && list.items.isNotEmpty) return list;
    }

    // Try [CHANGE_LIST: ...] block
    final changeListBlock = _extractChangeListBlock(text);
    if (changeListBlock != null) {
      final list = ChangeList.fromJson(changeListBlock);
      if (list != null && list.items.isNotEmpty) return list;
    }

    return null;
  }

  /// Extracts a JSON string from a fenced ```json block.
  static String? _extractFencedJson(String text) {
    final pattern = RegExp(r'```json\s*\n([\s\S]*?)\n```');
    final match = pattern.firstMatch(text);
    if (match == null) return null;
    return match.group(1)?.trim();
  }

  /// Extracts a JSON string from a `[CHANGE_LIST: ...]` block.
  static String? _extractChangeListBlock(String text) {
    // Find the [CHANGE_LIST: marker, then extract the balanced JSON object.
    final startIdx = text.indexOf('[CHANGE_LIST:');
    if (startIdx < 0) return null;
    final jsonStart = text.indexOf('{', startIdx);
    if (jsonStart < 0) return null;

    // Find the matching closing brace by counting brace depth.
    var depth = 0;
    for (var i = jsonStart; i < text.length; i++) {
      final ch = text[i];
      if (ch == '{') depth++;
      if (ch == '}') depth--;
      if (depth == 0) {
        // Check that the next non-space char is ]
        final remaining = text.substring(i + 1).trim();
        if (remaining.startsWith(']')) {
          return text.substring(jsonStart, i + 1);
        }
        return null;
      }
    }
    return null;
  }

  /// Extracts the raw JSON block from text (public for testing).
  static String? extractJsonBlock(String text) {
    return _extractFencedJson(text) ?? _extractChangeListBlock(text);
  }
}
