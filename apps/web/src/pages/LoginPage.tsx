/**
 * LoginPage — full-screen centered login card per UI-SPEC §Login Page.
 *
 * Form POSTs to Gateway /v1/auth/login via AuthContext.login().
 * On success, redirects to / (home page).
 */
import { createSignal, onMount, Show, type Component } from "solid-js";
import { useNavigate } from "@solidjs/router";
import { useTheme } from "@inkstatute/ui-core";
import { useAuth } from "../contexts/AuthContext";

export const LoginPage: Component = () => {
  const auth = useAuth();
  const navigate = useNavigate();
  const { theme, setTheme } = useTheme();

  const [username, setUsername] = createSignal("");
  const [password, setPassword] = createSignal("");
  const [token, setToken] = createSignal("");
  const [error, setError] = createSignal("");
  const [submitting, setSubmitting] = createSignal(false);

  const isTokenMode = import.meta.env.VITE_LOGIN_MODE === "token";
  const devAutoLogin = import.meta.env.VITE_DEV_AUTO_LOGIN === "true";

  onMount(() => {
    document.title = "登录 · 墨律 InkStatute";
    if (devAutoLogin) {
      setError("开发模式：自动登录中…");
      void doLogin({});
    }
  });

  async function doLogin(credentials: {
    username?: string;
    password?: string;
    token?: string;
  }): Promise<void> {
    setSubmitting(true);
    setError("");
    try {
      await auth.login(credentials);
      navigate("/");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "登录失败";
      if (msg.includes("network") || msg.includes("fetch")) {
        setError("无法连接服务器，请检查网络");
      } else {
        setError("用户名或密码错误");
      }
    } finally {
      setSubmitting(false);
    }
  }

  function handleSubmit(e: Event) {
    e.preventDefault();
    if (isTokenMode) {
      void doLogin({ token: token() });
    } else {
      void doLogin({ username: username(), password: password() });
    }
  }

  return (
    <div class="login-page">
      <div class="login-card">
        <div class="login-brand">
          <div class="seal">墨</div>
          <div class="brand-name">墨律 InkStatute</div>
        </div>
        <div class="login-divider" />
        <form onSubmit={handleSubmit} class="login-form">
          <Show when={!isTokenMode}>
            <label class="login-label">
              用户名
              <input
                type="text"
                name="username"
                class="login-input"
                value={username()}
                onInput={(e) => setUsername(e.currentTarget.value)}
                disabled={submitting()}
                placeholder="请输入用户名"
              />
            </label>
            <label class="login-label">
              密码
              <input
                type="password"
                name="password"
                class="login-input"
                value={password()}
                onInput={(e) => setPassword(e.currentTarget.value)}
                disabled={submitting()}
                placeholder="请输入密码"
              />
            </label>
          </Show>
          <Show when={isTokenMode}>
            <label class="login-label">
              访问令牌
              <input
                type="password"
                class="login-input"
                value={token()}
                onInput={(e) => setToken(e.currentTarget.value)}
                disabled={submitting()}
                placeholder="请输入访问令牌"
              />
            </label>
          </Show>
          <button
            type="submit"
            class="login-btn"
            disabled={submitting()}
          >
            {submitting() ? "登录中…" : "登 录"}
          </button>
        </form>
        <div class="login-theme-switch">
          <button
            class="theme-dot"
            classList={{ active: theme() === "a" }}
            onClick={() => setTheme("a")}
            aria-label="主题 A"
          />
          <button
            class="theme-dot"
            classList={{ active: theme() === "b" }}
            onClick={() => setTheme("b")}
            aria-label="主题 B"
          />
          <button
            class="theme-dot"
            classList={{ active: theme() === "c" }}
            onClick={() => setTheme("c")}
            aria-label="主题 C"
          />
        </div>
        <Show when={error()}>
          <div class="login-error">{error()}</div>
        </Show>
      </div>
    </div>
  );
};
