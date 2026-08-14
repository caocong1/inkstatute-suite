import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/guardrails/guardrail_models.dart';
import 'package:flutter_app/guardrails/human_review_enforcer.dart';
import 'package:flutter_app/guardrails/high_risk_task_config.dart';

void main() {
  group('HumanReviewEnforcer.hasHumanReviewMarker', () {
    test('returns true when markers are present', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
        humanReviewMarkers: [HumanReviewMarker(text: '需复核')],
      );
      expect(HumanReviewEnforcer.hasHumanReviewMarker(msg), isTrue);
    });

    test('returns false when no markers', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
      );
      expect(HumanReviewEnforcer.hasHumanReviewMarker(msg), isFalse);
    });
  });

  group('HumanReviewEnforcer.enforce', () {
    test('passes when no high-risk task type specified', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
      );
      final result = HumanReviewEnforcer.enforce(msg);
      expect(result.isPass, isTrue);
    });

    test('passes when high-risk task type has markers', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
        humanReviewMarkers: [HumanReviewMarker(text: '需复核')],
      );
      final result = HumanReviewEnforcer.enforce(
        msg,
        taskType: HighRiskTaskType.legalConclusion,
      );
      expect(result.isPass, isTrue);
    });

    test('blocks when high-risk task type has no markers', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
      );
      final result = HumanReviewEnforcer.enforce(
        msg,
        taskType: HighRiskTaskType.legalConclusion,
      );
      expect(result.isBlock, isTrue);
      expect(result.message, contains('人审标记'));
    });

    test('blocks for all high-risk types when no markers', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
      );
      for (final type in HighRiskTaskConfig.highRiskTypes) {
        final result = HumanReviewEnforcer.enforce(msg, taskType: type);
        expect(result.isBlock, isTrue, reason: '$type should block');
      }
    });
  });

  group('HumanReviewEnforcer.preserveMarkers', () {
    test('returns an unmodifiable list', () {
      final markers = [HumanReviewMarker(text: '需复核')];
      final preserved = HumanReviewEnforcer.preserveMarkers(markers);
      expect(
        () => preserved.add(HumanReviewMarker(text: 'new')),
        throwsUnsupportedError,
      );
    });

    test('preserves marker content', () {
      final markers = [
        HumanReviewMarker(text: '需复核条款风险'),
        HumanReviewMarker(text: '需复核法律依据'),
      ];
      final preserved = HumanReviewEnforcer.preserveMarkers(markers);
      expect(preserved.length, 2);
      expect(preserved[0].text, '需复核条款风险');
      expect(preserved[1].text, '需复核法律依据');
    });
  });

  group('HumanReviewEnforcer.requiresHumanReview', () {
    test('returns false when no task type', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
      );
      expect(HumanReviewEnforcer.requiresHumanReview(msg, null), isFalse);
    });

    test('returns true when high-risk type has no markers', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
      );
      expect(
        HumanReviewEnforcer.requiresHumanReview(
          msg,
          HighRiskTaskType.legalConclusion,
        ),
        isTrue,
      );
    });

    test('returns false when high-risk type has markers', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
        humanReviewMarkers: [HumanReviewMarker(text: '需复核')],
      );
      expect(
        HumanReviewEnforcer.requiresHumanReview(
          msg,
          HighRiskTaskType.legalConclusion,
        ),
        isFalse,
      );
    });
  });

  group('HighRiskTaskConfig', () {
    test('isHighRisk detects legal conclusion', () {
      expect(HighRiskTaskConfig.isHighRisk('这是一个法律结论'), isTrue);
    });

    test('isHighRisk detects litigation strategy', () {
      expect(HighRiskTaskConfig.isHighRisk('制定诉讼策略'), isTrue);
    });

    test('isHighRisk detects contract substantive clause', () {
      expect(HighRiskTaskConfig.isHighRisk('审查合同实质条款'), isTrue);
    });

    test('isHighRisk returns false for non-high-risk task', () {
      expect(HighRiskTaskConfig.isHighRisk('查找法条'), isFalse);
    });

    test('matchType returns correct type for legal conclusion', () {
      expect(
        HighRiskTaskConfig.matchType('法律结论'),
        HighRiskTaskType.legalConclusion,
      );
    });

    test('matchType returns null for non-high-risk task', () {
      expect(HighRiskTaskConfig.matchType('查找法条'), isNull);
    });

    test('highRiskTypes has exactly 3 types', () {
      expect(HighRiskTaskConfig.highRiskTypes.length, 3);
    });
  });
}
