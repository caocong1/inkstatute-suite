"""Integration tests for login/logout session auth in the admin web UI (Phase 85)."""

from __future__ import annotations

import unittest
from typing import Any

from admin_console_api.api import handle_admin_get
from admin_web_ui.csrf import issue_csrf_token
from admin_web_ui.server import handle_admin_web_ui_request
from conversation_read_view.read_model import build_read_model
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac import InMemorySessionStore, Role, issue_token
from rbac.session import SESSION_COOKIE_NAME


def _env_with_credentials(**overrides: str) -> dict[str, str]:
    env = {
        "ADMIN_WEB_UI_ENABLED": "true",
        "RBAC_ENABLED": "true",
        "RBAC_TOKEN_SECRET": "test-secret",
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "s3cret",
    }
    env.update(overrides)
    return env


def _extract_cookie_value(set_cookie: str) -> str:
    """Extract the cookie value (after ``name=`` and before ``;``)."""
    prefix = f"{SESSION_COOKIE_NAME}="
    start = set_cookie.index(prefix) + len(prefix)
    rest = set_cookie[start:]
    end = rest.index(";") if ";" in rest else len(rest)
    return rest[:end]


class AuthSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.feature_flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
            rbac_enabled=True,
        )
        self.session_store = InMemorySessionStore()
        self.read_model = build_read_model([])

    def _request(
        self,
        path: str = "/login",
        *,
        headers: dict[str, str] | None = None,
        env: dict[str, str] | None = None,
        method: str = "GET",
        body: bytes | str | None = None,
    ) -> tuple[int, str, dict[str, str]]:
        return handle_admin_web_ui_request(
            path,
            headers,
            feature_flags=self.feature_flags,
            handle_admin_get=handle_admin_get,
            read_model=self.read_model,
            feedback_queue=[],
            env=env or _env_with_credentials(),
            rbac_secret=None,
            method=method,
            body=body,
            session_store=self.session_store,
        )

    def _get_login_csrf(self, env: dict[str, str] | None = None) -> str:
        """GET /login and extract the csrf_token from the form."""
        status, body, _ = self._request("/login", env=env)
        self.assertEqual(status, 200)
        # Extract csrf_token value from the hidden input.
        marker = 'name="csrf_token" value="'
        idx = body.index(marker) + len(marker)
        end = body.index('"', idx)
        return body[idx:end]

    def _login(
        self, *, username: str = "admin", password: str = "s3cret", csrf_token: str | None = None, env: dict[str, str] | None = None
    ) -> tuple[int, str, dict[str, str]]:
        if csrf_token is None:
            csrf_token = self._get_login_csrf(env=env)
        body = f"csrf_token={csrf_token}&username={username}&password={password}"
        return self._request("/login", method="POST", body=body, env=env)

    # --- GET /login ---

    def test_get_login_renders_form(self) -> None:
        status, body, _ = self._request("/login")
        self.assertEqual(status, 200)
        self.assertIn("<form", body)
        self.assertIn('name="username"', body)
        self.assertIn('name="password"', body)
        self.assertIn('name="csrf_token"', body)
        self.assertIn("Login", body)

    def test_get_login_has_csrf_token(self) -> None:
        status, body, _ = self._request("/login")
        self.assertEqual(status, 200)
        self.assertIn('name="csrf_token" value="', body)
        # The value should be non-empty.
        marker = 'name="csrf_token" value="'
        idx = body.index(marker) + len(marker)
        end = body.index('"', idx)
        self.assertGreater(end - idx, 0)

    # --- POST /login ---

    def test_post_login_success_sets_cookie_and_redirects(self) -> None:
        status, body, headers = self._login()
        self.assertEqual(status, 302)
        self.assertEqual(headers.get("Location"), "/")
        set_cookie = headers.get("Set-Cookie", "")
        self.assertIn(f"{SESSION_COOKIE_NAME}=", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=Strict", set_cookie)

    def test_post_login_invalid_credentials(self) -> None:
        status, body, headers = self._login(password="wrong")
        self.assertEqual(status, 401)
        self.assertIn("Invalid username or password", body)
        # New csrf_token present.
        self.assertIn('name="csrf_token" value="', body)

    def test_post_login_missing_csrf(self) -> None:
        body = "username=admin&password=s3cret"
        status, body_text, _ = self._request("/login", method="POST", body=body)
        self.assertEqual(status, 403)
        self.assertIn("CSRF", body_text)

    def test_post_login_invalid_csrf(self) -> None:
        body = "csrf_token=tampered.token&username=admin&password=s3cret"
        status, body_text, _ = self._request("/login", method="POST", body=body)
        self.assertEqual(status, 403)

    def test_post_login_missing_username(self) -> None:
        csrf = self._get_login_csrf()
        body = f"csrf_token={csrf}&password=s3cret"
        status, body_text, _ = self._request("/login", method="POST", body=body)
        self.assertEqual(status, 400)

    def test_post_login_password_not_configured(self) -> None:
        env = _env_with_credentials()
        del env["ADMIN_PASSWORD"]
        status, body_text, _ = self._login(env=env)
        self.assertEqual(status, 401)

    # --- Session cookie auth ---

    def test_session_cookie_authenticates_subsequent_request(self) -> None:
        # Login.
        _, _, login_headers = self._login()
        cookie_value = _extract_cookie_value(login_headers["Set-Cookie"])
        # Use the cookie to access / (no Bearer header).
        status, body, _ = self._request(
            "/",
            headers={"Cookie": f"{SESSION_COOKIE_NAME}={cookie_value}"},
        )
        self.assertEqual(status, 200)

    def test_bearer_takes_priority_over_cookie(self) -> None:
        # Login to get a session cookie (ADMIN, tenant=default).
        _, _, login_headers = self._login()
        cookie_value = _extract_cookie_value(login_headers["Set-Cookie"])
        # Create a Bearer token with a different role/tenant.
        token = issue_token("test-secret", role=Role.LAWYER, tenant_id="bearer-tenant")
        status, body, _ = self._request(
            "/",
            headers={
                "Authorization": f"Bearer {token}",
                "Cookie": f"{SESSION_COOKIE_NAME}={cookie_value}",
            },
        )
        self.assertEqual(status, 200)
        # The identity should reflect the Bearer token (LAWYER), not the cookie (ADMIN).
        self.assertIn("lawyer", body)

    def test_session_cookie_invalid_returns_401(self) -> None:
        status, body, _ = self._request(
            "/",
            headers={"Cookie": f"{SESSION_COOKIE_NAME}=tampered.bad"},
        )
        self.assertEqual(status, 401)

    # --- POST /logout ---

    def test_post_logout_invalidates_session(self) -> None:
        # Login.
        _, _, login_headers = self._login()
        cookie_value = _extract_cookie_value(login_headers["Set-Cookie"])
        cookie_header = f"{SESSION_COOKIE_NAME}={cookie_value}"

        # GET / to get a csrf token for logout (authenticated).
        # Actually, logout csrf is bound to the authenticated identity + /logout route.
        # We need to issue a csrf token for the authenticated identity.
        # The logout page is not rendered via GET (405), so we issue the token directly.
        from admin_web_ui.auth import LOGOUT_PATH
        from rbac import Identity

        # Resolve identity via cookie to get the authenticated identity.
        from rbac import resolve_identity

        identity = resolve_identity(
            None,
            rbac_secret="test-secret",
            rbac_enabled=True,
            session_cookie=cookie_value,
            session_store=self.session_store,
        )
        assert identity is not None
        logout_csrf = issue_csrf_token(identity, LOGOUT_PATH, signing_key="test-secret")

        # POST /logout.
        logout_body = f"csrf_token={logout_csrf}"
        status, body, headers = self._request(
            "/logout",
            headers={"Cookie": cookie_header},
            method="POST",
            body=logout_body,
        )
        self.assertEqual(status, 302)
        self.assertEqual(headers.get("Location"), "/login")
        self.assertIn("Max-Age=0", headers.get("Set-Cookie", ""))

        # Old cookie should now be rejected.
        status2, _, _ = self._request(
            "/",
            headers={"Cookie": cookie_header},
        )
        self.assertEqual(status2, 401)

    def test_get_logout_returns_405(self) -> None:
        status, _, _ = self._request("/logout", method="GET")
        self.assertEqual(status, 405)

    def test_post_logout_requires_auth(self) -> None:
        status, body, _ = self._request("/logout", method="POST", body="csrf_token=x.y")
        self.assertEqual(status, 401)

    def test_post_logout_invalid_csrf(self) -> None:
        # Login.
        _, _, login_headers = self._login()
        cookie_value = _extract_cookie_value(login_headers["Set-Cookie"])
        cookie_header = f"{SESSION_COOKIE_NAME}={cookie_value}"
        # POST /logout with tampered csrf.
        status, body, _ = self._request(
            "/logout",
            headers={"Cookie": cookie_header},
            method="POST",
            body="csrf_token=tampered.token",
        )
        self.assertEqual(status, 403)

    # --- Session fixation prevention ---

    def test_session_fixation_prevention(self) -> None:
        _, _, headers1 = self._login()
        _, _, headers2 = self._login()
        cookie1 = _extract_cookie_value(headers1["Set-Cookie"])
        cookie2 = _extract_cookie_value(headers2["Set-Cookie"])
        self.assertNotEqual(cookie1, cookie2)

    # --- Cookie attributes ---

    def test_cookie_attributes_httponly_samesite(self) -> None:
        _, _, headers = self._login()
        set_cookie = headers["Set-Cookie"]
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=Strict", set_cookie)

    def test_cookie_attributes_secure_when_flag_set(self) -> None:
        env = _env_with_credentials(ADMIN_WEB_UI_SECURE_COOKIE="true")
        _, _, headers = self._login(env=env)
        set_cookie = headers["Set-Cookie"]
        self.assertIn("Secure", set_cookie)

    def test_cookie_attributes_no_secure_by_default(self) -> None:
        _, _, headers = self._login()
        set_cookie = headers["Set-Cookie"]
        self.assertNotIn("Secure", set_cookie)

    # --- HTML escaping ---

    def test_login_page_html_escaped(self) -> None:
        # POST with username containing <script> — invalid credentials path.
        csrf = self._get_login_csrf()
        body = f"csrf_token={csrf}&username=%3Cscript%3E&password=wrong"
        status, body_text, _ = self._request("/login", method="POST", body=body)
        self.assertEqual(status, 401)
        # The error message is static ("Invalid username or password"), but
        # verify the page itself does not contain unescaped <script>.
        # The username is not reflected back, so just verify no raw <script>.
        self.assertNotIn("<script>", body_text)

    # --- Session TTL from env ---

    def test_session_ttl_from_env(self) -> None:
        env = _env_with_credentials(SESSION_TTL_SECONDS="3600")
        _, _, headers = self._login(env=env)
        set_cookie = headers["Set-Cookie"]
        self.assertIn("Max-Age=3600", set_cookie)

    # --- CSP header ---

    def test_csp_header_on_login_page(self) -> None:
        status, _, headers = self._request("/login")
        self.assertIn("Content-Security-Policy", headers)

    # --- Nav links ---

    def test_nav_links_include_login_logout(self) -> None:
        # Login to get a cookie.
        _, _, login_headers = self._login()
        cookie_value = _extract_cookie_value(login_headers["Set-Cookie"])
        status, body, _ = self._request(
            "/",
            headers={"Cookie": f"{SESSION_COOKIE_NAME}={cookie_value}"},
        )
        self.assertEqual(status, 200)
        # Authenticated: Logout shown, Login absent (auth-state-aware nav)
        self.assertIn('<a href="/logout"', body)
        self.assertNotIn('<a href="/login"', body)

        # Anonymous: Login shown, Logout absent (login page renders with identity=None)
        status_anon, body_anon, _ = self._request("/login")
        self.assertEqual(status_anon, 200)
        self.assertIn('<a href="/login"', body_anon)
        self.assertNotIn('<a href="/logout"', body_anon)

    # --- RBAC guard still applies to cookie auth ---

    def test_rbac_guard_still_applies_to_cookie_auth(self) -> None:
        # Create a session with OPERATOR role (manually via store).
        now_val = 1000000000  # fixed-ish timestamp
        import time as _time

        now_val = int(_time.time())
        sid = self.session_store.create(
            role=Role.OPERATOR, tenant_id="default", ttl_seconds=28800, now=now_val
        )
        from rbac.session import issue_session_cookie

        cookie_value = issue_session_cookie(
            "test-secret", sid, role=Role.OPERATOR, tenant_id="default", ttl_seconds=28800, now=now_val
        )
        # OPERATOR is denied /gates (ADMIN-only).
        status, body, _ = self._request(
            "/gates",
            headers={"Cookie": f"{SESSION_COOKIE_NAME}={cookie_value}"},
        )
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
