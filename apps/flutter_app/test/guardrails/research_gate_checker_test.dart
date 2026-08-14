import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/guardrails/research_gate_checker.dart';

void main() {
  group('ResearchGateChecker.check', () {
    test('passes when no conclusions are present', () {
      final msg = AssistantMessage(
        text: '这是一段事实描述。',
        timestamp: DateTime.now(),
      );
      final result = ResearchGateChecker.check(msg);
      expect(result.isPass, isTrue);
    });

    test('passes when conclusions have verified citations', () {
      final msg = AssistantMessage(
        text: '因此，合同有效。',
        timestamp: DateTime.now(),
        citations: [
          Citation(
            source: '合同法第52条',
            citationType: CitationType.verified,
            text: 'cite',
          ),
        ],
      );
      final result = ResearchGateChecker.check(msg);
      expect(result.isPass, isTrue);
    });

    test('warns when conclusions exist but no verified citations', () {
      final msg = AssistantMessage(
        text: '因此，合同有效。',
        timestamp: DateTime.now(),
        citations: [],
      );
      final result = ResearchGateChecker.check(msg);
      expect(result.isWarning, isTrue);
      expect(result.message, contains('待核实'));
    });

    test('warns when conclusions exist with only unverified citations', () {
      final msg = AssistantMessage(
        text: '综上，建议采取诉讼策略。',
        timestamp: DateTime.now(),
        citations: [
          Citation(
            source: '网络来源',
            citationType: CitationType.unverified,
            text: 'cite',
          ),
        ],
      );
      final result = ResearchGateChecker.check(msg);
      expect(result.isWarning, isTrue);
    });

    test('passes when conclusions exist with retrieved citations', () {
      final msg = AssistantMessage(
        text: '建议参考相关案例。',
        timestamp: DateTime.now(),
        citations: [
          Citation(
            source: '案例库',
            citationType: CitationType.retrieved,
            text: 'cite',
          ),
        ],
      );
      final result = ResearchGateChecker.check(msg);
      // Retrieved is not verified — should still warn
      expect(result.isWarning, isTrue);
    });

    test('detects multiple conclusion keywords', () {
      final msg = AssistantMessage(
        text: '应当注意，必须遵守法律规定。',
        timestamp: DateTime.now(),
      );
      final result = ResearchGateChecker.check(msg);
      expect(result.isWarning, isTrue);
    });
  });

  group('ResearchGateChecker.needsVerificationTag', () {
    test('returns true when conclusions lack verified citations', () {
      final msg = AssistantMessage(
        text: '因此，合同有效。',
        timestamp: DateTime.now(),
      );
      expect(ResearchGateChecker.needsVerificationTag(msg), isTrue);
    });

    test('returns false when no conclusions', () {
      final msg = AssistantMessage(
        text: '事实描述。',
        timestamp: DateTime.now(),
      );
      expect(ResearchGateChecker.needsVerificationTag(msg), isFalse);
    });
  });
}
