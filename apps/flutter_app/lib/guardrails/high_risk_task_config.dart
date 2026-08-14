/// High-risk task configuration (GRD-05).
///
/// Defines which task types are considered high-risk and require
/// human review markers. This configuration lives in the app layer,
/// not the engine layer.
library;

import 'package:flutter_app/guardrails/guardrail_models.dart';

/// Configuration for high-risk task types.
class HighRiskTaskConfig {
  const HighRiskTaskConfig._();

  /// All configured high-risk task types.
  static const List<HighRiskTaskType> highRiskTypes = [
    HighRiskTaskType.legalConclusion,
    HighRiskTaskType.litigationStrategy,
    HighRiskTaskType.contractSubstantiveClause,
  ];

  /// Patterns that indicate a high-risk task.
  static const Map<HighRiskTaskType, List<String>> _patterns = {
    HighRiskTaskType.legalConclusion: ['法律结论', '定性建议', '法律意见'],
    HighRiskTaskType.litigationStrategy: ['诉讼策略', '诉讼方案', '应诉策略'],
    HighRiskTaskType.contractSubstantiveClause: [
      '合同实质条款',
      '合同核心条款',
      '实质性条款',
    ],
  };

  /// Checks if a task description matches any high-risk pattern.
  static bool isHighRisk(String taskDescription) {
    for (final type in highRiskTypes) {
      final patterns = _patterns[type]!;
      if (patterns.any((p) => taskDescription.contains(p))) {
        return true;
      }
    }
    return false;
  }

  /// Returns the matching high-risk task type for a description, or null.
  static HighRiskTaskType? matchType(String taskDescription) {
    for (final type in highRiskTypes) {
      final patterns = _patterns[type]!;
      if (patterns.any((p) => taskDescription.contains(p))) {
        return type;
      }
    }
    return null;
  }
}
