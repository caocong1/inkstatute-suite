// Widget test — verifies the app shell renders with the chat UI.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_app/main.dart';

void main() {
  testWidgets('App displays InkStatute title', (WidgetTester tester) async {
    await tester.pumpWidget(const InkStatuteApp());

    expect(find.text('墨律 InkStatute'), findsWidgets);
  });

  testWidgets('Chat view is present in home screen', (WidgetTester tester) async {
    await tester.pumpWidget(const InkStatuteApp());
    await tester.pumpAndSettle();

    // The home screen should contain a status bar and input field
    expect(find.text('商事法'), findsOneWidget);
    expect(find.byType(TextField), findsOneWidget);
  });
}
