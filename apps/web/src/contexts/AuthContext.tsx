/**
 * AuthContext — SolidJS context for web session management.
 *
 * Provides session_id, tenant_id, user_id signals + login/logout methods.
 * On mount, probes the Gateway for session validity by calling
 * POST /v1/auth/login (dev mode accepts any credentials, creating or
 * refreshing a session). The HttpOnly cookie is the sole credential —
 * no localStorage token storage.
 */
import {
  createContext,
  createSignal,
  onMount,
  useContext,
  type ParentComponent,
} from "solid-js";

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
   * Login: POST to /v1/auth/login. The Gateway sets the HttpOnly cookie
   * via Set-Cookie header — the browser stores it automatically.
   * We store session_id and tenant_id in signals for UI state.
   */
  async function login(credentials: {
    username?: string;
    password?: string;
    token?: string;
    tenant_id?: string;
    user_id?: string;
  }): Promise<void> {
    const response = await fetch("/v1/auth/login", {
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
    setUserId(credentials.user_id ?? "web-user");
  }

  function logout(): void {
    setSessionId(null);
    setTenantId(null);
    setUserId(null);
  }

  /**
   * On mount, probe session validity.
   *
   * Tracer simplification: In dev mode (rbac_enabled=False), calling
   * POST /v1/auth/login with empty body creates or refreshes a session.
   * If the call succeeds, we're authenticated. For RBAC mode, the probe
   * would need a different approach (e.g., GET /v1/auth/me) — deferred
   * to Plan 93-03.
   */
  onMount(async () => {
    try {
      const response = await fetch("/v1/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        credentials: "include",
        body: JSON.stringify({}),
      });
      if (response.ok) {
        const data = await response.json();
        setSessionId(data.session_id ?? null);
        setTenantId(data.tenant_id ?? null);
        setUserId("web-user");
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
