/// v3.x freeze annotation — marks frozen platform components (LEG-01).
///
/// All v3.x platform components are frozen: no new work, no V4 deliverables,
/// no V4 gate coverage. Retirement only after lawyer trial acceptance (LEG-02).
library;

/// Freeze status of a v3.x component.
enum FreezeStatus {
  /// Component is frozen — no new work, no V4 deliverables.
  frozen,

  /// Component is retired — removed from the repository.
  retired,
}

/// A frozen v3.x platform component.
class FrozenComponent {
  /// Creates a frozen component record.
  const FrozenComponent({
    required this.path,
    required this.name,
    required this.description,
    this.status = FreezeStatus.frozen,
  });

  /// Repository path.
  final String path;

  /// Component name.
  final String name;

  /// Description of the component.
  final String description;

  /// Current freeze status.
  final FreezeStatus status;
}

/// Registry of all frozen v3.x platform components (LEG-01).
class FreezeAnnotation {
  const FreezeAnnotation._();

  /// All frozen v3.x components.
  static const List<FrozenComponent> frozenComponents = [
    FrozenComponent(
      path: 'services/gateway',
      name: 'Gateway',
      description: 'V3 API gateway service — frozen, not in V4 deliverables',
    ),
    FrozenComponent(
      path: 'services/wecom-service',
      name: 'WeCom Service',
      description: 'V3 WeCom integration — frozen, not in V4 deliverables',
    ),
    FrozenComponent(
      path: 'services/qqbot-service',
      name: 'QQ Bot Service',
      description: 'V3 QQ bot integration — frozen, not in V4 deliverables',
    ),
    FrozenComponent(
      path: 'services/arena-service',
      name: 'Arena Service',
      description: 'V3 arena service — frozen, not in V4 deliverables',
    ),
    FrozenComponent(
      path: 'packages/agent-core',
      name: 'Agent Core',
      description: 'V3 self-built agent core — frozen, replaced by DSH',
    ),
    FrozenComponent(
      path: 'packages/acp-client',
      name: 'ACP Client (TS)',
      description: 'V3 TypeScript ACP client — frozen, replaced by Dart ACP client',
    ),
    FrozenComponent(
      path: 'packages/ui-core',
      name: 'UI Core (SolidJS)',
      description: 'V3 SolidJS UI core — frozen, replaced by Flutter UI',
    ),
    FrozenComponent(
      path: 'apps/web',
      name: 'Web App',
      description: 'V3 web application — frozen, not in V4 deliverables',
    ),
    FrozenComponent(
      path: 'apps/desktop',
      name: 'Desktop App (Tauri)',
      description: 'V3 Tauri desktop app — frozen, replaced by Flutter app',
    ),
  ];

  /// Returns the list of component paths that are frozen.
  static List<String> get frozenPaths =>
      frozenComponents.map((c) => c.path).toList();

  /// Returns true if a path is a frozen component.
  static bool isFrozen(String path) {
    return frozenComponents.any((c) => c.path == path);
  }

  /// Returns the number of frozen components.
  static int get frozenCount => frozenComponents.length;
}
