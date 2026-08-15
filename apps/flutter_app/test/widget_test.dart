// Widget test — verifies the app shell renders with the startup gate.
//
// The app now starts with StartupGate which shows a loading indicator
// while checking wizard state. These tests verify the initial loading
// state renders correctly.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_app/main.dart';

void main() {
  testWidgets('App displays loading indicator on startup', (WidgetTester tester) async {
    await tester.pumpWidget(const InkStatuteApp());

    // The StartupGate shows a loading indicator initially
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('App displays InkStatute title in MaterialApp', (WidgetTester tester) async {
    await tester.pumpWidget(const InkStatuteApp());

    // The MaterialApp should be present with the correct title
    final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
    expect(materialApp.title, '墨律 InkStatute');
  });
}
