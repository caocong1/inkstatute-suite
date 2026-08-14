import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/export/change_list_schema.dart';
import 'package:flutter_app/export/change_list_parser.dart';

void main() {
  group('ChangeListParser.extractFromText', () {
    test('extracts from fenced json block', () {
      const text = '''
审查结果如下：

```json
{
  "sourceDocument": "合同.docx",
  "createdAt": "2026-08-14T10:00:00.000Z",
  "items": [
    {
      "id": 1,
      "clauseLocation": "第十五条",
      "originalText": "根据合同法",
      "revisedText": "根据民法典",
      "reason": "法律已废止",
      "riskLevel": "P0",
      "comment": "必须修正"
    }
  ]
}
```
''';
      final list = ChangeListParser.extractFromText(text);
      expect(list, isNotNull);
      expect(list!.items.length, 1);
      expect(list.items[0].id, 1);
      expect(list.items[0].riskLevel, RiskLevel.p0);
      expect(list.sourceDocument, '合同.docx');
    });

    test('extracts from [CHANGE_LIST: ...] block', () {
      const text = '''
审查结果：

[CHANGE_LIST: {"sourceDocument":"doc.docx","createdAt":"2026-08-14T10:00:00.000Z","items":[{"id":1,"clauseLocation":"第一条","originalText":"原文","revisedText":"修订","reason":"理由","riskLevel":"P1","comment":"评论"}]}]
''';
      final list = ChangeListParser.extractFromText(text);
      expect(list, isNotNull);
      expect(list!.items.length, 1);
      expect(list.items[0].riskLevel, RiskLevel.p1);
    });

    test('returns null when no change list found', () {
      const text = '这是一段普通的审查意见，没有变更清单。';
      final list = ChangeListParser.extractFromText(text);
      expect(list, isNull);
    });

    test('returns null for invalid JSON in fenced block', () {
      const text = '```json\nnot valid json\n```';
      final list = ChangeListParser.extractFromText(text);
      expect(list, isNull);
    });

    test('returns null for empty items list', () {
      const text = '''
```json
{
  "sourceDocument": "doc.docx",
  "createdAt": "2026-08-14T10:00:00.000Z",
  "items": []
}
```
''';
      final list = ChangeListParser.extractFromText(text);
      expect(list, isNull);
    });

    test('extracts multiple items', () {
      const text = '''
```json
{
  "sourceDocument": "合同.docx",
  "createdAt": "2026-08-14T10:00:00.000Z",
  "items": [
    {"id":1,"clauseLocation":"第一条","originalText":"a","revisedText":"b","reason":"r","riskLevel":"P0","comment":"c"},
    {"id":2,"clauseLocation":"第二条","originalText":"x","revisedText":null,"reason":"r","riskLevel":"P2","comment":"c2"}
  ]
}
```
''';
      final list = ChangeListParser.extractFromText(text);
      expect(list, isNotNull);
      expect(list!.items.length, 2);
      expect(list.items[0].revisedText, 'b');
      expect(list.items[1].revisedText, isNull);
    });
  });

  group('ChangeListParser.extractFromMessage', () {
    test('extracts from AssistantMessage', () {
      final msg = AssistantMessage(
        text: '''
```json
{
  "sourceDocument": "doc.docx",
  "createdAt": "2026-08-14T10:00:00.000Z",
  "items": [
    {"id":1,"clauseLocation":"第一条","originalText":"a","revisedText":"b","reason":"r","riskLevel":"P0","comment":"c"}
  ]
}
```
''',
        timestamp: DateTime.now(),
      );
      final list = ChangeListParser.extractFromMessage(msg);
      expect(list, isNotNull);
      expect(list!.items.length, 1);
    });

    test('returns null when message has no change list', () {
      final msg = AssistantMessage(
        text: '普通审查意见',
        timestamp: DateTime.now(),
      );
      final list = ChangeListParser.extractFromMessage(msg);
      expect(list, isNull);
    });
  });

  group('ChangeListParser.extractJsonBlock', () {
    test('extracts from fenced json block', () {
      const text = '```json\n{"key":"value"}\n```';
      final json = ChangeListParser.extractJsonBlock(text);
      expect(json, '{"key":"value"}');
    });

    test('extracts from CHANGE_LIST block', () {
      const text = '[CHANGE_LIST: {"key":"value"}]';
      final json = ChangeListParser.extractJsonBlock(text);
      expect(json, '{"key":"value"}');
    });

    test('returns null when no block found', () {
      const text = 'no json here';
      final json = ChangeListParser.extractJsonBlock(text);
      expect(json, isNull);
    });
  });

  group('Model-never-writes-docx assertion', () {
    test('ChangeList is the only export input format', () {
      // The export path only accepts ChangeList objects, not raw text.
      // This test documents the constraint: the parser produces a
      // ChangeList, and the exporter only accepts ChangeList.
      final msg = AssistantMessage(
        text: '''
```json
{
  "sourceDocument": "doc.docx",
  "createdAt": "2026-08-14T10:00:00.000Z",
  "items": [
    {"id":1,"clauseLocation":"第一条","originalText":"a","revisedText":"b","reason":"r","riskLevel":"P0","comment":"c"}
  ]
}
```
''',
        timestamp: DateTime.now(),
      );
      final list = ChangeListParser.extractFromMessage(msg);
      expect(list, isA<ChangeList>());
      // The ChangeList is the validated input to the docx exporter.
      // Raw model text never reaches the docx writer.
    });
  });
}
