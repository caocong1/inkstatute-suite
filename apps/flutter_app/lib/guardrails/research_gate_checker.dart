/// Research-gate checker (GRD-01).
///
/// App-side enforcement: when an assistant message contains conclusions
/// but no verified citations, the conclusion area is marked "待核实".
/// The preset persona layer (Phase 113) already instructs the model to
/// research before concluding; this is the second layer.
library;

import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/guardrails/guardrail_models.dart';

/// Checks the research-gate guardrail on assistant messages.
class ResearchGateChecker {
  const ResearchGateChecker._();

  /// Conclusion keywords that trigger the research-gate check.
  static const _conclusionKeywords = [
    '因此',
    '综上',
    '结论',
    '建议',
    '应当',
    '应',
    '必须',
    '不得',
  ];

  /// Checks if the message has conclusions without verified citations.
  ///
  /// Returns:
  /// - `pass` if no conclusions are detected
  /// - `pass` if conclusions are detected AND verified citations exist
  /// - `warn` if conclusions are detected but NO verified citations exist
  static GuardrailResult check(AssistantMessage message) {
    final hasConclusions = _hasConclusions(message.text);
    if (!hasConclusions) {
      return GuardrailResult.pass(GuardrailType.researchGate);
    }

    final hasVerifiedCitations = message.citations.any(
      (c) => c.citationType == CitationType.verified,
    );

    if (hasVerifiedCitations) {
      return GuardrailResult.pass(GuardrailType.researchGate);
    }

    return GuardrailResult.warn(
      GuardrailType.researchGate,
      '结论区无已验证引用，标记为"待核实"',
    );
  }

  /// Returns true if the text contains conclusion keywords.
  static bool _hasConclusions(String text) {
    return _conclusionKeywords.any((kw) => text.contains(kw));
  }

  /// Returns true if the message needs the "待核实" tag.
  static bool needsVerificationTag(AssistantMessage message) {
    final result = check(message);
    return result.isWarning;
  }
}
