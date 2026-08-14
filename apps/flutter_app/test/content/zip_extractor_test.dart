import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/content/zip_extractor.dart';
import 'package:flutter_app/content/update_exception.dart';
import 'package:archive/archive_io.dart';
import 'dart:io';

void main() {
  late Directory tempDir;

  setUp(() {
    tempDir = Directory.systemTemp.createTempSync('zip_extractor_test');
  });

  tearDown(() {
    if (tempDir.existsSync()) tempDir.deleteSync(recursive: true);
  });

  test('extracts normal zip with nested directories', () async {
    // Create a zip with nested structure
    final archive = Archive();
    archive.addFile(ArchiveFile('legal-commercial/contract-review/SKILL.md',
        20, '---\nname: test\n---\n'));
    archive.addFile(ArchiveFile(
        'legal-commercial/contract-review-risk-identification/SKILL.md',
        20,
        '---\nname: risk\n---\n'));

    final zipPath = '${tempDir.path}/test.zip';
    final outputStream = OutputFileStream(zipPath);
    ZipEncoder().encode(archive, output: outputStream);
    await outputStream.close();

    final outputDir = '${tempDir.path}/output';
    await ZipExtractor.extract(zipPath, outputDir);

    expect(
        File('$outputDir/legal-commercial/contract-review/SKILL.md')
            .existsSync(),
        isTrue);
    expect(
        File(
                '$outputDir/legal-commercial/contract-review-risk-identification/SKILL.md')
            .existsSync(),
        isTrue);
  });

  test('creates output directory if it does not exist', () async {
    final archive = Archive();
    archive.addFile(ArchiveFile('test.txt', 5, 'hello'));

    final zipPath = '${tempDir.path}/test.zip';
    final outputStream = OutputFileStream(zipPath);
    ZipEncoder().encode(archive, output: outputStream);
    await outputStream.close();

    final outputDir = '${tempDir.path}/nonexistent/deep/output';
    await ZipExtractor.extract(zipPath, outputDir);

    expect(File('$outputDir/test.txt').existsSync(), isTrue);
  });

  test('rejects path traversal with .. in entry name', () async {
    final archive = Archive();
    archive.addFile(ArchiveFile('../escape.txt', 5, 'evil'));

    final zipPath = '${tempDir.path}/traversal.zip';
    final outputStream = OutputFileStream(zipPath);
    ZipEncoder().encode(archive, output: outputStream);
    await outputStream.close();

    final outputDir = '${tempDir.path}/output';
    await expectLater(
      ZipExtractor.extract(zipPath, outputDir),
      throwsA(isA<UpdateException>()
          .having((e) => e.kind, 'kind', UpdateExceptionKind.pathTraversal)),
    );
  });

  test('extracts empty zip without error', () async {
    final archive = Archive();
    final zipPath = '${tempDir.path}/empty.zip';
    final outputStream = OutputFileStream(zipPath);
    ZipEncoder().encode(archive, output: outputStream);
    await outputStream.close();

    final outputDir = '${tempDir.path}/output';
    await ZipExtractor.extract(zipPath, outputDir);

    expect(Directory(outputDir).existsSync(), isTrue);
  });

  test('extracts zip with directory entries', () async {
    final archive = Archive();
    archive.addFile(
        ArchiveFile('legal-commercial/contract-review/SKILL.md', 5, 'test'));

    final zipPath = '${tempDir.path}/dirs.zip';
    final outputStream = OutputFileStream(zipPath);
    ZipEncoder().encode(archive, output: outputStream);
    await outputStream.close();

    final outputDir = '${tempDir.path}/output';
    await ZipExtractor.extract(zipPath, outputDir);

    expect(
        File('$outputDir/legal-commercial/contract-review/SKILL.md')
            .existsSync(),
        isTrue);
  });
}
