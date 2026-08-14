import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/security/owner_mode.dart';

void main() {
  group('OwnerMode', () {
    test('initial state is inactive by default', () {
      final mode = OwnerMode();
      expect(mode.isActive, isFalse);
    });

    test('initial state can be set to active', () {
      final mode = OwnerMode(initiallyActive: true);
      expect(mode.isActive, isTrue);
    });

    test('activate sets isActive to true', () {
      final mode = OwnerMode();
      mode.activate();
      expect(mode.isActive, isTrue);
    });

    test('deactivate sets isActive to false', () {
      final mode = OwnerMode(initiallyActive: true);
      mode.deactivate();
      expect(mode.isActive, isFalse);
    });

    test('toggle switches state', () {
      final mode = OwnerMode();
      expect(mode.isActive, isFalse);
      mode.toggle();
      expect(mode.isActive, isTrue);
      mode.toggle();
      expect(mode.isActive, isFalse);
    });

    test('activation shortcut is Ctrl+Shift+D', () {
      expect(OwnerMode.activationShortcut, contains('ControlLeft'));
      expect(OwnerMode.activationShortcut, contains('ShiftLeft'));
      expect(OwnerMode.activationShortcut, contains('KeyD'));
      expect(OwnerMode.activationShortcut.length, 3);
    });
  });
}
