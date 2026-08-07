/**
 * ConnectionContext — online/offline detection via Gateway health probe.
 *
 * Provides connectionState() signal: "checking" | "online" | "offline".
 * On mount, probes Gateway /v1/health. Periodic heartbeat: 30s when online,
 * 10s when offline (faster reconnection detection).
 *
 * On transition offline → online: emits "connection-restored" window event.
 * On transition online → offline: emits "connection-lost" window event.
 *
 * Offline mode is read-only — no data is written locally that would conflict
 * with the Gateway on reconnection.
 */
import {
  createContext,
  createSignal,
  onMount,
  onCleanup,
  useContext,
  type ParentComponent,
} from "solid-js";

export type ConnectionState = "online" | "offline" | "checking";

export interface ConnectionContextValue {
  connectionState: () => ConnectionState;
  isOnline: () => boolean;
  isOffline: () => boolean;
}

const ConnectionContext = createContext<ConnectionContextValue>();

export const ConnectionProvider: ParentComponent = (props) => {
  const [connectionState, setConnectionState] = createSignal<ConnectionState>("checking");
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null;

  const baseUrl = import.meta.env.VITE_GATEWAY_URL || "http://127.0.0.1:8000";

  async function probeGateway(): Promise<boolean> {
    try {
      const response = await fetch(`${baseUrl}/v1/health`, {
        method: "GET",
        signal: AbortSignal.timeout(5000),
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  function startHeartbeat(): void {
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    const interval = connectionState() === "offline" ? 10_000 : 30_000;
    heartbeatTimer = setInterval(async () => {
      const reachable = await probeGateway();
      const prev = connectionState();
      if (reachable && prev === "offline") {
        setConnectionState("online");
        window.dispatchEvent(new CustomEvent("connection-restored"));
        startHeartbeat(); // restart with online interval
      } else if (!reachable && prev === "online") {
        setConnectionState("offline");
        window.dispatchEvent(new CustomEvent("connection-lost"));
        startHeartbeat(); // restart with offline interval
      }
    }, interval);
  }

  onMount(async () => {
    const reachable = await probeGateway();
    setConnectionState(reachable ? "online" : "offline");
    if (reachable) {
      window.dispatchEvent(new CustomEvent("connection-restored"));
    }
    startHeartbeat();
  });

  onCleanup(() => {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer);
      heartbeatTimer = null;
    }
  });

  const value: ConnectionContextValue = {
    connectionState,
    isOnline: () => connectionState() === "online",
    isOffline: () => connectionState() === "offline",
  };

  return (
    <ConnectionContext.Provider value={value}>
      {props.children}
    </ConnectionContext.Provider>
  );
};

export function useConnection(): ConnectionContextValue {
  const ctx = useContext(ConnectionContext);
  if (!ctx) {
    throw new Error("useConnection() must be used within a ConnectionProvider");
  }
  return ctx;
}
