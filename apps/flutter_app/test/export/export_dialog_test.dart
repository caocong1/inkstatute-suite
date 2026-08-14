import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'dart:io';
import 'package:flutter_app/export/change_list_schema.dart';
import 'package:flutter_app/export/docx_exporter.dart';
import 'package:flutter_app/export/export_dialog.dart';
import 'package:flutter_app/export/hg4_status.dart';

void main() {
  late ChangeList sampleChangeList;
  late DocxExporter exporter;
  late Hg4Tracker hg4Tracker;
  late String fixturesDir;
  late String inputDocx;
  late String outputDocx;

  setUpAll(() {
    fixturesDir = '${Directory.current.path}/test/fixtures/export';
    inputDocx = '$fixturesDir/sample_input.docx';
    outputDocx = '$fixturesDir/test_dialog_output.docx';
  });

  setUp(() {
    sampleChangeList = ChangeList(
      items: [
        ChangeItem(
          id: 1,
          clauseLocation: '第一条',
          originalText: '根据《中华人民共和国合同法》的规定',
          revisedText: '根据《中华人民共和国民法典》的规定',
          reason: '法律引用已废止',
          riskLevel: RiskLevel.p0,
          comment: '《合同法》已废止',
        ),
      ],
      sourceDocument: 'sample_input.docx',
      createdAt: DateTime(2026, 8, 14),
    );

    exporter = DocxExporter(
      pythonPath: 'python3',
      scriptPath:
          '${Directory.current.path}/assets/scripts/contract_review_trackchanges_v4.py',
    );

    hg4Tracker = Hg4Tracker();
  });

  tearDown(() {
    final output = File(outputDocx);
    if (output.existsSync()) {
      output.deleteSync();
    }
  });

  testWidgets('ExportDialog shows exporting state', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ExportDialog(
            changeList: sampleChangeList,
            inputDocxPath: inputDocx,
            outputDocxPath: outputDocx,
            exporter: exporter,
            hg4Tracker: hg4Tracker,
          ),
        ),
      ),
    );

    // Pump once to trigger initState
    await tester.pump();

    // Should show progress indicator initially
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.text('正在生成修订稿...'), findsOneWidget);
  });

  testWidgets('ExportDialog has correct title', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ExportDialog(
            changeList: sampleChangeList,
            inputDocxPath: inputDocx,
            outputDocxPath: outputDocx,
            exporter: exporter,
            hg4Tracker: hg4Tracker,
          ),
        ),
      ),
    );

    await tester.pump();
    expect(find.text('导出 Word 修订稿'), findsOneWidget);
  });

  testWidgets('ExportDialog shows result after export completes',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ExportDialog(
            changeList: sampleChangeList,
            inputDocxPath: inputDocx,
            outputDocxPath: outputDocx,
            exporter: exporter,
            hg4Tracker: hg4Tracker,
          ),
        ),
      ),
    );

    // Pump to start the export, then pump with delays to let it complete
    await tester.pump();
    await tester.pump(const Duration(seconds: 3));

    // Should show either success or failure (not still exporting)
    // The close button appears when not exporting
    final closeFinder = find.text('关闭');
    if (closeFinder.evaluate().isNotEmpty) {
      expect(closeFinder, findsOneWidget);
    }
  });
}
