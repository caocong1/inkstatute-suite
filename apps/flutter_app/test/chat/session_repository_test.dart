import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/chat/session_database.dart';
import 'package:flutter_app/chat/session_repository.dart';
import 'package:flutter_app/chat/chat_models.dart';
import 'dart:convert';

void main() {
  late SessionDatabase db;
  late SessionRepository repo;

  setUp(() async {
    db = SessionDatabase.inMemory();
    await db.init();
    repo = SessionRepository(db);
  });

  tearDown(() async {
    await db.close();
  });

  test('createSession and getSession round-trip', () async {
    final session = ChatSession(
      id: 's1',
      providerName: 'DeepSeek',
      modelConfig: 'deepseek-chat',
      title: '合同审查',
      createdAt: DateTime(2026, 8, 14),
      messages: [
        UserMessage(text: '帮我审查合同', timestamp: DateTime(2026, 8, 14, 10)),
        AssistantMessage(
          text: '审查结果',
          timestamp: DateTime(2026, 8, 14, 10, 1),
          citations: [
            Citation(
              source: '合同法52条',
              citationType: CitationType.verified,
              text: 'cite',
            ),
          ],
        ),
      ],
    );

    await repo.createSession(session);
    final loaded = await repo.getSession('s1');

    expect(loaded, isNotNull);
    expect(loaded!.id, 's1');
    expect(loaded.providerName, 'DeepSeek');
    expect(loaded.modelConfig, 'deepseek-chat');
    expect(loaded.title, '合同审查');
    expect(loaded.messages.length, 2);
    expect(loaded.messages[0], isA<UserMessage>());
    expect((loaded.messages[0] as UserMessage).text, '帮我审查合同');
    expect(loaded.messages[1], isA<AssistantMessage>());
    expect((loaded.messages[1] as AssistantMessage).text, '审查结果');
    expect((loaded.messages[1] as AssistantMessage).citations.length, 1);
  });

  test('getSession returns null for non-existent session', () async {
    final loaded = await repo.getSession('nonexistent');
    expect(loaded, isNull);
  });

  test('listSessions returns all sessions', () async {
    await repo.createSession(ChatSession(
      id: 's1',
      providerName: 'DeepSeek',
      modelConfig: 'deepseek-chat',
      title: 'Session 1',
      createdAt: DateTime(2026, 8, 14),
    ));
    await repo.createSession(ChatSession(
      id: 's2',
      providerName: 'OpenAI',
      modelConfig: 'gpt-4o',
      title: 'Session 2',
      createdAt: DateTime(2026, 8, 15),
    ));

    final sessions = await repo.listSessions();
    expect(sessions.length, 2);
  });

  test('listSessions filters by provider', () async {
    await repo.createSession(ChatSession(
      id: 's1',
      providerName: 'DeepSeek',
      modelConfig: 'deepseek-chat',
      title: 'Session 1',
      createdAt: DateTime(2026, 8, 14),
    ));
    await repo.createSession(ChatSession(
      id: 's2',
      providerName: 'OpenAI',
      modelConfig: 'gpt-4o',
      title: 'Session 2',
      createdAt: DateTime(2026, 8, 15),
    ));

    final sessions = await repo.listSessions(providerName: 'DeepSeek');
    expect(sessions.length, 1);
    expect(sessions.first.id, 's1');
  });

  test('addMessage appends to existing session', () async {
    await repo.createSession(ChatSession(
      id: 's1',
      providerName: 'DeepSeek',
      modelConfig: 'deepseek-chat',
      title: 'Session 1',
      createdAt: DateTime(2026, 8, 14),
    ));

    await repo.addMessage('s1', UserMessage(text: '追加消息', timestamp: DateTime.now()));

    final loaded = await repo.getSession('s1');
    expect(loaded!.messages.length, 1);
    expect((loaded.messages[0] as UserMessage).text, '追加消息');
  });

  test('deleteSession removes session and all related records', () async {
    await repo.createSession(ChatSession(
      id: 's1',
      providerName: 'DeepSeek',
      modelConfig: 'deepseek-chat',
      title: 'Session 1',
      createdAt: DateTime(2026, 8, 14),
      messages: [
        UserMessage(text: '你好', timestamp: DateTime.now()),
        AssistantMessage(
          text: '您好',
          timestamp: DateTime.now(),
          citations: [
            Citation(source: '法条', citationType: CitationType.verified, text: ''),
          ],
        ),
      ],
    ));

    await repo.deleteSession('s1');

    final loaded = await repo.getSession('s1');
    expect(loaded, isNull);

    // Verify messages are also deleted
    final msgRows = await db.select('SELECT * FROM messages WHERE session_id = ?', ['s1']);
    expect(msgRows, isEmpty);
  });

  test('exportSession returns JSON string', () async {
    await repo.createSession(ChatSession(
      id: 's1',
      providerName: 'DeepSeek',
      modelConfig: 'deepseek-chat',
      title: '合同审查',
      createdAt: DateTime(2026, 8, 14),
      messages: [
        UserMessage(text: '你好', timestamp: DateTime(2026, 8, 14, 10)),
      ],
    ));

    final json = await repo.exportSession('s1');
    final parsed = jsonDecode(json) as Map<String, dynamic>;

    expect(parsed['id'], 's1');
    expect(parsed['providerName'], 'DeepSeek');
    expect(parsed['modelConfig'], 'deepseek-chat');
    expect(parsed['title'], '合同审查');
    expect(parsed['messages'], isA<List>());
    expect((parsed['messages'] as List).length, 1);
  });

  test('exportSession returns {} for non-existent session', () async {
    final json = await repo.exportSession('nonexistent');
    expect(json, '{}');
  });

  test('listProviders returns distinct providers', () async {
    await repo.createSession(ChatSession(
      id: 's1',
      providerName: 'DeepSeek',
      modelConfig: 'deepseek-chat',
      title: 'S1',
      createdAt: DateTime.now(),
    ));
    await repo.createSession(ChatSession(
      id: 's2',
      providerName: 'OpenAI',
      modelConfig: 'gpt-4o',
      title: 'S2',
      createdAt: DateTime.now(),
    ));
    await repo.createSession(ChatSession(
      id: 's3',
      providerName: 'DeepSeek',
      modelConfig: 'deepseek-chat',
      title: 'S3',
      createdAt: DateTime.now(),
    ));

    final providers = await repo.listProviders();
    expect(providers.length, 2);
    expect(providers, containsAll(['DeepSeek', 'OpenAI']));
  });
}
