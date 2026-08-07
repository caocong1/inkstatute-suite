/**
 * AuthContext — SolidJS context for desktop session management.
 *
 * Provides session_id, tenant_id, user_id signals + login/logout methods.
 * On mount, probes the Gateway for session validity by calling
 * POST /v1/auth/login (dev mode accepts any credentials).
 *
 * Key difference from web: Gateway URL is cross-origin (not same-origin),
 * so we use the full baseUrl from gateway config.
 */
import {
  createContext,
  createSignal,
  onMount,
  useContext,
  type ParentComponent,
} from "solid-js";
import { gateway } from "../config/gateway";

export interface AuthContextValue {
  isAuthenticated: () => boolean;
  sessionId: () => string | null;
  tenantId: () => string | null;
  userId: () => string | null;
  loading: () => boolean;
  login: (credentials: {
    username?: string;
    password?: string;
    token?: string;
    tenant_id?: string;
    user_id?: string;
  }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>();

export const AuthProvider: ParentComponent = (props) => {
  const [sessionId, setSessionId] = createSignal<string | null>(null);
  const [tenantId, setTenantId] = createSignal<string | null>(null);
  const [userId, setUserId] = createSignal<string | null>(null);
  const [loading, setLoading] = createSignal(true);

  const isAuthenticated = () => sessionId() !== null;

  /**
   * Login: POST to Gateway /v1/auth/login with credentials.
   * The Gateway sets the HttpOnly cookie via Set-Cookie header.
   */
  async function login(credentials: {
    username?: string;
    password?: string;
    token?: string;
    tenant_id?: string;
    user_id?: string;
  }): Promise<void> {
    const baseUrl = import.meta.env.VITE_GATEWAY_URL || "http://127.0.0.1:8000";
    const response = await fetch(`${baseUrl}/v1/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      credentials: "include",
      body: JSON.stringify(credentials),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body?.error?.message ?? "登录失败");
    }
    const data = await response.json();
    setSessionId(data.session_id ?? null);
    setTenantId(data.tenant_id ?? null);
    setUserId(credentials.user_id ?? "desktop-user");
  }

  function logout(): void {
    setSessionId(null);
    setTenantId(null);
    setUserId(null);
  }

  /**
   * On mount, probe session validity.
   * In dev mode (rbac_enabled=False), POST /v1/auth/login with empty body
   * creates or refreshes a session.
   */
  onMount(async () => {
    try {
      const baseUrl = import.meta.env.VITE_GATEWAY_URL || "http://127.0.0.1:8000";
      const response = await fetch(`${baseUrl}/v1/auth/login`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        credentials: "include",
        body: JSON.stringify({}),
      });
      if (response.ok) {
        const data = await response.json();
        setSessionId(data.session_id ?? null);
        setTenantId(data.tenant_id ?? null);
        setUserId("desktop-user");
      }
    } catch {
      // Probe failed — not authenticated
    } finally {
      setLoading(false);
    }
  });

  const value: AuthContextValue = {
    isAuthenticated,
    sessionId,
    tenantId,
    userId,
    loading,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{props.children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth() must be used within an AuthProvider");
  }
  return ctx;
}
