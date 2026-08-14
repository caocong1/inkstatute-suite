import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/chat/clarification_card_widget.dart';
import 'package:flutter_app/chat/chat_models.dart';

void main() {
  testWidgets('renders clarify question with input and submit button',
      (tester) async {
    final msg = ClarifyMessage(
      clarifyText: '请补充合同类型',
      timestamp: DateTime.now(),
    );
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: ClarificationCardWidget(message: msg))),
    );

    expect(find.text('需要澄清'), findsOneWidget);
    expect(find.text('请补充合同类型'), findsOneWidget);
    expect(find.byType(TextField), findsOneWidget);
    expect(find.text('提交补充'), findsOneWidget);
  });

  testWidgets('calls onSubmit with clarify text and user response',
      (tester) async {
    String? submittedClarify;
    String? submittedResponse;
    final msg = ClarifyMessage(
      clarifyText: '请补充合同类型',
      timestamp: DateTime.now(),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ClarificationCardWidget(
            message: msg,
            onSubmit: (clarify, response) {
              submittedClarify = clarify;
              submittedResponse = response;
            },
          ),
        ),
      ),
    );

    await tester.enterText(find.byType(TextField), '买卖合同');
    await tester.tap(find.text('提交补充'));

    expect(submittedClarify, '请补充合同类型');
    expect(submittedResponse, '买卖合同');
  });

  testWidgets('shows collapsed view when userResponse is set', (tester) async {
    final msg = ClarifyMessage(
      clarifyText: '请补充合同类型',
      timestamp: DateTime.now(),
      userResponse: '买卖合同',
    );
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: ClarificationCardWidget(message: msg))),
    );

    expect(find.textContaining('买卖合同'), findsOneWidget);
    // Input field should not be visible when already answered
    expect(find.byType(TextField), findsNothing);
  });

  testWidgets('does not submit empty response', (tester) async {
    bool submitted = false;
    final msg = ClarifyMessage(
      clarifyText: '请补充',
      timestamp: DateTime.now(),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ClarificationCardWidget(
            message: msg,
            onSubmit: (_, _) => submitted = true,
          ),
        ),
      ),
    );

    await tester.tap(find.text('提交补充'));
    expect(submitted, isFalse);
  });
}
