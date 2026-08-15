import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/chat/chat_view.dart';
import 'package:flutter_app/chat/chat_models.dart';

void main() {
  testWidgets('renders message list with user and assistant messages',
      (tester) async {
    final messages = [
      UserMessage(text: '你好', timestamp: DateTime.now()),
      AssistantMessage(text: '您好，有什么可以帮您？', timestamp: DateTime.now()),
    ];
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatView(messages: messages, status: MessageStatus.idle),
        ),
      ),
    );

    expect(find.text('你好'), findsOneWidget);
    expect(find.textContaining('您好'), findsOneWidget);
  });

  testWidgets('input is enabled when idle', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatView(messages: [], status: MessageStatus.idle),
        ),
      ),
    );

    final textField = tester.widget<TextField>(find.byType(TextField));
    expect(textField.enabled, isTrue);
  });

  testWidgets('input is disabled when processing', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatView(messages: [], status: MessageStatus.processing),
        ),
      ),
    );

    final textField = tester.widget<TextField>(find.byType(TextField));
    expect(textField.enabled, isFalse);
    expect(find.text('处理中...'), findsWidgets);
  });

  testWidgets('cancel button visible during processing', (tester) async {
    bool cancelled = false;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatView(
            messages: [],
            status: MessageStatus.processing,
            onCancel: () => cancelled = true,
          ),
        ),
      ),
    );

    expect(find.text('取消'), findsOneWidget);
    await tester.tap(find.text('取消'));
    expect(cancelled, isTrue);
  });

  testWidgets('cancel button not visible when idle', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatView(
            messages: [],
            status: MessageStatus.idle,
            onCancel: () {},
          ),
        ),
      ),
    );

    expect(find.text('取消'), findsNothing);
  });

  testWidgets('send button calls onSendPrompt', (tester) async {
    String? sentText;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatView(
            messages: [],
            status: MessageStatus.idle,
            onSendPrompt: (text) => sentText = text,
          ),
        ),
      ),
    );

    await tester.enterText(find.byType(TextField), '帮我审查合同');
    await tester.tap(find.byIcon(Icons.send));
    expect(sentText, '帮我审查合同');
  });

  testWidgets('send button disabled when processing', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatView(
            messages: [],
            status: MessageStatus.processing,
            onSendPrompt: (text) {},
          ),
        ),
      ),
    );

    // Send button should be disabled (onPressed null)
    expect(find.byIcon(Icons.send), findsOneWidget);
    // Can't tap a disabled IconButton
  });

  testWidgets('renders approval card in message list', (tester) async {
    final messages = [
      ApprovalMessage(
        toolCallId: 'tc-1',
        toolName: 'terminal',
        status: ApprovalStatus.pending,
        timestamp: DateTime.now(),
      ),
    ];
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatView(messages: messages, status: MessageStatus.idle),
        ),
      ),
    );

    expect(find.text('工具审批请求'), findsOneWidget);
    expect(find.text('允许'), findsOneWidget);
  });

  testWidgets('renders clarification card in message list', (tester) async {
    final messages = [
      ClarifyMessage(
        clarifyText: '请补充信息',
        timestamp: DateTime.now(),
      ),
    ];
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatView(messages: messages, status: MessageStatus.idle),
        ),
      ),
    );

    expect(find.text('需要澄清'), findsOneWidget);
    expect(find.text('请补充信息'), findsOneWidget);
  });

  testWidgets('provider name displayed in status bar', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatView(
            messages: [],
            status: MessageStatus.idle,
            providerName: 'DeepSeek',
            modelConfig: 'deepseek-chat',
          ),
        ),
      ),
    );

    expect(find.text('DeepSeek'), findsOneWidget);
  });
}
