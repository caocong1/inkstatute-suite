import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/wizard/first_run_wizard.dart';
import 'package:flutter_app/wizard/wizard_models.dart';
import 'package:flutter_app/wizard/llm_provider.dart';

void main() {
  testWidgets('FirstRunWizard shows welcome and step 1', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: FirstRunWizard(onComplete: (_) {}),
      ),
    );

    expect(find.text('欢迎使用墨律'), findsOneWidget);
    expect(find.text('步骤 1 / 2'), findsOneWidget);
    expect(find.text('选择 LLM 供应商并输入 API 密钥'), findsOneWidget);
  });

  testWidgets('next button disabled until API key entered',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: FirstRunWizard(onComplete: (_) {}),
      ),
    );

    // Next button should be disabled initially (no API key)
    final nextButton = find.widgetWithText(ElevatedButton, '下一步');
    final ElevatedButton button = tester.widget(nextButton);
    expect(button.enabled, isFalse);

    // Enter API key (first TextField is the API key field)
    await tester.enterText(
      find.byType(TextField).at(0), 'sk-test-key');
    await tester.pump();

    // Next button should now be enabled
    final ElevatedButton buttonAfter = tester.widget(nextButton);
    expect(buttonAfter.enabled, isTrue);
  });

  testWidgets('navigates to model confirmation step', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: FirstRunWizard(onComplete: (_) {}),
      ),
    );

    // Enter API key (DeepSeek is selected by default)
    await tester.enterText(
      find.byType(TextField).at(0), 'sk-test-key');
    await tester.pump();

    // Ensure the next button is visible and tap it
    await tester.ensureVisible(find.text('下一步'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('下一步'));
    await tester.pumpAndSettle();

    expect(find.text('步骤 2 / 2'), findsOneWidget);
    expect(find.text('确认模型配置'), findsOneWidget);
  });

  testWidgets('back button returns to previous step', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: FirstRunWizard(onComplete: (_) {}),
      ),
    );

    // Navigate to step 2
    await tester.enterText(
      find.byType(TextField).at(0), 'sk-test-key');
    await tester.pump();
    await tester.ensureVisible(find.text('下一步'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('下一步'));
    await tester.pumpAndSettle();

    expect(find.text('步骤 2 / 2'), findsOneWidget);

    // Go back
    await tester.ensureVisible(find.text('上一步'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('上一步'));
    await tester.pumpAndSettle();

    expect(find.text('步骤 1 / 2'), findsOneWidget);
    expect(find.text('选择 LLM 供应商并输入 API 密钥'), findsOneWidget);
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

    // Step 1: enter API key (DeepSeek is default provider)
    await tester.enterText(
      find.byType(TextField).at(0), 'sk-test-key');
    await tester.pump();
    await tester.ensureVisible(find.text('下一步'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('下一步'));
    await tester.pumpAndSettle();

    // Step 2: confirm model
    expect(find.text('步骤 2 / 2'), findsOneWidget);
    expect(find.text('确认模型配置'), findsOneWidget);
    await tester.tap(find.text('完成'));
    await tester.pumpAndSettle();

    expect(completedState, isNotNull);
    expect(completedState!.step, WizardStep.complete);
    expect(completedState!.selectedProvider, LlmProvider.deepseek);
    expect(completedState!.apiKey, 'sk-test-key');
    expect(completedState!.modelConfig, 'deepseek-v4-flash');
  });

  testWidgets('shows all 9 provider options in dropdown', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: FirstRunWizard(onComplete: (_) {}),
      ),
    );

    // Open the dropdown
    await tester.tap(find.byType(DropdownButtonFormField<LlmProvider>));
    await tester.pumpAndSettle();

    // All 9 providers should be visible
    expect(find.text('DeepSeek'), findsWidgets);
    expect(find.text('OpenAI'), findsOneWidget);
    expect(find.text('Anthropic'), findsOneWidget);
    expect(find.text('Google Gemini'), findsOneWidget);
    expect(find.text('Groq'), findsOneWidget);
    expect(find.text('xAI (Grok)'), findsOneWidget);
    expect(find.text('Z.AI (GLM)'), findsOneWidget);
    expect(find.text('Qwen (通义千问)'), findsOneWidget);
    expect(find.text('自定义供应商'), findsOneWidget);
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
