"""Socket-level integration tests for admin-console-api HTTP server."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from admin_console_api.server import AdminConsoleApiServer, create_server
from platform_runtime.feature_flags import RuntimeFeatureDisabledError
from rbac import Role, issue_token


class AdminConsoleApiServerIntegrationTests(unittest.TestCase):
    """Boot the API on an ephemeral port and exercise GET/PUT concurrency."""

    SECRET = "test-server-secret"

    def _env(self, tmpdir: Path, **overrides: str) -> dict[str, str]:
        return {
            "INKSTATUTE_ADMIN_API_ENABLED": "true",
            "INKSTATUTE_OPERATOR_CONFIG_ENABLED": "true",
            "INKSTATUTE_RBAC_ENABLED": "true",
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
        """Start a server in a daemon thread and return the bound port."""
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.shutdown)
        return httpd.server_address[1]

    def _get(self, port: int, path: str, headers: dict[str, str] | None = None) -> tuple[int, dict]:
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
        if headers:
            for key, value in headers.items():
                req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, {"raw": body}

    def _put(self, port: int, path: str, body: dict, headers: dict[str, str] | None = None) -> tuple[int, dict]:
        data = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        if headers:
            for key, value in headers.items():
                req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, {"raw": body}

    def test_concurrent_health_requests_do_not_serialize(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = self._env(Path(tmpdir))
            httpd = create_server(env)
            port = self._start(httpd)

            token = issue_token(self.SECRET, role=Role.ADMIN, tenant_id="default")
            results: list[tuple[int, dict]] = []
            errors: list[Exception] = []

            def _fetch() -> None:
                try:
                    results.append(
                        self._get(port, "/health", {"Authorization": f"Bearer {token}"})
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
                self.assertEqual(body.get("status"), "ok")

    def test_get_sessions_with_bearer_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = self._env(Path(tmpdir))
            httpd = create_server(env)
            port = self._start(httpd)

            token = issue_token(self.SECRET, role=Role.ADMIN, tenant_id="default")
            status, body = self._get(
                port,
                "/sessions",
                {"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(status, 200)
            self.assertIn("items", body)

    def test_put_config_channels_updates_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = self._env(Path(tmpdir))
            httpd = create_server(env)
            port = self._start(httpd)

            body = {
                "qqbot": {
                    "channel_id": "qqbot",
                    "enabled": False,
                    "app_id_ref": "env:QQBOT_APP_ID",
                    "app_secret_ref": None,
                    "token_secret_ref": None,
                    "bot_secret_ref": None,
                    "metadata": {},
                },
                "wecom": {
                    "channel_id": "wecom",
                    "enabled": False,
                    "token_secret_ref": None,
                    "encoding_aes_key_secret_ref": None,
                    "corp_id_ref": None,
                    "metadata": {},
                },
            }
            token = issue_token(self.SECRET, role=Role.ADMIN, tenant_id="default")
            status, response = self._put(
                port,
                "/config/channels",
                body,
                {"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(status, 200)
            self.assertEqual(response["data"]["qqbot"]["app_id_ref"], "env:QQBOT_APP_ID")

    def test_create_server_with_disabled_flag_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = self._env(Path(tmpdir), INKSTATUTE_ADMIN_API_ENABLED="false")
            with self.assertRaises(RuntimeFeatureDisabledError):
                create_server(env)


if __name__ == "__main__":
    unittest.main()
