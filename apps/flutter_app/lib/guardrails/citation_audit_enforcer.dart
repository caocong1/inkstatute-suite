/// Citation audit enforcer (GRD-02).
///
/// App-side enforcement: ensures all citations have a valid type
/// (verified/retrieved/unverified). Parse failures default to
/// unverified with visual warning. The visual warning is already
/// rendered by CitationBadgeWidget (Phase 116).
library;

import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/guardrails/guardrail_models.dart';

/// Enforces the citation audit guardrail on assistant messages.
class CitationAuditEnforcer {
  const CitationAuditEnforcer._();

  /// Ensures all citations have a valid type.
  ///
  /// Citations with invalid or missing types default to `unverified`.
  /// This is the app-side enforcement — the model may produce malformed
  /// citation markers, and this layer catches them.
  static List<Citation> enforce(List<Citation> citations) {
    return citations.map((c) {
      // CitationType.fromString already defaults to unverified for unknown
      // values, but we re-check here for explicitness.
      if (c.citationType == CitationType.verified ||
          c.citationType == CitationType.retrieved ||
          c.citationType == CitationType.unverified) {
        return c;
      }
      // This should never happen due to the enum, but defensive:
      return Citation(
        source: c.source,
        citationType: CitationType.unverified,
        text: c.text,
      );
    }).toList();
  }

  /// Audits the message citations and returns a guardrail result.
  ///
  /// Returns:
  /// - `pass` if no citations or all citations are verified
  /// - `warn` if any citations are unverified
  static GuardrailResult audit(AssistantMessage message) {
    if (message.citations.isEmpty) {
      return GuardrailResult.pass(GuardrailType.citationAudit);
    }

    final hasUnverified = message.citations.any(
      (c) => c.citationType == CitationType.unverified,
    );

    if (hasUnverified) {
      return GuardrailResult.warn(
        GuardrailType.citationAudit,
        '存在未验证引用，请审慎参考',
      );
    }

    return GuardrailResult.pass(GuardrailType.citationAudit);
  }

  /// Returns true if the message has any unverified citations.
  static bool hasUnverifiedCitations(AssistantMessage message) {
    return message.citations.any(
      (c) => c.citationType == CitationType.unverified,
    );
  }

  /// Returns the count of unverified citations.
  static int unverifiedCount(AssistantMessage message) {
    return message.citations
        .where((c) => c.citationType == CitationType.unverified)
        .length;
  }
}
