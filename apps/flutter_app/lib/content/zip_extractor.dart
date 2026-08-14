import 'dart:io';

import 'package:archive/archive_io.dart';
import 'package:flutter_app/content/update_exception.dart';
import 'package:path/path.dart' as p;

/// Zip archive extractor with path traversal protection.
///
/// Extracts zip files to a target directory. Validates that no zip
/// entry escapes the target directory via path traversal (e.g.,
/// `../escape.txt`).
class ZipExtractor {
  const ZipExtractor._();

  /// Extracts [zipPath] to [outputDir].
  ///
  /// Creates [outputDir] if it does not exist. Each zip entry is
  /// validated for path traversal before extraction.
  ///
  /// Throws [UpdateException] with kind [UpdateExceptionKind.pathTraversal]
  /// if any entry attempts to escape [outputDir].
  /// Throws [UpdateException] with kind [UpdateExceptionKind.extractionFailed]
  /// on I/O or archive format errors.
  static Future<void> extract(String zipPath, String outputDir) async {
    final outputPath = p.normalize(p.absolute(outputDir));
    await Directory(outputPath).create(recursive: true);

    try {
      final bytes = File(zipPath).readAsBytesSync();
      final archive = ZipDecoder().decodeBytes(bytes);

      for (final file in archive) {
        final name = file.name;
        final targetPath = p.normalize(p.join(outputPath, name));

        // Path traversal protection: ensure target is within outputDir.
        if (!targetPath.startsWith(outputPath)) {
          throw UpdateException(
            UpdateExceptionKind.pathTraversal,
            'Zip entry "$name" resolves outside target directory',
          );
        }

        // Also reject explicit `..` in the entry name.
        if (name.contains('..')) {
          throw UpdateException(
            UpdateExceptionKind.pathTraversal,
            'Zip entry "$name" contains path traversal pattern',
          );
        }

        if (file.isFile) {
          final outFile = File(targetPath);
          await outFile.parent.create(recursive: true);
          final content = file.content as List<int>;
          await outFile.writeAsBytes(content);
        } else {
          await Directory(targetPath).create(recursive: true);
        }
      }
    } catch (e) {
      if (e is UpdateException) rethrow;
      throw UpdateException(
        UpdateExceptionKind.extractionFailed,
        'Zip extraction failed: $e',
      );
    }
  }
}
