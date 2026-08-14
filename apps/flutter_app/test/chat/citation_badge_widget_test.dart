import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/chat/citation_badge_widget.dart';
import 'package:flutter_app/chat/chat_models.dart';

void main() {
  testWidgets('renders verified citation with green badge', (tester) async {
    final citation = Citation(
      source: '合同法第52条',
      citationType: CitationType.verified,
      text: 'cite',
    );
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: CitationBadgeWidget(citation: citation))),
    );

    expect(find.text('合同法第52条'), findsOneWidget);
    expect(find.byIcon(Icons.check_circle), findsOneWidget);
  });

  testWidgets('renders retrieved citation with blue badge', (tester) async {
    final citation = Citation(
      source: '案例库',
      citationType: CitationType.retrieved,
      text: 'cite',
    );
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: CitationBadgeWidget(citation: citation))),
    );

    expect(find.text('案例库'), findsOneWidget);
    expect(find.byIcon(Icons.search), findsOneWidget);
  });

  testWidgets('renders unverified citation with orange badge', (tester) async {
    final citation = Citation(
      source: '网络来源',
      citationType: CitationType.unverified,
      text: 'cite',
    );
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: CitationBadgeWidget(citation: citation))),
    );

    expect(find.text('网络来源'), findsOneWidget);
    expect(find.byIcon(Icons.warning), findsOneWidget);
  });

  testWidgets('renders human review marker with red badge', (tester) async {
    final marker = HumanReviewMarker(text: '需复核条款风险');
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: CitationBadgeWidget.humanReview(marker: marker)),
      ),
    );

    expect(find.text('需人审'), findsOneWidget);
    expect(find.byIcon(Icons.rate_review), findsOneWidget);
  });

  testWidgets('three citation types are visually distinguishable',
      (tester) async {
    final citations = [
      Citation(source: 'A', citationType: CitationType.verified, text: ''),
      Citation(source: 'B', citationType: CitationType.retrieved, text: ''),
      Citation(source: 'C', citationType: CitationType.unverified, text: ''),
    ];
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Row(
            children: [
              for (final c in citations) CitationBadgeWidget(citation: c),
            ],
          ),
        ),
      ),
    );

    // Three different icons should be present
    expect(find.byIcon(Icons.check_circle), findsOneWidget);
    expect(find.byIcon(Icons.search), findsOneWidget);
    expect(find.byIcon(Icons.warning), findsOneWidget);
  });
}
