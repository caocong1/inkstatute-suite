import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/guardrails/polish_checker.dart';

void main() {
  group('PolishChecker.isPolished', () {
    test('returns true when [POLISHED] marker is present', () {
      expect(PolishChecker.isPolished('text [POLISHED]'), isTrue);
    });

    test('returns false when no [POLISHED] marker', () {
      expect(PolishChecker.isPolished('plain text'), isFalse);
    });
  });

  group('PolishChecker.removePolishMarker', () {
    test('removes [POLISHED] from text', () {
      expect(PolishChecker.removePolishMarker('text [POLISHED] end'), 'text end');
    });

    test('returns text unchanged when no marker', () {
      expect(PolishChecker.removePolishMarker('plain text'), 'plain text');
    });
  });

  group('PolishChecker.check', () {
    test('passes when no conclusions are present', () {
      final msg = AssistantMessage(
        text: '事实描述。',
        timestamp: DateTime.now(),
      );
      final result = PolishChecker.check(msg);
      expect(result.isPass, isTrue);
    });

    test('warns when conclusions exist but no [POLISHED] marker', () {
      final msg = AssistantMessage(
        text: '因此，合同有效。',
        timestamp: DateTime.now(),
      );
      final result = PolishChecker.check(msg);
      expect(result.isWarning, isTrue);
      expect(result.message, contains('未经润色'));
    });

    test('passes when conclusions exist with [POLISHED] marker in text', () {
      final msg = AssistantMessage(
        text: '因此，合同有效。 [POLISHED]',
        timestamp: DateTime.now(),
      );
      final result = PolishChecker.check(msg);
      expect(result.isPass, isTrue);
    });
  });

  group('PolishChecker.needsPolishTag', () {
    test('returns true when conclusions lack polish', () {
      final msg = AssistantMessage(
        text: '综上，建议采取诉讼。',
        timestamp: DateTime.now(),
      );
      expect(PolishChecker.needsPolishTag(msg), isTrue);
    });

    test('returns false when no conclusions', () {
      final msg = AssistantMessage(
        text: '事实描述。',
        timestamp: DateTime.now(),
      );
      expect(PolishChecker.needsPolishTag(msg), isFalse);
    });
  });
}
