import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/chat/approval_card_widget.dart';
import 'package:flutter_app/chat/chat_models.dart';

void main() {
  testWidgets('renders pending approval with allow/reject buttons',
      (tester) async {
    final msg = ApprovalMessage(
      toolCallId: 'tc-1',
      toolName: 'terminal',
      status: ApprovalStatus.pending,
      timestamp: DateTime.now(),
    );
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: ApprovalCardWidget(message: msg))),
    );

    expect(find.text('工具审批请求'), findsOneWidget);
    expect(find.textContaining('terminal'), findsOneWidget);
    expect(find.text('允许'), findsOneWidget);
    expect(find.text('拒绝'), findsOneWidget);
  });

  testWidgets('calls onAllow when allow button pressed', (tester) async {
    String? allowedId;
    final msg = ApprovalMessage(
      toolCallId: 'tc-2',
      toolName: 'terminal',
      status: ApprovalStatus.pending,
      timestamp: DateTime.now(),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ApprovalCardWidget(
            message: msg,
            onAllow: (id) => allowedId = id,
          ),
        ),
      ),
    );

    await tester.tap(find.text('允许'));
    expect(allowedId, 'tc-2');
  });

  testWidgets('calls onReject when reject button pressed', (tester) async {
    String? rejectedId;
    final msg = ApprovalMessage(
      toolCallId: 'tc-3',
      toolName: 'execute_code',
      status: ApprovalStatus.pending,
      timestamp: DateTime.now(),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ApprovalCardWidget(
            message: msg,
            onReject: (id) => rejectedId = id,
          ),
        ),
      ),
    );

    await tester.tap(find.text('拒绝'));
    expect(rejectedId, 'tc-3');
  });

  testWidgets('renders approved status without buttons', (tester) async {
    final msg = ApprovalMessage(
      toolCallId: 'tc-4',
      toolName: 'terminal',
      status: ApprovalStatus.approved,
      timestamp: DateTime.now(),
    );
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: ApprovalCardWidget(message: msg))),
    );

    expect(find.text('已允许'), findsOneWidget);
    expect(find.text('允许'), findsNothing);
    expect(find.text('拒绝'), findsNothing);
  });

  testWidgets('renders rejected status without buttons', (tester) async {
    final msg = ApprovalMessage(
      toolCallId: 'tc-5',
      toolName: 'terminal',
      status: ApprovalStatus.rejected,
      timestamp: DateTime.now(),
    );
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: ApprovalCardWidget(message: msg))),
    );

    expect(find.text('已拒绝'), findsOneWidget);
    expect(find.text('允许'), findsNothing);
  });

  testWidgets('no batch approval control exists', (tester) async {
    final msg = ApprovalMessage(
      toolCallId: 'tc-6',
      toolName: 'terminal',
      status: ApprovalStatus.pending,
      timestamp: DateTime.now(),
    );
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: ApprovalCardWidget(message: msg))),
    );

    // No "allow all" or "batch" text should appear
    expect(find.textContaining('批量'), findsNothing);
    expect(find.textContaining('全部'), findsNothing);
  });
}
