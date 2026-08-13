// Tracer widget test — verifies the V4 banner renders.
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_app/main.dart';

void main() {
  testWidgets('App displays InkStatute V4 banner', (WidgetTester tester) async {
    await tester.pumpWidget(const InkStatuteApp());

    expect(find.text('InkStatute V4'), findsWidgets);
  });
}
