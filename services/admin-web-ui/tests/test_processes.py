"""Tests for the admin web UI Process Orchestration page."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from admin_web_ui.csrf import issue_csrf_token
from admin_web_ui.server import handle_admin_web_ui_request
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac import Identity, Role


class ProcessesPageTests(unittest.TestCase):
    """Smoke tests for the /processes UI route and action POST."""

    def setUp(self) -> None:
        self.flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
            operator_config_enabled=True,
            qqbot_channel_enabled=True,
            wecom_channel_enabled=True,
        )
        self.identity = Identity(role=Role.ADMIN, tenant_id="default")
        self.csrf_token = issue_csrf_token(self.identity, "/processes")
        self.handle_admin_get = MagicMock(return_value=(
            200,
            {
                "processes": [
                    {
                        "name": "wecom",
                        "status": "stopped",
                        "pid": None,
                        "started_at": None,
                        "last_exit_code": None,
                        "host": "127.0.0.1",
                        "port": 8082,
                        "log_path": "",
                        "metadata": {},
                    },
                    {
                        "name": "qqbot",
                        "status": "stopped",
                        "pid": None,
                        "started_at": None,
                        "last_exit_code": None,
                        "host": "127.0.0.1",
                        "port": 8080,
                        "log_path": "",
                        "metadata": {},
                    },
                ],
                "metadata": {"count": 2},
            },
        ))
        self.handle_admin_put = MagicMock(return_value=(200, {"status": "ok"}))

    def _get(self) -> tuple[int, str, dict]:
        return handle_admin_web_ui_request(
            "/processes",
            None,
            feature_flags=self.flags,
            handle_admin_get=self.handle_admin_get,
            read_model=None,
            handle_admin_put=self.handle_admin_put,
            process_supervisor=MagicMock(),
        )

    def _post(self, body: str) -> tuple[int, str, dict]:
        return handle_admin_web_ui_request(
            "/processes",
            None,
            feature_flags=self.flags,
            handle_admin_get=self.handle_admin_get,
            read_model=None,
            method="POST",
            body=body,
            handle_admin_put=self.handle_admin_put,
            process_supervisor=MagicMock(),
        )

    def test_get_renders_process_orchestration(self) -> None:
        status, html, _headers = self._get()
        self.assertEqual(status, 200)
        self.assertIn("Process Orchestration", html)
        self.assertIn("wecom", html)
        self.assertIn("qqbot", html)

    def test_post_proxies_start_action(self) -> None:
        body = f"name=wecom&action=start&csrf_token={self.csrf_token}"
        status, _html, _headers = self._post(body)
        self.assertEqual(status, 200)
        self.handle_admin_put.assert_called_once()
        kwargs = self.handle_admin_put.call_args.kwargs
        self.assertEqual(kwargs.get("path"), "/processes/wecom/start")

    def test_post_rejects_unknown_name(self) -> None:
        body = f"name=unknown&action=start&csrf_token={self.csrf_token}"
        status, html, _headers = self._post(body)
        self.assertEqual(status, 400)
        self.assertIn("unknown process name", html)

    def test_post_rejects_unknown_action(self) -> None:
        body = f"name=wecom&action=purge&csrf_token={self.csrf_token}"
        status, html, _headers = self._post(body)
        self.assertEqual(status, 400)
        self.assertIn("unknown process action", html)


if __name__ == "__main__":
    unittest.main()
