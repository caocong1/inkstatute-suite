import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/wizard/first_run_wizard.dart';
import 'package:flutter_app/wizard/wizard_models.dart';

void main() {
  testWidgets('FirstRunWizard shows welcome and step 1', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: FirstRunWizard(onComplete: (_) {}),
      ),
    );

    expect(find.text('欢迎使用墨律'), findsOneWidget);
    expect(find.text('步骤 1 / 3'), findsOneWidget);
    expect(find.text('选择您的执业方向'), findsOneWidget);
  });

  testWidgets('practice area selection enables next button',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: FirstRunWizard(onComplete: (_) {}),
      ),
    );

    // Next button should be disabled initially
    final nextButton = find.widgetWithText(ElevatedButton, '下一步');
    final ElevatedButton button = tester.widget(nextButton);
    expect(button.enabled, isFalse);

    // Tap a practice area
    await tester.tap(find.text('商事法'));
    await tester.pump();

    // Next button should now be enabled
    final ElevatedButton buttonAfter = tester.widget(nextButton);
    expect(buttonAfter.enabled, isTrue);
  });

  testWidgets('navigates to API key step', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: FirstRunWizard(onComplete: (_) {}),
      ),
    );

    // Select practice area
    await tester.tap(find.text('商事法'));
    await tester.pump();

    // Tap next
    await tester.tap(find.text('下一步'));
    await tester.pumpAndSettle();

    expect(find.text('步骤 2 / 3'), findsOneWidget);
    expect(find.text('输入 DeepSeek API 密钥'), findsOneWidget);
  });

  testWidgets('back button returns to previous step', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: FirstRunWizard(onComplete: (_) {}),
      ),
    );

    // Navigate to step 2
    await tester.tap(find.text('商事法'));
    await tester.pump();
    await tester.tap(find.text('下一步'));
    await tester.pumpAndSettle();

    expect(find.text('步骤 2 / 3'), findsOneWidget);

    // Go back
    await tester.tap(find.text('上一步'));
    await tester.pumpAndSettle();

    expect(find.text('步骤 1 / 3'), findsOneWidget);
    expect(find.text('选择您的执业方向'), findsOneWidget);
  });

  testWidgets('API key input enables next button', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: FirstRunWizard(onComplete: (_) {}),
      ),
    );

    // Navigate to step 2
    await tester.tap(find.text('商事法'));
    await tester.pump();
    await tester.tap(find.text('下一步'));
    await tester.pumpAndSettle();

    // Next should be disabled
    final nextButton = find.widgetWithText(ElevatedButton, '下一步');
    expect((tester.widget(nextButton) as ElevatedButton).enabled, isFalse);

    // Enter API key
    await tester.enterText(find.byType(TextField), 'sk-test-key');
    await tester.pump();

    // Next should be enabled
    expect((tester.widget(nextButton) as ElevatedButton).enabled, isTrue);
  });

  testWidgets('completes wizard and calls onComplete', (WidgetTester tester) async {
    WizardState? completedState;

    await tester.pumpWidget(
      MaterialApp(
        home: FirstRunWizard(
          onComplete: (state) {
            completedState = state;
          },
        ),
      ),
    );

    // Step 1: select practice area
    await tester.tap(find.text('商事法'));
    await tester.pump();
    await tester.tap(find.text('下一步'));
    await tester.pumpAndSettle();

    // Step 2: enter API key
    await tester.enterText(find.byType(TextField), 'sk-test-key');
    await tester.pump();
    await tester.tap(find.text('下一步'));
    await tester.pumpAndSettle();

    // Step 3: confirm model
    expect(find.text('步骤 3 / 3'), findsOneWidget);
    expect(find.text('确认模型配置'), findsOneWidget);
    await tester.tap(find.text('完成'));
    await tester.pumpAndSettle();

    expect(completedState, isNotNull);
    expect(completedState!.step, WizardStep.complete);
    expect(completedState!.selectedPracticeArea?.name, '商事法');
    expect(completedState!.apiKey, 'sk-test-key');
    expect(completedState!.modelConfig, 'deepseek-chat');
  });

  testWidgets('shows all 5 practice area options', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: FirstRunWizard(onComplete: (_) {}),
      ),
    );

    // ListView only renders visible items; scroll to find all options.
    expect(find.text('商事法'), findsOneWidget);
    expect(find.text('劳动法'), findsOneWidget);
    expect(find.text('家事法'), findsOneWidget);
    // 诉讼法 and 通用法律 may be off-screen; scroll down.
    await tester.scrollUntilVisible(
      find.text('诉讼法'),
      100,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.text('诉讼法'), findsOneWidget);

    await tester.scrollUntilVisible(
      find.text('通用法律'),
      100,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.text('通用法律'), findsOneWidget);
  });

  testWidgets('no back button on first step', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: FirstRunWizard(onComplete: (_) {}),
      ),
    );

    expect(find.text('上一步'), findsNothing);
  });
}
