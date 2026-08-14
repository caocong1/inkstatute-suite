import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/guardrails/confidentiality_gate.dart';

void main() {
  group('ConfidentialityGate.requiresConfirmation', () {
    test('returns true for prompts with 合同 keyword', () {
      expect(ConfidentialityGate.requiresConfirmation('帮我审查合同'), isTrue);
    });

    test('returns true for prompts with 案件 keyword', () {
      expect(ConfidentialityGate.requiresConfirmation('这个案件怎么处理'), isTrue);
    });

    test('returns true for prompts with 客户 keyword', () {
      expect(ConfidentialityGate.requiresConfirmation('客户要求修改'), isTrue);
    });

    test('returns true for prompts with 当事人 keyword', () {
      expect(ConfidentialityGate.requiresConfirmation('当事人信息'), isTrue);
    });

    test('returns true for prompts with 证据 keyword', () {
      expect(ConfidentialityGate.requiresConfirmation('证据分析'), isTrue);
    });

    test('returns false for non-client-material prompts', () {
      expect(ConfidentialityGate.requiresConfirmation('查找合同法第52条'), isTrue);
    });

    test('returns false for general legal questions', () {
      expect(ConfidentialityGate.requiresConfirmation('什么是诉讼时效'), isFalse);
    });
  });

  group('ConfidentialityGate.canProceed', () {
    test('returns true for non-client-material prompts', () {
      final gate = ConfidentialityGate();
      expect(gate.canProceed('什么是诉讼时效'), isTrue);
    });

    test('returns false for client-material prompts without confirmation', () {
      final gate = ConfidentialityGate();
      expect(gate.canProceed('帮我审查合同'), isFalse);
    });

    test('returns true for client-material prompts after confirmation', () {
      final gate = ConfidentialityGate();
      gate.confirm();
      expect(gate.canProceed('帮我审查合同'), isTrue);
    });
  });

  group('ConfidentialityGate.confirm', () {
    test('sets confirmed to true', () {
      final gate = ConfidentialityGate();
      expect(gate.confirmed, isFalse);
      gate.confirm();
      expect(gate.confirmed, isTrue);
    });
  });

  group('ConfidentialityGate.reset', () {
    test('resets confirmed to false', () {
      final gate = ConfidentialityGate();
      gate.confirm();
      gate.reset();
      expect(gate.confirmed, isFalse);
    });
  });

  group('ConfidentialityGate constants', () {
    test('confirmationMessage contains DeepSeek API notice', () {
      expect(ConfidentialityGate.confirmationMessage, contains('DeepSeek API'));
    });

    test('confirmationMessage contains desensitization reminder', () {
      expect(ConfidentialityGate.confirmationMessage, contains('脱敏'));
    });

    test('confirmationTitle is 保密提示', () {
      expect(ConfidentialityGate.confirmationTitle, '保密提示');
    });
  });
}
