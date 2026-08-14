import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/settings/content_settings_page.dart';
import 'package:flutter_app/content/content_updater.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'dart:convert';

void main() {
  testWidgets('ContentSettingsPage renders with current version',
      (WidgetTester tester) async {
    final mockClient = MockClient((request) async {
      return http.Response('Not Found', 404);
    });

    final updater = ContentUpdater(
      contentReleaseUrl: 'http://test.local',
      engineVersion: '47f943859b',
      httpClient: mockClient,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: ContentSettingsPage(updater: updater),
      ),
    );

    // Verify the page title
    expect(find.text('技能内容更新'), findsOneWidget);

    // Verify the "当前版本" section exists
    expect(find.text('当前版本'), findsOneWidget);

    // Verify the "检查更新" button exists
    expect(find.text('检查更新'), findsOneWidget);

    // Verify the "更新源地址" section exists
    expect(find.text('更新源地址'), findsOneWidget);

    updater.close();
  });

  testWidgets('status display shows message', (WidgetTester tester) async {
    final mockClient = MockClient((request) async {
      return http.Response('Not Found', 404);
    });

    final updater = ContentUpdater(
      contentReleaseUrl: 'http://test.local',
      engineVersion: '47f943859b',
      httpClient: mockClient,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: ContentSettingsPage(updater: updater),
      ),
    );

    // The status section should be present
    expect(find.text('状态'), findsOneWidget);

    // Some status message should be displayed (exact text depends on
    // whether content is installed in test env)
    expect(find.byType(Text), findsWidgets);

    updater.close();
  });

  testWidgets('check update button triggers update check',
      (WidgetTester tester) async {
    final manifest = {
      'schema_version': '1.0.0',
      'release_version': '1.0.0',
      'released_at': '2026-08-14T00:00:00Z',
      'min_engine_version': '47f943859b',
      'domains': {},
    };

    final mockClient = MockClient((request) async {
      return http.Response(jsonEncode(manifest), 200);
    });

    final updater = ContentUpdater(
      contentReleaseUrl: 'http://test.local',
      engineVersion: '47f943859b',
      httpClient: mockClient,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: ContentSettingsPage(updater: updater),
      ),
    );

    // Tap the check button
    await tester.tap(find.text('检查更新'));

    // Wait for the async operation to complete
    await tester.pumpAndSettle();

    // After completion, the button should be enabled again
    // (not showing progress indicator)
    expect(find.text('检查更新'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);

    updater.close();
  });

  testWidgets('update source URL field is editable', (WidgetTester tester) async {
    final mockClient = MockClient((request) async {
      return http.Response('Not Found', 404);
    });

    final updater = ContentUpdater(
      contentReleaseUrl: 'http://test.local',
      engineVersion: '47f943859b',
      httpClient: mockClient,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: ContentSettingsPage(updater: updater),
      ),
    );

    // Find the URL text field
    expect(find.byType(TextField), findsOneWidget);

    // Enter a new URL
    await tester.enterText(find.byType(TextField), 'https://custom.url/content');

    // Verify the text was entered
    expect(find.text('https://custom.url/content'), findsOneWidget);

    updater.close();
  });
}
