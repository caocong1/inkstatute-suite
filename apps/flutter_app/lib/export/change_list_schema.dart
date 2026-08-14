/// Change list JSON schema for Word track-changes export (APP-04).
///
/// Defines the structured change list that the model produces and
/// the app-side Python script consumes. The model never directly
/// writes docx bytes — only this JSON schema.
library;

import 'dart:convert';

/// Risk level for a change item.
enum RiskLevel {
  /// P0 — must fix (legal error, critical risk).
  p0('P0'),

  /// P1 — negotiate (important but negotiable).
  p1('P1'),

  /// P2 — optimize (improvement suggestion).
  p2('P2');

  const RiskLevel(this.label);

  /// Display label.
  final String label;

  /// Parses a risk level from a string.
  static RiskLevel fromString(String? s) {
    switch (s?.toUpperCase()) {
      case 'P0':
        return RiskLevel.p0;
      case 'P1':
        return RiskLevel.p1;
      case 'P2':
        return RiskLevel.p2;
      default:
        return RiskLevel.p2;
    }
  }
}

/// A single change item in the change list.
class ChangeItem {
  /// Creates a change item.
  const ChangeItem({
    required this.id,
    required this.clauseLocation,
    required this.originalText,
    this.revisedText,
    required this.reason,
    required this.riskLevel,
    required this.comment,
  });

  /// Unique identifier.
  final int id;

  /// Clause location or identifier (e.g., "第十五条", "第三条第二款").
  final String clauseLocation;

  /// Original text to find in the document.
  final String originalText;

  /// Replacement text (null = comment only, no text replacement).
  final String? revisedText;

  /// Revision reason.
  final String reason;

  /// Risk level (P0/P1/P2).
  final RiskLevel riskLevel;

  /// Comment to attach to the change.
  final String comment;

  /// Converts to JSON map.
  Map<String, dynamic> toJson() => {
        'id': id,
        'clauseLocation': clauseLocation,
        'originalText': originalText,
        'revisedText': revisedText,
        'reason': reason,
        'riskLevel': riskLevel.label,
        'comment': comment,
      };

  /// Parses from JSON map.
  static ChangeItem fromJson(Map<String, dynamic> json) {
    return ChangeItem(
      id: json['id'] as int,
      clauseLocation: json['clauseLocation'] as String? ?? '',
      originalText: json['originalText'] as String? ?? '',
      revisedText: json['revisedText'] as String?,
      reason: json['reason'] as String? ?? '',
      riskLevel: RiskLevel.fromString(json['riskLevel'] as String?),
      comment: json['comment'] as String? ?? '',
    );
  }
}

/// A change list containing multiple change items.
class ChangeList {
  /// Creates a change list.
  const ChangeList({
    required this.items,
    required this.sourceDocument,
    required this.createdAt,
  });

  /// Change items.
  final List<ChangeItem> items;

  /// Source document path or identifier.
  final String sourceDocument;

  /// Creation timestamp.
  final DateTime createdAt;

  /// Converts to JSON string.
  String toJson() => jsonEncode({
        'sourceDocument': sourceDocument,
        'createdAt': createdAt.toIso8601String(),
        'items': items.map((i) => i.toJson()).toList(),
      });

  /// Parses from JSON string.
  static ChangeList? fromJson(String jsonStr) {
    try {
      final json = jsonDecode(jsonStr) as Map<String, dynamic>;
      final itemsRaw = json['items'] as List<dynamic>;
      final items = itemsRaw
          .map((i) => ChangeItem.fromJson(i as Map<String, dynamic>))
          .toList();
      return ChangeList(
        items: items,
        sourceDocument: json['sourceDocument'] as String? ?? '',
        createdAt:
            DateTime.tryParse(json['createdAt'] as String? ?? '') ??
                DateTime.now(),
      );
    } on Exception {
      return null;
    }
  }

  /// Validates the change list and returns a list of validation errors.
  ///
  /// An empty list means valid.
  List<String> validate() {
    final errors = <String>[];
    if (items.isEmpty) {
      errors.add('Change list must have at least one item');
    }
    for (final item in items) {
      if (item.id <= 0) {
        errors.add('Item ${item.id}: id must be positive');
      }
      if (item.originalText.isEmpty && item.revisedText != null) {
        errors.add(
            'Item ${item.id}: originalText cannot be empty when revisedText is present');
      }
      if (item.comment.isEmpty) {
        errors.add('Item ${item.id}: comment cannot be empty');
      }
    }
    final ids = items.map((i) => i.id).toSet();
    if (ids.length != items.length) {
      errors.add('Duplicate item IDs detected');
    }
    return errors;
  }
}
