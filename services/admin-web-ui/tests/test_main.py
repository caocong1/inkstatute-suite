"""Socket-level integration tests for admin-web-ui HTTP entry point."""

from __future__ import annotations

import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from admin_web_ui.__main__ import create_server
from admin_web_ui.csrf import issue_csrf_token
from platform_runtime.feature_flags import RuntimeFeatureDisabledError
from rbac import Identity, Role, issue_token


class AdminWebUiMainIntegrationTests(unittest.TestCase):
    """Boot the web UI on an ephemeral port and exercise GET/POST concurrency."""

    SECRET = "test-web-ui-secret"

    def _env(self, tmpdir: Path, **overrides: str) -> dict[str, str]:
        return {
            "INKSTATUTE_ADMIN_WEB_UI_ENABLED": "true",
            "INKSTATUTE_ADMIN_API_ENABLED": "true",
            "INKSTATUTE_OPERATOR_CONFIG_ENABLED": "true",
            "INKSTATUTE_RBAC_ENABLED": "true",
            "ADMIN_WEB_UI_HOST": "127.0.0.1",
            "ADMIN_WEB_UI_PORT": "0",
            "ADMIN_CONSOLE_API_HOST": "127.0.0.1",
            "ADMIN_CONSOLE_API_PORT": "0",
            "RBAC_TOKEN_SECRET": self.SECRET,
            "ADMIN_API_TOKEN": "static-admin-token",
            "INKSTATUTE_OPERATOR_CONFIG_PATH": str(tmpdir / "operator-config.json"),
            "INKSTATUTE_CONTRACT_LOG_PATH": str(tmpdir / "events.jsonl"),
            "INKSTATUTE_FEEDBACK_QUEUE_PATH": str(tmpdir / "feedback.jsonl"),
            **overrides,
        }

    def _start(self, httpd) -> int:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.shutdown)
        return httpd.server_address[1]

    def _request(self, port: int, path: str, method="GET", data: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, str]:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}",
            data=data,
            method=method,
        )
        if headers:
            for key, value in headers.items():
                req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", errors="replace")

    def test_concurrent_index_requests_return_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = self._env(Path(tmpdir))
            httpd = create_server(env)
            port = self._start(httpd)

            token = issue_token(self.SECRET, role=Role.ADMIN, tenant_id="default")
            results: list[tuple[int, str]] = []
            errors: list[Exception] = []

            def _fetch() -> None:
                try:
                    results.append(
                        self._request(port, "/", headers={"Authorization": f"Bearer {token}"})
                    )
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            threads = [threading.Thread(target=_fetch) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [])
            self.assertEqual(len(results), 2)
            for status, body in results:
                self.assertEqual(status, 200)
                self.assertIn("<!DOCTYPE html>", body)

    def test_post_config_channels_with_csrf_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = self._env(Path(tmpdir))
            httpd = create_server(env)
            port = self._start(httpd)

            token = issue_token(self.SECRET, role=Role.ADMIN, tenant_id="default")
            identity = Identity(role=Role.ADMIN, tenant_id="default")
            csrf_token = issue_csrf_token(identity, "/config/channels", signing_key=self.SECRET)

            form = urllib.parse.urlencode(
                {
                    "csrf_token": csrf_token,
                    "qqbot.enabled": "1",
                    "qqbot.channel_id": "qqbot",
                    "qqbot.app_id_ref": "env:QQBOT_APP_ID",
                    "wecom.enabled": "0",
                    "wecom.channel_id": "wecom",
                }
            ).encode("utf-8")

            status, body = self._request(
                port,
                "/config/channels",
                method="POST",
                data=form,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            self.assertEqual(status, 200)
            self.assertIn("Channel config saved", body)

    def test_create_server_with_disabled_flag_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = self._env(Path(tmpdir), INKSTATUTE_ADMIN_WEB_UI_ENABLED="false")
            with self.assertRaises(RuntimeFeatureDisabledError):
                create_server(env)


if __name__ == "__main__":
    unittest.main()
