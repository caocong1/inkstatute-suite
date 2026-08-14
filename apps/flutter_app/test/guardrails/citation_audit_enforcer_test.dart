import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/guardrails/citation_audit_enforcer.dart';

void main() {
  group('CitationAuditEnforcer.enforce', () {
    test('preserves valid citations', () {
      final citations = [
        Citation(source: 'A', citationType: CitationType.verified, text: ''),
        Citation(source: 'B', citationType: CitationType.retrieved, text: ''),
        Citation(source: 'C', citationType: CitationType.unverified, text: ''),
      ];
      final enforced = CitationAuditEnforcer.enforce(citations);
      expect(enforced.length, 3);
      expect(enforced[0].citationType, CitationType.verified);
      expect(enforced[1].citationType, CitationType.retrieved);
      expect(enforced[2].citationType, CitationType.unverified);
    });

    test('empty list returns empty', () {
      final enforced = CitationAuditEnforcer.enforce([]);
      expect(enforced, isEmpty);
    });
  });

  group('CitationAuditEnforcer.audit', () {
    test('passes when no citations', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
      );
      final result = CitationAuditEnforcer.audit(msg);
      expect(result.isPass, isTrue);
    });

    test('passes when all citations are verified', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
        citations: [
          Citation(source: 'A', citationType: CitationType.verified, text: ''),
        ],
      );
      final result = CitationAuditEnforcer.audit(msg);
      expect(result.isPass, isTrue);
    });

    test('warns when unverified citations exist', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
        citations: [
          Citation(source: 'A', citationType: CitationType.verified, text: ''),
          Citation(source: 'B', citationType: CitationType.unverified, text: ''),
        ],
      );
      final result = CitationAuditEnforcer.audit(msg);
      expect(result.isWarning, isTrue);
      expect(result.message, contains('未验证'));
    });

    test('passes when all citations are retrieved (not unverified)', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
        citations: [
          Citation(source: 'A', citationType: CitationType.retrieved, text: ''),
        ],
      );
      final result = CitationAuditEnforcer.audit(msg);
      expect(result.isPass, isTrue);
    });
  });

  group('CitationAuditEnforcer.hasUnverifiedCitations', () {
    test('returns true when unverified citations exist', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
        citations: [
          Citation(source: 'A', citationType: CitationType.unverified, text: ''),
        ],
      );
      expect(CitationAuditEnforcer.hasUnverifiedCitations(msg), isTrue);
    });

    test('returns false when no unverified citations', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
        citations: [
          Citation(source: 'A', citationType: CitationType.verified, text: ''),
        ],
      );
      expect(CitationAuditEnforcer.hasUnverifiedCitations(msg), isFalse);
    });

    test('returns false when no citations', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
      );
      expect(CitationAuditEnforcer.hasUnverifiedCitations(msg), isFalse);
    });
  });

  group('CitationAuditEnforcer.unverifiedCount', () {
    test('returns count of unverified citations', () {
      final msg = AssistantMessage(
        text: 'text',
        timestamp: DateTime.now(),
        citations: [
          Citation(source: 'A', citationType: CitationType.unverified, text: ''),
          Citation(source: 'B', citationType: CitationType.unverified, text: ''),
          Citation(source: 'C', citationType: CitationType.verified, text: ''),
        ],
      );
      expect(CitationAuditEnforcer.unverifiedCount(msg), 2);
    });
  });
}
