import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/chat/session_database.dart';

void main() {
  late SessionDatabase db;

  setUp(() async {
    db = SessionDatabase.inMemory();
    await db.init();
  });

  tearDown(() async {
    await db.close();
  });

  test('init creates all tables', () async {
    final sessionRows = await db.select('SELECT * FROM sessions');
    expect(sessionRows, isEmpty);

    final msgRows = await db.select('SELECT * FROM messages');
    expect(msgRows, isEmpty);

    final citeRows = await db.select('SELECT * FROM citations');
    expect(citeRows, isEmpty);

    final approvalRows = await db.select('SELECT * FROM approvals');
    expect(approvalRows, isEmpty);
  });

  test('can insert and query a session', () async {
    await db.exec(
      'INSERT INTO sessions (id, practice_area, title, created_at) VALUES (?, ?, ?, ?)',
      ['s1', '商事法', '合同审查', DateTime(2026, 8, 14).millisecondsSinceEpoch],
    );

    final rows = await db.select('SELECT * FROM sessions');
    expect(rows.length, 1);
    expect(rows.first['id'], 's1');
    expect(rows.first['practice_area'], '商事法');
  });

  test('can insert and query messages', () async {
    await db.exec(
      'INSERT INTO messages (id, session_id, role, text, created_at, sort_order) VALUES (?, ?, ?, ?, ?, ?)',
      ['m1', 's1', 'user', '你好', DateTime.now().millisecondsSinceEpoch, 0],
    );

    final rows = await db.select('SELECT * FROM messages');
    expect(rows.length, 1);
    expect(rows.first['text'], '你好');
  });

  test('close does not throw', () async {
    await db.close();
  });
}
