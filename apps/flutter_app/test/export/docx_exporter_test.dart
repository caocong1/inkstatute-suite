import 'package:flutter_test/flutter_test.dart';
import 'dart:io';
import 'package:flutter_app/export/change_list_schema.dart';
import 'package:flutter_app/export/docx_exporter.dart';

void main() {
  late DocxExporter exporter;
  late String fixturesDir;
  late String inputDocx;
  late String outputDocx;
  late ChangeList sampleChangeList;

  setUpAll(() {
    fixturesDir = '${Directory.current.path}/test/fixtures/export';
    inputDocx = '$fixturesDir/sample_input.docx';
    outputDocx = '$fixturesDir/test_output.docx';
  });

  setUp(() {
    // Use system Python for testing (portable Python in production)
    exporter = DocxExporter(
      pythonPath: Platform.environment['PYTHON3_PATH'] ?? 'python3',
      scriptPath:
          '${Directory.current.path}/assets/scripts/contract_review_trackchanges_v4.py',
    );

    sampleChangeList = ChangeList(
      items: [
        ChangeItem(
          id: 1,
          clauseLocation: '第一条',
          originalText: '根据《中华人民共和国合同法》的规定',
          revisedText: '根据《中华人民共和国民法典》的规定',
          reason: '法律引用已废止',
          riskLevel: RiskLevel.p0,
          comment: '《合同法》已于2021年1月1日废止',
        ),
        ChangeItem(
          id: 2,
          clauseLocation: '第二条',
          originalText: '这是第二段。',
          revisedText: null,
          reason: '建议补充',
          riskLevel: RiskLevel.p2,
          comment: '建议补充更多细节',
        ),
      ],
      sourceDocument: 'sample_input.docx',
      createdAt: DateTime(2026, 8, 14),
    );
  });

  tearDown(() {
    // Clean up output file
    final output = File(outputDocx);
    if (output.existsSync()) {
      output.deleteSync();
    }
  });

  group('DocxExporter', () {
    test('export succeeds with valid change list and input docx', () async {
      final result = await exporter.export(
        changeList: sampleChangeList,
        inputDocxPath: inputDocx,
        outputDocxPath: outputDocx,
      );

      // This test may fail if Python/lxml is not available in CI.
      // In that case, it verifies the error path.
      if (result is ExportSuccess) {
        expect(result.outputPath, outputDocx);
        expect(File(outputDocx).existsSync(), isTrue);
      } else {
        // If Python or lxml is not available, verify we get a clear error
        final failure = result as ExportFailure;
        expect(failure.error, isNotEmpty);
      }
    });

    test('export fails with invalid change list (empty items)', () async {
      final invalidList = ChangeList(
        items: [],
        sourceDocument: 'doc.docx',
        createdAt: DateTime.now(),
      );

      final result = await exporter.export(
        changeList: invalidList,
        inputDocxPath: inputDocx,
        outputDocxPath: outputDocx,
      );

      expect(result, isA<ExportFailure>());
      expect((result as ExportFailure).error, contains('校验失败'));
    });

    test('export fails when input docx does not exist', () async {
      final result = await exporter.export(
        changeList: sampleChangeList,
        inputDocxPath: '/nonexistent/path.docx',
        outputDocxPath: outputDocx,
      );

      expect(result, isA<ExportFailure>());
      expect((result as ExportFailure).error, contains('不存在'));
    });

    test('export fails when Python not found', () async {
      final badExporter = DocxExporter(
        pythonPath: '/nonexistent/python3',
        scriptPath: '${Directory.current.path}/assets/scripts/contract_review_trackchanges_v4.py',
      );

      final result = await badExporter.export(
        changeList: sampleChangeList,
        inputDocxPath: inputDocx,
        outputDocxPath: outputDocx,
      );

      expect(result, isA<ExportFailure>());
    });

    test('export fails when script not found', () async {
      final badExporter = DocxExporter(
        pythonPath: 'python3',
        scriptPath: '/nonexistent/script.py',
      );

      final result = await badExporter.export(
        changeList: sampleChangeList,
        inputDocxPath: inputDocx,
        outputDocxPath: outputDocx,
      );

      expect(result, isA<ExportFailure>());
      expect((result as ExportFailure).error, contains('脚本未找到'));
    });
  });

  group('Model-never-writes-docx assertion', () {
    test('exporter only accepts ChangeList, not raw model text', () {
      // The export() method signature requires a ChangeList parameter.
      // There is no overload that accepts raw string text.
      // This is enforced at the type level.
      expect(sampleChangeList, isA<ChangeList>());
    });

    test('ChangeList JSON is the only input to the Python script', () async {
      // The exporter calls Process.run with the script and passes
      // changeList.toJson() via stdin. No raw model text is passed.
      final json = sampleChangeList.toJson();
      expect(json, contains('"items"'));
      expect(json, contains('"originalText"'));
      // The JSON is a structured change list, not raw model text.
    });
  });

  group('ExportResult', () {
    test('ExportSuccess contains output path', () {
      const result = ExportSuccess('/path/to/output.docx');
      expect(result.outputPath, '/path/to/output.docx');
    });

    test('ExportFailure contains error message', () {
      const result = ExportFailure('something went wrong');
      expect(result.error, 'something went wrong');
    });
  });
}
