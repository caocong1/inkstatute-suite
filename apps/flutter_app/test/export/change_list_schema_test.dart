import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/export/change_list_schema.dart';

void main() {
  group('RiskLevel', () {
    test('fromString parses P0', () {
      expect(RiskLevel.fromString('P0'), RiskLevel.p0);
    });

    test('fromString parses P1', () {
      expect(RiskLevel.fromString('P1'), RiskLevel.p1);
    });

    test('fromString parses P2', () {
      expect(RiskLevel.fromString('P2'), RiskLevel.p2);
    });

    test('fromString defaults to P2 for unknown', () {
      expect(RiskLevel.fromString('unknown'), RiskLevel.p2);
      expect(RiskLevel.fromString(null), RiskLevel.p2);
    });

    test('label is correct', () {
      expect(RiskLevel.p0.label, 'P0');
      expect(RiskLevel.p1.label, 'P1');
      expect(RiskLevel.p2.label, 'P2');
    });
  });

  group('ChangeItem', () {
    test('toJson serializes correctly', () {
      final item = ChangeItem(
        id: 1,
        clauseLocation: '第十五条',
        originalText: '原条款',
        revisedText: '修订条款',
        reason: '法律引用已废止',
        riskLevel: RiskLevel.p0,
        comment: '必须修正',
      );
      final json = item.toJson();
      expect(json['id'], 1);
      expect(json['clauseLocation'], '第十五条');
      expect(json['originalText'], '原条款');
      expect(json['revisedText'], '修订条款');
      expect(json['riskLevel'], 'P0');
    });

    test('fromJson parses correctly', () {
      final json = {
        'id': 2,
        'clauseLocation': '第三条',
        'originalText': '原文',
        'revisedText': null,
        'reason': '建议修改',
        'riskLevel': 'P1',
        'comment': '评论',
      };
      final item = ChangeItem.fromJson(json);
      expect(item.id, 2);
      expect(item.clauseLocation, '第三条');
      expect(item.revisedText, isNull);
      expect(item.riskLevel, RiskLevel.p1);
    });
  });

  group('ChangeList', () {
    test('toJson and fromJson round-trip', () {
      final list = ChangeList(
        items: [
          ChangeItem(
            id: 1,
            clauseLocation: '第一条',
            originalText: '原文1',
            revisedText: '修订1',
            reason: '理由1',
            riskLevel: RiskLevel.p0,
            comment: '评论1',
          ),
          ChangeItem(
            id: 2,
            clauseLocation: '第二条',
            originalText: '原文2',
            revisedText: null,
            reason: '理由2',
            riskLevel: RiskLevel.p2,
            comment: '评论2',
          ),
        ],
        sourceDocument: '合同.docx',
        createdAt: DateTime(2026, 8, 14),
      );
      final jsonStr = list.toJson();
      final parsed = ChangeList.fromJson(jsonStr);
      expect(parsed, isNotNull);
      expect(parsed!.items.length, 2);
      expect(parsed.items[0].id, 1);
      expect(parsed.items[0].revisedText, '修订1');
      expect(parsed.items[1].revisedText, isNull);
      expect(parsed.sourceDocument, '合同.docx');
    });

    test('fromJson returns null for invalid JSON', () {
      expect(ChangeList.fromJson('not json'), isNull);
      expect(ChangeList.fromJson(''), isNull);
    });

    test('validate returns empty for valid list', () {
      final list = ChangeList(
        items: [
          ChangeItem(
            id: 1,
            clauseLocation: '第一条',
            originalText: '原文',
            revisedText: '修订',
            reason: '理由',
            riskLevel: RiskLevel.p0,
            comment: '评论',
          ),
        ],
        sourceDocument: 'doc.docx',
        createdAt: DateTime.now(),
      );
      expect(list.validate(), isEmpty);
    });

    test('validate returns error for empty items', () {
      final list = ChangeList(
        items: [],
        sourceDocument: 'doc.docx',
        createdAt: DateTime.now(),
      );
      final errors = list.validate();
      expect(errors, isNotEmpty);
      expect(errors.first, contains('at least one item'));
    });

    test('validate returns error for duplicate IDs', () {
      final list = ChangeList(
        items: [
          ChangeItem(
            id: 1,
            clauseLocation: 'a',
            originalText: 'a',
            reason: 'a',
            riskLevel: RiskLevel.p0,
            comment: 'a',
          ),
          ChangeItem(
            id: 1,
            clauseLocation: 'b',
            originalText: 'b',
            reason: 'b',
            riskLevel: RiskLevel.p0,
            comment: 'b',
          ),
        ],
        sourceDocument: 'doc.docx',
        createdAt: DateTime.now(),
      );
      final errors = list.validate();
      expect(errors.any((e) => e.contains('Duplicate')), isTrue);
    });

    test('validate returns error for empty comment', () {
      final list = ChangeList(
        items: [
          ChangeItem(
            id: 1,
            clauseLocation: 'a',
            originalText: 'a',
            reason: 'a',
            riskLevel: RiskLevel.p0,
            comment: '',
          ),
        ],
        sourceDocument: 'doc.docx',
        createdAt: DateTime.now(),
      );
      final errors = list.validate();
      expect(errors.any((e) => e.contains('comment')), isTrue);
    });
  });
}
