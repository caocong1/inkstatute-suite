import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/legacy/freeze_annotation.dart';

void main() {
  group('FreezeAnnotation', () {
    test('frozenComponents has 9 components', () {
      expect(FreezeAnnotation.frozenComponents.length, 9);
    });

    test('all components are frozen (not retired)', () {
      for (final component in FreezeAnnotation.frozenComponents) {
        expect(component.status, FreezeStatus.frozen);
      }
    });

    test('frozenPaths returns all paths', () {
      final paths = FreezeAnnotation.frozenPaths;
      expect(paths.length, 9);
      expect(paths, contains('services/gateway'));
      expect(paths, contains('packages/agent-core'));
      expect(paths, contains('apps/desktop'));
    });

    test('isFrozen returns true for frozen paths', () {
      expect(FreezeAnnotation.isFrozen('services/gateway'), isTrue);
      expect(FreezeAnnotation.isFrozen('packages/agent-core'), isTrue);
    });

    test('isFrozen returns false for non-frozen paths', () {
      expect(FreezeAnnotation.isFrozen('apps/flutter_app'), isFalse);
      expect(FreezeAnnotation.isFrozen('nonexistent'), isFalse);
    });

    test('frozenCount returns correct count', () {
      expect(FreezeAnnotation.frozenCount, 9);
    });

    test('all components have non-empty names and descriptions', () {
      for (final component in FreezeAnnotation.frozenComponents) {
        expect(component.name, isNotEmpty);
        expect(component.description, isNotEmpty);
        expect(component.path, isNotEmpty);
      }
    });
  });
}
