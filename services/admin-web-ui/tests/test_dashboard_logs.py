"""Integration tests for the /logs admin web UI page (Phase 82)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from admin_console_api.api import handle_admin_get
from admin_web_ui.server import handle_admin_web_ui_request
from conversation_read_view.log_reader import LogReader
from platform_runtime.feature_flags import RuntimeFeatureFlags


def _make_jsonl(lines: list[str]) -> str:
    path = Path(tempfile.mktemp(suffix=".jsonl"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


class LogsDashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.feature_flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
        )
        self.env = {"ADMIN_API_TOKEN": "test-token"}

    def _request(
        self,
        path: str = "/logs",
        *,
        log_reader: Any = None,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str, dict[str, str]]:
        return handle_admin_web_ui_request(
            path,
            {"Authorization": "Bearer test-token"},
            feature_flags=self.feature_flags,
            handle_admin_get=handle_admin_get,
            read_model=None,
            feedback_queue=[],
            env=env or self.env,
            rbac_secret=None,
            log_reader=log_reader,
        )

    # --- Source list page ---

    def test_logs_page_renders_sources(self) -> None:
        log_reader = LogReader(env={})
        status, body, _ = self._request(log_reader=log_reader)
        self.assertEqual(status, 200)
        self.assertIn("Log Source", body)
        self.assertIn("Contract Events", body)
        self.assertIn("Runtime Audit", body)
        self.assertIn("Feedback Queue", body)
        self.assertIn("WeCom", body)
        self.assertIn("QQBot", body)

    def test_logs_page_nav_link(self) -> None:
        log_reader = LogReader(env={})
        status, body, _ = self._request(log_reader=log_reader)
        self.assertEqual(status, 200)
        self.assertIn('href="/logs"', body)
        self.assertIn("Logs", body)

    def test_logs_page_meta_refresh(self) -> None:
        log_reader = LogReader(env={})
        status, body, _ = self._request(log_reader=log_reader)
        self.assertEqual(status, 200)
        self.assertIn('<meta http-equiv="refresh"', body)

    # --- Log line rendering ---

    def test_logs_page_renders_lines(self) -> None:
        log_path = _make_jsonl([
            json.dumps({"level": "INFO", "msg": "hello world"}),
        ])
        self.addCleanup(lambda: Path(log_path).unlink(missing_ok=True))
        env = {**self.env, "INKSTATUTE_CONTRACT_LOG_PATH": log_path}
        log_reader = LogReader(env=env)
        status, body, _ = self._request(
            "/logs/contract_events?offset=0",
            log_reader=log_reader,
            env=env,
        )
        self.assertEqual(status, 200)
        self.assertIn("hello world", body)

    def test_logs_page_html_escaped(self) -> None:
        log_path = _make_jsonl([
            json.dumps({"level": "INFO", "msg": "<script>alert(1)</script>"}),
        ])
        self.addCleanup(lambda: Path(log_path).unlink(missing_ok=True))
        env = {**self.env, "INKSTATUTE_CONTRACT_LOG_PATH": log_path}
        log_reader = LogReader(env=env)
        status, body, _ = self._request(
            "/logs/contract_events?offset=0",
            log_reader=log_reader,
            env=env,
        )
        self.assertEqual(status, 200)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;", body)

    def test_logs_page_privacy_scrubbed(self) -> None:
        """Lines with forbidden keys (raw_payload) must be redacted."""
        log_path = _make_jsonl([
            json.dumps({"level": "INFO", "raw_payload": "secret-data"}),
        ])
        self.addCleanup(lambda: Path(log_path).unlink(missing_ok=True))
        env = {**self.env, "INKSTATUTE_CONTRACT_LOG_PATH": log_path}
        log_reader = LogReader(env=env)
        status, body, _ = self._request(
            "/logs/contract_events?offset=0",
            log_reader=log_reader,
            env=env,
        )
        self.assertEqual(status, 200)
        self.assertIn("[REDACTED", body)
        self.assertNotIn("secret-data", body)

    # --- Filter state ---

    def test_logs_page_level_filter_selected(self) -> None:
        log_reader = LogReader(env={})
        status, body, _ = self._request(
            "/logs?level=ERROR",
            log_reader=log_reader,
        )
        self.assertEqual(status, 200)
        self.assertIn('value="ERROR" selected', body)

    def test_logs_page_keyword_search_value(self) -> None:
        log_reader = LogReader(env={})
        status, body, _ = self._request(
            "/logs?q=keyword",
            log_reader=log_reader,
        )
        self.assertEqual(status, 200)
        self.assertIn('value="keyword"', body)

    def test_logs_page_next_offset_hidden(self) -> None:
        log_path = _make_jsonl([
            json.dumps({"level": "INFO", "msg": "line one"}),
        ])
        self.addCleanup(lambda: Path(log_path).unlink(missing_ok=True))
        env = {**self.env, "INKSTATUTE_CONTRACT_LOG_PATH": log_path}
        log_reader = LogReader(env=env)
        status, body, _ = self._request(
            "/logs/contract_events?offset=0",
            log_reader=log_reader,
            env=env,
        )
        self.assertEqual(status, 200)
        self.assertIn('name="offset"', body)
        self.assertIn('type="hidden"', body)

    # --- Method / RBAC ---

    def test_logs_page_post_returns_405(self) -> None:
        log_reader = LogReader(env={})
        status, body, _ = handle_admin_web_ui_request(
            "/logs",
            {"Authorization": "Bearer test-token"},
            feature_flags=self.feature_flags,
            handle_admin_get=handle_admin_get,
            read_model=None,
            feedback_queue=[],
            env=self.env,
            rbac_secret=None,
            method="POST",
            body=b"",
            log_reader=log_reader,
        )
        self.assertEqual(status, 405)

    def test_logs_page_rbac_admin_allowed(self) -> None:
        """ADMIN role should access /logs (static token fallback)."""
        log_reader = LogReader(env={})
        status, body, _ = self._request(log_reader=log_reader)
        self.assertEqual(status, 200)

    def test_logs_page_rbac_lawyer_denied(self) -> None:
        """LAWYER role should be denied /logs via RBAC."""
        from rbac import Role, issue_token

        secret = "test-rbac-secret"
        flags = RuntimeFeatureFlags(
            admin_web_ui_enabled=True,
            admin_api_enabled=True,
            rbac_enabled=True,
        )
        token = issue_token(secret, role=Role.LAWYER, tenant_id="default")
        log_reader = LogReader(env={})
        status, body, _ = handle_admin_web_ui_request(
            "/logs",
            {"Authorization": f"Bearer {token}"},
            feature_flags=flags,
            handle_admin_get=handle_admin_get,
            read_model=None,
            feedback_queue=[],
            env={**self.env, "RBAC_TOKEN_SECRET": secret},
            rbac_secret=secret,
            log_reader=log_reader,
        )
        self.assertEqual(status, 403)

    # --- Error handling ---

    def test_logs_page_error_renders(self) -> None:
        """When log_reader is None, the API returns a 503 error which renders gracefully."""
        status, body, _ = self._request(log_reader=None)
        # handle_logs returns 503 when log_reader is None; the UI renders the error.
        self.assertEqual(status, 503)
        self.assertIn("Error", body)
        self.assertIn("log_reader", body.lower())

    # --- Rotation ---

    def test_logs_page_rotation_indicator(self) -> None:
        """Reading after truncation should show rotated=true in metadata."""
        log_path = _make_jsonl([
            json.dumps({"level": "INFO", "msg": "first line"}),
            json.dumps({"level": "INFO", "msg": "second line"}),
        ])
        self.addCleanup(lambda: Path(log_path).unlink(missing_ok=True))
        env = {**self.env, "INKSTATUTE_CONTRACT_LOG_PATH": log_path}
        log_reader = LogReader(env=env)

        # First read to get the inode.
        status1, body1, _ = self._request(
            "/logs/contract_events?offset=0",
            log_reader=log_reader,
            env=env,
        )
        self.assertEqual(status1, 200)

        # Truncate the file (simulate rotation by content shrink).
        Path(log_path).write_text(
            json.dumps({"level": "INFO", "msg": "after rotation"}) + "\n",
            encoding="utf-8",
        )

        # Read again with the old offset — should detect rotation.
        status2, body2, _ = self._request(
            "/logs/contract_events?offset=100&inode=999999",
            log_reader=log_reader,
            env=env,
        )
        self.assertEqual(status2, 200)
        self.assertIn("Rotated: True", body2)


if __name__ == "__main__":
    unittest.main()
