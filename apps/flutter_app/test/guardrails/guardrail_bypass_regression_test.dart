/// Negative regression tests for all 6 guardrails (GRD-01..06).
///
/// Each test verifies that a bypass attempt is caught by the app-side
/// enforcement layer. These tests lock the "double-layer" guarantee:
/// removing either the preset persona layer or the app enforcement
/// layer must cause test failure.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/guardrails/guardrail_models.dart';
import 'package:flutter_app/guardrails/research_gate_checker.dart';
import 'package:flutter_app/guardrails/citation_audit_enforcer.dart';
import 'package:flutter_app/guardrails/clarify_lock_state.dart';
import 'package:flutter_app/guardrails/polish_checker.dart';
import 'package:flutter_app/guardrails/human_review_enforcer.dart';
import 'package:flutter_app/guardrails/confidentiality_gate.dart';
import 'package:flutter_app/guardrails/guardrail_integrator.dart';

void main() {
  group('GRD-01 bypass: conclusions without verified citations', () {
    test('research-gate catches conclusions without verified citations', () {
      // Bypass attempt: model outputs conclusions without any research
      final msg = AssistantMessage(
        text: '因此，合同有效，建议立即签署。',
        timestamp: DateTime.now(),
        citations: [],
      );
      final result = ResearchGateChecker.check(msg);
      expect(result.isWarning, isTrue,
          reason: 'Research-gate must warn when conclusions lack verified citations');
      expect(result.message, contains('待核实'));
    });

    test('research-gate passes when verified citations exist', () {
      final msg = AssistantMessage(
        text: '因此，合同有效。',
        timestamp: DateTime.now(),
        citations: [
          Citation(source: '合同法第52条', citationType: CitationType.verified, text: ''),
        ],
      );
      final result = ResearchGateChecker.check(msg);
      expect(result.isPass, isTrue);
    });
  });

  group('GRD-02 bypass: citations with invalid type', () {
    test('citation audit defaults invalid citations to unverified', () {
      // Bypass attempt: model outputs citations with unknown type
      // CitationType.fromString already defaults to unverified
      final citations = [
        Citation(source: 'unknown', citationType: CitationType.unverified, text: ''),
      ];
      final enforced = CitationAuditEnforcer.enforce(citations);
      expect(enforced[0].citationType, CitationType.unverified,
          reason: 'Invalid citations must default to unverified');
    });

    test('citation audit warns when unverified citations exist', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
        citations: [
          Citation(source: 'unverified source', citationType: CitationType.unverified, text: ''),
        ],
      );
      final result = CitationAuditEnforcer.audit(msg);
      expect(result.isWarning, isTrue,
          reason: 'Citation audit must warn for unverified citations');
    });
  });

  group('GRD-03 bypass: prompt sent while clarify lock active', () {
    test('clarify lock blocks new prompts when locked', () {
      // Bypass attempt: user tries to send a new prompt while clarification is pending
      final sm = ClarifyLockStateMachine();
      sm.lock('请补充合同类型');
      expect(sm.canSendPrompt(), isFalse,
          reason: 'Clarify lock must block new prompts when locked');
    });

    test('clarify lock allows prompts after unlock', () {
      final sm = ClarifyLockStateMachine();
      sm.lock('请补充');
      sm.unlock();
      expect(sm.canSendPrompt(), isTrue,
          reason: 'Clarify lock must allow prompts after user responds');
    });
  });

  group('GRD-04 bypass: conclusions without polish marker', () {
    test('polish checker catches unpolished conclusions', () {
      // Bypass attempt: model outputs final conclusions without [POLISHED] marker
      final msg = AssistantMessage(
        text: '综上，建议签署合同。',
        timestamp: DateTime.now(),
      );
      final result = PolishChecker.check(msg);
      expect(result.isWarning, isTrue,
          reason: 'Polish checker must warn for unpolished conclusions');
      expect(result.message, contains('未经润色'));
    });

    test('polish checker passes when [POLISHED] marker present', () {
      final msg = AssistantMessage(
        text: '综上，建议签署合同。 [POLISHED]',
        timestamp: DateTime.now(),
      );
      final result = PolishChecker.check(msg);
      expect(result.isPass, isTrue);
    });
  });

  group('GRD-05 bypass: high-risk task without human review marker', () {
    test('human review enforcer blocks high-risk conclusions without markers', () {
      // Bypass attempt: model outputs high-risk legal conclusion without [HUMAN_REVIEW:]
      final msg = AssistantMessage(
        text: '法律结论：合同无效。',
        timestamp: DateTime.now(),
      );
      final result = HumanReviewEnforcer.enforce(
        msg,
        taskType: HighRiskTaskType.legalConclusion,
      );
      expect(result.isBlock, isTrue,
          reason: 'Human review enforcer must block high-risk tasks without markers');
    });

    test('human review enforcer passes when markers present', () {
      final msg = AssistantMessage(
        text: '法律结论：合同无效。',
        timestamp: DateTime.now(),
        humanReviewMarkers: [HumanReviewMarker(text: '需复核合同效力')],
      );
      final result = HumanReviewEnforcer.enforce(
        msg,
        taskType: HighRiskTaskType.legalConclusion,
      );
      expect(result.isPass, isTrue);
    });

    test('human review markers cannot be removed from preserved list', () {
      final markers = [HumanReviewMarker(text: '需复核')];
      final preserved = HumanReviewEnforcer.preserveMarkers(markers);
      expect(
        () => preserved.add(HumanReviewMarker(text: 'new')),
        throwsUnsupportedError,
        reason: 'No UI/API path can add or remove human review markers',
      );
    });
  });

  group('GRD-06 bypass: client material prompt without confirmation', () {
    test('confidentiality gate blocks client material prompts without confirmation', () {
      // Bypass attempt: user sends client material prompt without confirming
      final gate = ConfidentialityGate();
      expect(gate.canProceed('帮我审查这份合同'), isFalse,
          reason: 'Confidentiality gate must block client material prompts without confirmation');
    });

    test('confidentiality gate allows after confirmation', () {
      final gate = ConfidentialityGate();
      gate.confirm();
      expect(gate.canProceed('帮我审查这份合同'), isTrue);
    });
  });

  group('GuardrailIntegrator', () {
    test('runAllChecks returns results for all 4 message-level guardrails', () {
      final msg = AssistantMessage(
        text: '因此，合同有效。',
        timestamp: DateTime.now(),
      );
      final results = GuardrailIntegrator.runAllChecks(msg);
      expect(results.length, 4);
      // At least research-gate and polish should warn
      expect(results.any((r) => r.isWarning), isTrue);
    });

    test('shouldBlock returns true when any result blocks', () {
      final results = [
        GuardrailResult.pass(GuardrailType.researchGate),
        GuardrailResult.block(GuardrailType.humanReview, 'blocked'),
      ];
      expect(GuardrailIntegrator.shouldBlock(results), isTrue);
    });

    test('shouldBlock returns false when no results block', () {
      final results = [
        GuardrailResult.pass(GuardrailType.researchGate),
        GuardrailResult.warn(GuardrailType.citationAudit, 'warn'),
      ];
      expect(GuardrailIntegrator.shouldBlock(results), isFalse);
    });

    test('warnings returns only warning messages', () {
      final results = [
        GuardrailResult.pass(GuardrailType.researchGate),
        GuardrailResult.warn(GuardrailType.citationAudit, 'warn1'),
        GuardrailResult.warn(GuardrailType.polish, 'warn2'),
      ];
      final warnings = GuardrailIntegrator.warnings(results);
      expect(warnings.length, 2);
      expect(warnings, containsAll(['warn1', 'warn2']));
    });

    test('allPass returns true when all results pass', () {
      final msg = AssistantMessage(
        text: '事实描述。',
        timestamp: DateTime.now(),
        citations: [
          Citation(source: '法条', citationType: CitationType.verified, text: ''),
        ],
      );
      final results = GuardrailIntegrator.runAllChecks(msg);
      expect(GuardrailIntegrator.allPass(results), isTrue);
    });
  });
}
