import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/chat/chat_message_widget.dart';
import 'package:flutter_app/chat/chat_models.dart';

void main() {
  testWidgets('renders user message as right-aligned bubble', (tester) async {
    final msg = UserMessage(text: '帮我审查合同', timestamp: DateTime.now());
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: ChatMessageWidget(message: msg))),
    );

    expect(find.text('帮我审查合同'), findsOneWidget);
    // User messages are right-aligned
    final align = tester.widget<Align>(find.byType(Align));
    expect(align.alignment, Alignment.centerRight);
  });

  testWidgets('renders assistant message with clean text', (tester) async {
    final msg = AssistantMessage(
      text: '审查结果 [CITE:verified:合同法52条]',
      timestamp: DateTime.now(),
    );
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: ChatMessageWidget(message: msg))),
    );

    // Clean text should be visible (marker removed)
    expect(find.textContaining('审查结果'), findsOneWidget);
    // Citation badge should be rendered
    expect(find.text('合同法52条'), findsOneWidget);
  });

  testWidgets('renders system error message', (tester) async {
    final msg = SystemErrorMessage(
      errorType: ErrorType.engineNotStarted,
      userMessage: '引擎未启动，请检查安装',
      timestamp: DateTime.now(),
    );
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: ChatMessageWidget(message: msg))),
    );

    expect(find.text('引擎未启动，请检查安装'), findsOneWidget);
    expect(find.byIcon(Icons.error_outline), findsOneWidget);
  });

  testWidgets('renders approval message with pending status', (tester) async {
    final msg = ApprovalMessage(
      toolCallId: 'tc-1',
      toolName: 'terminal',
      status: ApprovalStatus.pending,
      timestamp: DateTime.now(),
    );
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: ChatMessageWidget(message: msg))),
    );

    expect(find.textContaining('terminal'), findsOneWidget);
    expect(find.text('等待审批'), findsOneWidget);
  });

  testWidgets('renders clarify message', (tester) async {
    final msg = ClarifyMessage(
      clarifyText: '请补充合同类型',
      timestamp: DateTime.now(),
    );
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: ChatMessageWidget(message: msg))),
    );

    expect(find.text('需要澄清'), findsOneWidget);
    expect(find.text('请补充合同类型'), findsOneWidget);
  });
}
