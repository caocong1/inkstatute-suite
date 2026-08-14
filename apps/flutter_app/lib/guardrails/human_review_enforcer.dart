/// Human review enforcer (GRD-05).
///
/// App-side enforcement: high-risk legal conclusions must carry
/// `[HUMAN_REVIEW: …]` markers. These markers cannot be removed by
/// any UI/API path. The sealed ChatMessage model ensures immutability.
/// The preset persona (Phase 113) instructs the model to add markers;
/// this is the second layer.
library;

import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/guardrails/guardrail_models.dart';

/// Enforces the human review guardrail on assistant messages.
class HumanReviewEnforcer {
  const HumanReviewEnforcer._();

  /// Returns true if the message has `[HUMAN_REVIEW:]` markers.
  static bool hasHumanReviewMarker(AssistantMessage message) {
    return message.humanReviewMarkers.isNotEmpty;
  }

  /// Enforces the human review guardrail.
  ///
  /// Returns:
  /// - `pass` if no high-risk task type is specified
  /// - `pass` if high-risk task type is specified AND markers are present
  /// - `block` if high-risk task type is specified but NO markers are present
  static GuardrailResult enforce(
    AssistantMessage message, {
    HighRiskTaskType? taskType,
  }) {
    if (taskType == null) {
      return GuardrailResult.pass(GuardrailType.humanReview);
    }

    if (hasHumanReviewMarker(message)) {
      return GuardrailResult.pass(GuardrailType.humanReview);
    }

    return GuardrailResult.block(
      GuardrailType.humanReview,
      '高风险任务（${taskType.displayName}）缺少人审标记，禁止自动定稿',
    );
  }

  /// Preserves human review markers — returns them unchanged.
  ///
  /// This is a no-op that documents the immutability guarantee:
  /// no UI/API path can remove human review markers from a message.
  /// The sealed ChatMessage model ensures this at the type level.
  static List<HumanReviewMarker> preserveMarkers(
    List<HumanReviewMarker> markers,
  ) {
    // Return a copy to prevent external mutation.
    return List.unmodifiable(markers);
  }

  /// Returns true if the message is high-risk and requires human review.
  static bool requiresHumanReview(
    AssistantMessage message,
    HighRiskTaskType? taskType,
  ) {
    if (taskType == null) return false;
    return !hasHumanReviewMarker(message);
  }
}
