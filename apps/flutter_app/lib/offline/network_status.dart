/// Network status detector (PKG-04).
library;

/// Network connectivity status.
enum NetworkStatus {
  /// Online — network available.
  online,

  /// Offline — no network.
  offline,
}

/// Detects network connectivity status.
class NetworkStatusDetector {
  /// Creates a network status detector.
  NetworkStatusDetector({NetworkStatus? initialStatus})
      : _status = initialStatus ?? NetworkStatus.online;

  NetworkStatus _status;

  /// Returns the current network status.
  NetworkStatus get status => _status;

  /// Returns true if currently online.
  bool get isOnline => _status == NetworkStatus.online;

  /// Returns true if currently offline.
  bool get isOffline => _status == NetworkStatus.offline;

  /// Sets the network status (for testing or manual override).
  void setStatus(NetworkStatus status) {
    _status = status;
  }

  /// Checks network connectivity.
  ///
  /// In production, this would attempt a network request to verify
  /// connectivity. For now, returns the current status.
  Future<NetworkStatus> check() async {
    return _status;
  }

  /// Returns a human-readable status message.
  static String statusMessage(NetworkStatus status) {
    return switch (status) {
      NetworkStatus.online => '网络正常',
      NetworkStatus.offline => '当前处于离线状态',
    };
  }
}
