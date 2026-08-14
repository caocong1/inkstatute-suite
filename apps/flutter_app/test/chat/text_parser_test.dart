import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/chat/text_parser.dart';
import 'package:flutter_app/chat/chat_models.dart';

void main() {
  group('TextParser.parse', () {
    test('extracts CLARIFY marker', () {
      final result = TextParser.parse('some text [CLARIFY: 请补充合同类型] more text');
      expect(result.clarifyRequests.length, 1);
      expect(result.clarifyRequests.first.text, '请补充合同类型');
      expect(result.cleanText, contains('some text'));
      expect(result.cleanText, contains('more text'));
      expect(result.cleanText, isNot(contains('[CLARIFY:')));
    });

    test('extracts HUMAN_REVIEW marker', () {
      final result = TextParser.parse('结论 [HUMAN_REVIEW: 需复核条款风险] end');
      expect(result.humanReviewMarkers.length, 1);
      expect(result.humanReviewMarkers.first.text, '需复核条款风险');
      expect(result.cleanText, isNot(contains('[HUMAN_REVIEW:')));
    });

    test('extracts verified citation', () {
      final result = TextParser.parse('参考 [CITE:verified:合同法第52条] 结论');
      expect(result.citations.length, 1);
      expect(result.citations.first.citationType, CitationType.verified);
      expect(result.citations.first.source, '合同法第52条');
      expect(result.cleanText, isNot(contains('[CITE:')));
    });

    test('extracts retrieved citation', () {
      final result = TextParser.parse('见 [CITE:retrieved:案例库] 文档');
      expect(result.citations.length, 1);
      expect(result.citations.first.citationType, CitationType.retrieved);
      expect(result.citations.first.source, '案例库');
    });

    test('extracts unverified citation', () {
      final result = TextParser.parse('据 [CITE:unverified:网络来源] 分析');
      expect(result.citations.length, 1);
      expect(result.citations.first.citationType, CitationType.unverified);
    });

    test('extracts multiple markers from same text', () {
      final result = TextParser.parse(
        '分析 [CITE:verified:法条1] 和 [CITE:retrieved:案例2] '
        '[CLARIFY: 请补充] [HUMAN_REVIEW: 需复核]',
      );
      expect(result.citations.length, 2);
      expect(result.clarifyRequests.length, 1);
      expect(result.humanReviewMarkers.length, 1);
    });

    test('clean text has markers removed', () {
      final result = TextParser.parse('text [CLARIFY: q] middle [HUMAN_REVIEW: r] end');
      expect(result.cleanText, 'text middle end');
    });

    test('handles text with no markers', () {
      final result = TextParser.parse('plain text without markers');
      expect(result.cleanText, 'plain text without markers');
      expect(result.clarifyRequests, isEmpty);
      expect(result.humanReviewMarkers, isEmpty);
      expect(result.citations, isEmpty);
    });

    test('handles empty text', () {
      final result = TextParser.parse('');
      expect(result.cleanText, '');
      expect(result.clarifyRequests, isEmpty);
    });

    test('handles multiple CLARIFY markers', () {
      final result = TextParser.parse(
        '[CLARIFY: 问题1] text [CLARIFY: 问题2]',
      );
      expect(result.clarifyRequests.length, 2);
      expect(result.clarifyRequests[0].text, '问题1');
      expect(result.clarifyRequests[1].text, '问题2');
    });

    test('preserves newlines in clean text', () {
      final result = TextParser.parse('line1\n[CITE:verified:src]\nline3');
      expect(result.cleanText, contains('line1'));
      expect(result.cleanText, contains('line3'));
      expect(result.cleanText, isNot(contains('[CITE:')));
    });

    test('trims leading/trailing whitespace in marker content', () {
      final result = TextParser.parse('[CLARIFY:   spaced content  ]');
      expect(result.clarifyRequests.first.text, 'spaced content');
    });
  });

  group('TextParser.hasClarifyRequest', () {
    test('returns true when CLARIFY present', () {
      expect(TextParser.hasClarifyRequest('text [CLARIFY: q]'), isTrue);
    });

    test('returns false when no CLARIFY', () {
      expect(TextParser.hasClarifyRequest('plain text'), isFalse);
    });
  });

  group('TextParser.hasHumanReviewMarker', () {
    test('returns true when HUMAN_REVIEW present', () {
      expect(TextParser.hasHumanReviewMarker('text [HUMAN_REVIEW: r]'), isTrue);
    });

    test('returns false when no HUMAN_REVIEW', () {
      expect(TextParser.hasHumanReviewMarker('plain text'), isFalse);
    });
  });

  group('TextParser.hasCitation', () {
    test('returns true when CITE present', () {
      expect(TextParser.hasCitation('text [CITE:verified:src]'), isTrue);
    });

    test('returns false when no CITE', () {
      expect(TextParser.hasCitation('plain text'), isFalse);
    });
  });
}
