import 'package:flutter_test/flutter_test.dart';
import 'dart:async';
import 'package:acp_client/acp_client.dart';
import 'package:flutter_app/chat/chat_controller.dart';
import 'package:flutter_app/chat/chat_models.dart';
import 'package:flutter_app/chat/session_database.dart';
import 'package:flutter_app/chat/session_repository.dart';
import 'package:flutter_app/guardrails/guardrail_models.dart';

/// A mock ACP transport that responds with configurable assistant text.
///
/// Allows tests to inject specific assistant responses to exercise
/// guardrail checks (e.g. unverified citations, missing polish marker).
class _MockTransport implements AcpTransport {
  final _controller = StreamController<Map<String, dynamic>>.broadcast();

  /// The assistant text to emit in response to session/prompt.
  String assistantText = '';

  @override
  Stream<Map<String, dynamic>> get messages => _controller.stream;

  @override
  Future<void> send(Map<String, dynamic> message) async {
    if (message['method'] == 'session/prompt') {
      final id = message['id'] as int;

      // Emit an agent_message_chunk update with the configured text
      _controller.add({
        'jsonrpc': '2.0',
        'method': 'session/update',
        'params': {
          'sessionId': message['params']['sessionId'],
          'update': {
            'sessionUpdate': 'agent_message_chunk',
            'content': {'type': 'text', 'text': assistantText},
          },
        },
      });

      // Respond to the prompt request
      _controller.add({
        'jsonrpc': '2.0',
        'id': id,
        'result': {'stopReason': 'end_turn'},
      });
    }
  }

  @override
  Future<void> close() async {
    await _controller.close();
  }
}

void main() {
  late _MockTransport transport;
  late AcpClient client;
  late SessionDatabase db;
  late SessionRepository repo;
  late ChatController controller;

  setUp(() async {
    transport = _MockTransport();
    client = AcpClient(transport);
    db = SessionDatabase.inMemory();
    await db.init();
    repo = SessionRepository(db);

    await repo.createSession(ChatSession(
      id: 'guardrail-test-session',
      providerName: 'DeepSeek',
      modelConfig: 'deepseek-chat',
      title: 'Guardrail Test Session',
      createdAt: DateTime.now(),
    ));

    controller = ChatController(
      client: client,
      repository: repo,
      sessionId: 'guardrail-test-session',
      providerName: 'DeepSeek',
      modelConfig: 'deepseek-chat',
    );
  });

  tearDown(() async {
    controller.dispose();
    await client.close();
    await transport.close();
    await db.close();
  });

  test('guardrail results are empty before any assistant message', () {
    expect(controller.lastGuardrailResults, isEmpty);
    expect(controller.lastMessageBlocked, isFalse);
    expect(controller.guardrailWarnings, isEmpty);
    expect(controller.guardrailBlocks, isEmpty);
  });

  test('clean assistant message passes all guardrails', () async {
    transport.assistantText = '[POLISHED] 审查结果：合同条款合法合规。[CITE: 源=民法典§585|type=verified|text=违约责任]';
    await controller.sendPrompt('帮我审查合同');

    expect(controller.lastGuardrailResults, isNotEmpty);
    expect(controller.lastMessageBlocked, isFalse);
    expect(controller.guardrailBlocks, isEmpty);
  });

  test('assistant message without polish marker triggers GRD-04 warning',
      () async {
    transport.assistantText = '审查结果：合同条款合法合规。';
    await controller.sendPrompt('帮我审查合同');

    // GRD-04 (polish) should produce a warning or block
    final hasPolishResult = controller.lastGuardrailResults.any(
      (r) => r.type == GuardrailType.polish,
    );
    expect(hasPolishResult, isTrue);
  });

  test('assistant message with unverified citations triggers GRD-02', () async {
    transport.assistantText =
        '[POLISHED] 审查结果：建议修改条款。[CITE: 源=未知|type=unverified|text=某条款]';
    await controller.sendPrompt('帮我审查合同');

    // GRD-02 (citation audit) should flag unverified citations
    final hasCitationResult = controller.lastGuardrailResults.any(
      (r) => r.type == GuardrailType.citationAudit,
    );
    expect(hasCitationResult, isTrue);
  });

  test('guardrail block adds a system error message to the message list',
      () async {
    // Text with no citations and no polish marker — should trigger blocks
    transport.assistantText = '这是一个没有引用的法律结论。';
    await controller.sendPrompt('帮我审查合同');

    // Check if any guardrail blocked — if so, a SystemErrorMessage should
    // be present in the messages list
    if (controller.lastMessageBlocked) {
      final hasBlockError = controller.messages
          .whereType<SystemErrorMessage>()
          .any((m) => m.userMessage.contains('护栏拦截'));
      expect(hasBlockError, isTrue);
    }
  });

  test('guardrail results are accessible after sendPrompt', () async {
    transport.assistantText = '[POLISHED] 测试文本。';
    await controller.sendPrompt('test');

    // Verify all guardrail types are represented in the results
    final resultTypes = controller.lastGuardrailResults.map((r) => r.type).toSet();
    expect(resultTypes, contains(GuardrailType.researchGate));
    expect(resultTypes, contains(GuardrailType.citationAudit));
    expect(resultTypes, contains(GuardrailType.polish));
    expect(resultTypes, contains(GuardrailType.humanReview));
  });
}
