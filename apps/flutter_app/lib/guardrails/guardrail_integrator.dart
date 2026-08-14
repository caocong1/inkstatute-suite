/// Guardrail integrator — runs all 6 guardrail checks (GRD-01..06).
///
/// Wires the individual guardrail checkers into a single entry point
/// that ChatController calls after receiving an assistant message.
library;

import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/guardrails/guardrail_models.dart';
import 'package:flutter_app/guardrails/research_gate_checker.dart';
import 'package:flutter_app/guardrails/citation_audit_enforcer.dart';
import 'package:flutter_app/guardrails/polish_checker.dart';
import 'package:flutter_app/guardrails/human_review_enforcer.dart';

/// Integrates all 6 guardrail checks into a single call.
class GuardrailIntegrator {
  const GuardrailIntegrator._();

  /// Runs all guardrail checks on an assistant message.
  ///
  /// Returns a list of [GuardrailResult], one per guardrail.
  /// GRD-03 (ask-user) and GRD-06 (confidentiality) are stateful and
  /// checked at the prompt-sending stage, not here.
  static List<GuardrailResult> runAllChecks(
    AssistantMessage message, {
    HighRiskTaskType? taskType,
  }) {
    return [
      ResearchGateChecker.check(message),
      CitationAuditEnforcer.audit(message),
      PolishChecker.check(message),
      HumanReviewEnforcer.enforce(message, taskType: taskType),
    ];
  }

  /// Returns true if any result has block severity.
  static bool shouldBlock(List<GuardrailResult> results) {
    return results.any((r) => r.isBlock);
  }

  /// Returns all warning messages from the results.
  static List<String> warnings(List<GuardrailResult> results) {
    return results
        .where((r) => r.isWarning)
        .map((r) => r.message)
        .toList();
  }

  /// Returns all block messages from the results.
  static List<String> blocks(List<GuardrailResult> results) {
    return results
        .where((r) => r.isBlock)
        .map((r) => r.message)
        .toList();
  }

  /// Returns true if all checks pass.
  static bool allPass(List<GuardrailResult> results) {
    return results.every((r) => r.isPass);
  }
}
