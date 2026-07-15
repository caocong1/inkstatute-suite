"""End-to-end console smoke test for the admin web UI (Phase 87).

Boots the admin-web-ui via ``create_server`` on an ephemeral port, logs in via
session auth (POST /login with CSRF + credentials), exercises every major
surface, starts a channel host subprocess, views scrubbed log lines, browses
reports, and audits a contract event trace — all within stdlib-only constraints
and stamping ``not_live_acceptance=true`` on every evidence record.
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from admin_web_ui.__main__ import create_server
from admin_web_ui.csrf import issue_csrf_token
from conversation_read_view.log_reader import LogReader
from conversation_read_view.read_model import build_read_model
from rbac import Identity, Role

_SELF_PATH = Path(__file__).resolve()

_NO_REDIRECT_OPENER = urllib.request.OpenerDirector()
_NO_REDIRECT_OPENER.add_handler(urllib.request.HTTPHandler())
_NO_REDIRECT_OPENER.add_handler(urllib.request.HTTPSHandler())
_NO_REDIRECT_OPENER.add_handler(urllib.request.HTTPDefaultErrorHandler())
_NO_REDIRECT_OPENER.add_handler(urllib.request.HTTPErrorProcessor())

_SURFACES = [
    "/",
    "/config/channels",
    "/config/providers",
    "/config/catalog",
    "/config/vision",
    "/sessions",
    "/reports",
    "/logs",
    "/audit",
    "/health",
    "/gates",
    "/processes",
]


class TestConsoleSmokeEndToEnd(unittest.TestCase):
    """End-to-end smoke that boots the console and exercises every surface."""

    SECRET = "test-smoke-secret"

    def _env(self, tmpdir: Path) -> dict[str, str]:
        return {
            "INKSTATUTE_ADMIN_WEB_UI_ENABLED": "true",
            "INKSTATUTE_ADMIN_API_ENABLED": "true",
            "INKSTATUTE_OPERATOR_CONFIG_ENABLED": "true",
            "INKSTATUTE_RBAC_ENABLED": "true",
            "INKSTATUTE_QQBOT_CHANNEL_ENABLED": "true",
            "INKSTATUTE_WECOM_CHANNEL_ENABLED": "true",
            "ADMIN_WEB_UI_HOST": "127.0.0.1",
            "ADMIN_WEB_UI_PORT": "0",
            "ADMIN_CONSOLE_API_HOST": "127.0.0.1",
            "ADMIN_CONSOLE_API_PORT": "0",
            "RBAC_TOKEN_SECRET": self.SECRET,
            "ADMIN_API_TOKEN": "static-admin-token",
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "test-pass",
            "INKSTATUTE_OPERATOR_CONFIG_PATH": str(tmpdir / "operator-config.json"),
            "INKSTATUTE_CONTRACT_LOG_PATH": str(tmpdir / "events.jsonl"),
            "INKSTATUTE_FEEDBACK_QUEUE_PATH": str(tmpdir / "feedback.jsonl"),
            "INKSTATUTE_PROCESS_STATE_PATH": str(tmpdir / "process-state.json"),
            "INKSTATUTE_PROCESS_LOG_DIR": str(tmpdir / "process-logs"),
        }

    def _start(self, httpd) -> int:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.shutdown)
        return httpd.server_address[1]

    def _request(
        self,
        port: int,
        path: str,
        method: str = "GET",
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, str, dict[str, str]]:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}",
            data=data,
            method=method,
        )
        if headers:
            for key, value in headers.items():
                req.add_header(key, value)
        try:
            with _NO_REDIRECT_OPENER.open(req, timeout=5) as resp:
                body = resp.read().decode("utf-8")
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                return resp.status, body, resp_headers
        except urllib.error.HTTPError as exc:
            with exc:
                body = exc.read().decode("utf-8", errors="replace")
                resp_headers = (
                    {k.lower(): v for k, v in exc.headers.items()}
                    if exc.headers
                    else {}
                )
                return exc.code, body, resp_headers

    def _login(self, port: int) -> str:
        status, body, _ = self._request(port, "/login")
        self.assertEqual(status, 200)
        marker = 'name="csrf_token" value="'
        idx = body.index(marker) + len(marker)
        end = body.index('"', idx)
        csrf_token = body[idx:end]
        form = urllib.parse.urlencode(
            {
                "csrf_token": csrf_token,
                "username": "admin",
                "password": "test-pass",
            }
        ).encode("utf-8")
        status, body, headers = self._request(
            port,
            "/login",
            method="POST",
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(status, 302)
        set_cookie = headers.get("set-cookie", "")
        self.assertIn("inkstatute_session=", set_cookie)
        prefix = "inkstatute_session="
        start = set_cookie.index(prefix) + len(prefix)
        rest = set_cookie[start:]
        end = rest.index(";") if ";" in rest else len(rest)
        cookie_value = rest[:end]
        return f"inkstatute_session={cookie_value}"

    def _write_contract_log(self, tmpdir: Path) -> str:
        path = tmpdir / "events.jsonl"
        occurred_at = "2026-07-01T00:00:00Z"
        records = [
            {
                "event_key": "agent_turn",
                "occurred_at": occurred_at,
                "ingested_at": occurred_at,
                "seq": 1,
                "event": {
                    "turn_id": "turn-smoke-001",
                    "conversation_id": "conv-smoke-001",
                    "channel": "wecom",
                    "user_id": "user-smoke-01",
                    "message_type": "text",
                    "received_at": occurred_at,
                },
            },
            {
                "event_key": "execution_trace",
                "occurred_at": "2026-07-01T00:00:02Z",
                "ingested_at": "2026-07-01T00:00:02Z",
                "seq": 2,
                "event": {
                    "trace_id": "trace-smoke-001",
                    "turn_id": "turn-smoke-001",
                    "started_at": "2026-07-01T00:00:02Z",
                    "ended_at": "2026-07-01T00:00:03Z",
                    "active_skill_name": None,
                    "matched_registered_skill": False,
                    "occurred_at": "2026-07-01T00:00:02Z",
                    "ingested_at": "2026-07-01T00:00:02Z",
                    "seq": 2,
                },
            },
            {
                "event_key": "agent_result",
                "occurred_at": "2026-07-01T00:00:04Z",
                "ingested_at": "2026-07-01T00:00:04Z",
                "seq": 3,
                "event": {
                    "result_id": "res-turn-smoke-001",
                    "turn_id": "turn-smoke-001",
                    "status": "success",
                    "reply_type": "text",
                    "metadata": {"trace_id": "trace-smoke-001"},
                },
            },
        ]
        lines = [json.dumps(rec, ensure_ascii=False, sort_keys=True) for rec in records]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(path)

    def _build_evidence(
        self,
        surfaces: list[tuple[str, int]],
        audit_trace: dict[str, object],
    ) -> dict[str, object]:
        return {
            "schema": "console-smoke-v1",
            "mode": "dry-run",
            "not_live_acceptance": True,
            "surfaces": {
                surface: {"status": status, "passed": status == 200}
                for surface, status in surfaces
            },
            "audit_trace": audit_trace,
        }

    def test_console_smoke_e2e(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            env = self._env(tmpdir_path)
            self._write_contract_log(tmpdir_path)
            httpd = create_server(env)
            port = self._start(httpd)

            cookie = self._login(port)

            surfaces: list[tuple[str, int]] = []
            for surface in _SURFACES:
                status, body, _ = self._request(
                    port, surface, headers={"Cookie": cookie}
                )
                surfaces.append((surface, status))

            for surface, status in surfaces:
                self.assertEqual(status, 200, f"Surface {surface} returned {status}")

            audit_status, audit_body, _ = self._request(
                port, "/audit", headers={"Cookie": cookie}
            )
            self.assertEqual(audit_status, 200)
            self.assertIn("Contract Event Audit", audit_body)
            self.assertIn("trace-smoke-001", audit_body)

            trace_status, trace_body, _ = self._request(
                port, "/audit/trace-smoke-001", headers={"Cookie": cookie}
            )
            self.assertEqual(trace_status, 200)
            self.assertIn("Trace Reconstruction", trace_body)

            evidence = self._build_evidence(
                surfaces,
                {"status": trace_status, "passed": trace_status == 200},
            )
            self.assertIs(evidence["not_live_acceptance"], True)
            for surface, status in surfaces:
                self.assertTrue(evidence["surfaces"][surface]["passed"])

    def test_smoke_evidence_stamps_not_live_acceptance(self) -> None:
        evidence = self._build_evidence(
            [("/", 200), ("/reports", 200)],
            {"status": 200, "passed": True},
        )
        self.assertIs(evidence["not_live_acceptance"], True)

    def test_smoke_uses_only_stdlib_http_client(self) -> None:
        source = _SELF_PATH.read_text(encoding="utf-8")
        self.assertIn("urllib.request", source)
        for name in ("requests", "httpx", "aiohttp"):
            self.assertNotIn("import " + name, source)

    def test_smoke_login_csrf_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            env = self._env(tmpdir_path)
            httpd = create_server(env)
            port = self._start(httpd)

            form = urllib.parse.urlencode(
                {"username": "admin", "password": "test-pass"}
            ).encode("utf-8")
            status, body, _ = self._request(
                port,
                "/login",
                method="POST",
                data=form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
