import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/offline/offline_prompt.dart';

void main() {
  testWidgets('OfflinePrompt shows offline message', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: OfflinePrompt(
            onViewHistory: () {},
            onRetry: () {},
          ),
        ),
      ),
    );

    expect(find.text('离线提示'), findsOneWidget);
    expect(find.text('当前处于离线状态'), findsOneWidget);
    expect(find.byIcon(Icons.wifi_off), findsOneWidget);
  });

  testWidgets('OfflinePrompt has view history and retry buttons',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: OfflinePrompt(
            onViewHistory: () {},
            onRetry: () {},
          ),
        ),
      ),
    );

    expect(find.text('查看历史'), findsOneWidget);
    expect(find.text('重试'), findsOneWidget);
  });

  testWidgets('OfflinePrompt retry button calls onRetry', (WidgetTester tester) async {
    bool retryCalled = false;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: OfflinePrompt(
            onViewHistory: () {},
            onRetry: () {
              retryCalled = true;
            },
          ),
        ),
      ),
    );

    await tester.tap(find.text('重试'));
    await tester.pump();
    expect(retryCalled, isTrue);
  });

  testWidgets('OfflinePrompt view history button calls onViewHistory',
      (WidgetTester tester) async {
    bool viewHistoryCalled = false;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: OfflinePrompt(
            onViewHistory: () {
              viewHistoryCalled = true;
            },
            onRetry: () {},
          ),
        ),
      ),
    );

    await tester.tap(find.text('查看历史'));
    await tester.pump();
    expect(viewHistoryCalled, isTrue);
  });

  test('OfflinePrompt.message returns correct text', () {
    expect(OfflinePrompt.message, contains('离线'));
    expect(OfflinePrompt.message, contains('联网'));
    expect(OfflinePrompt.message, contains('历史'));
  });
}
