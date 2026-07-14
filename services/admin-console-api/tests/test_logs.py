"""Tests for the /logs admin API route and RBAC wiring (Phase 82)."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from admin_console_api.api import handle_admin_get
from admin_console_api.routes import ROUTE_PREFIXES
from conversation_read_view.log_reader import LogReader
from platform_runtime.feature_flags import RuntimeFeatureFlags
from rbac import Role, issue_token
from rbac.matrix import PERMISSIONS_MATRIX


def _make_jsonl(lines: list[str], suffix: str = ".jsonl") -> str:
    path = Path(tempfile.mktemp(suffix=suffix))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _make_text(lines: list[str]) -> str:
    path = Path(tempfile.mktemp(suffix=".log"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


@dataclass
class _FakeRecord:
    name: str = "wecom"
    status: str = "running"
    pid: int | None = 1234
    log_path: str = ""


class LogsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.feature_flags = RuntimeFeatureFlags(admin_api_enabled=True)
        self.env = {"ADMIN_API_TOKEN": "test-token"}
        self.headers = {"Authorization": "Bearer test-token"}

    def _make_reader_with_contract_log(self, lines: list[str]) -> tuple[LogReader, str]:
        path = _make_jsonl(lines)
        self.addCleanup(lambda: Path(path).unlink(missing_ok=True))
        reader = LogReader(env={"INKSTATUTE_CONTRACT_LOG_PATH": path})
        return reader, path

    def _get_logs(self, path: str = "/logs", query: str | dict = "", log_reader: Any = None) -> tuple[int, dict[str, Any]]:
        return handle_admin_get(
            path,
            query,
            self.headers,
            read_model=None,
            feedback_queue=[],
            feature_flags=self.feature_flags,
            env=self.env,
            log_reader=log_reader,
        )

    # --- List sources ---

    def test_logs_list_sources(self) -> None:
        reader = LogReader(env={})
        status, body = self._get_logs("/logs", "", reader)
        self.assertEqual(status, 200)
        self.assertIn("sources", body)
        self.assertEqual(len(body["sources"]), 5)
        names = [s["source"] for s in body["sources"]]
        self.assertIn("contract_events", names)
        self.assertIn("runtime_audit", names)
        self.assertIn("feedback", names)
        self.assertIn("wecom_stdout", names)
        self.assertIn("qqbot_stdout", names)

    # --- Read contract events ---

    def test_logs_read_contract_events(self) -> None:
        reader, _ = self._make_reader_with_contract_log([
            json.dumps({"level": "INFO", "msg": "line1"}),
            json.dumps({"level": "INFO", "msg": "line2"}),
        ])
        status, body = self._get_logs("/logs/contract_events", "", reader)
        self.assertEqual(status, 200)
        self.assertIn("lines", body)
        self.assertGreater(body["next_offset"], 0)
        self.assertEqual(len(body["lines"]), 2)

    def test_logs_read_with_offset(self) -> None:
        reader, _ = self._make_reader_with_contract_log([
            json.dumps({"level": "INFO", "msg": "line1"}),
            json.dumps({"level": "INFO", "msg": "line2"}),
            json.dumps({"level": "INFO", "msg": "line3"}),
        ])
        status1, body1 = self._get_logs("/logs/contract_events", {"max_lines": "1"}, reader)
        self.assertEqual(status1, 200)
        self.assertEqual(len(body1["lines"]), 1)
        status2, body2 = self._get_logs(
            "/logs/contract_events",
            {"offset": str(body1["next_offset"])},
            reader,
        )
        self.assertEqual(status2, 200)
        self.assertEqual(len(body2["lines"]), 2)

    # --- Level filter ---

    def test_logs_level_filter(self) -> None:
        reader, _ = self._make_reader_with_contract_log([
            json.dumps({"level": "ERROR", "msg": "err"}),
            json.dumps({"level": "INFO", "msg": "info"}),
            json.dumps({"level": "DEBUG", "msg": "dbg"}),
        ])
        status, body = self._get_logs("/logs/contract_events", {"level": "ERROR"}, reader)
        self.assertEqual(status, 200)
        levels = [ln["level"] for ln in body["lines"]]
        self.assertEqual(levels, ["ERROR"])

    # --- Keyword search ---

    def test_logs_keyword_search(self) -> None:
        reader, _ = self._make_reader_with_contract_log([
            json.dumps({"level": "INFO", "msg": "alpha keyword here"}),
            json.dumps({"level": "INFO", "msg": "beta no match"}),
        ])
        status, body = self._get_logs("/logs/contract_events", {"q": "keyword"}, reader)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["lines"]), 1)

    # --- Privacy scrub ---

    def test_logs_privacy_scrub(self) -> None:
        reader, _ = self._make_reader_with_contract_log([
            json.dumps({"level": "INFO", "raw_payload": "secret-data"}),
        ])
        status, body = self._get_logs("/logs/contract_events", "", reader)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["lines"]), 1)
        self.assertIn("[REDACTED", body["lines"][0]["text"])
        self.assertNotIn("secret-data", body["lines"][0]["text"])

    # --- Rotation ---

    def test_logs_rotation(self) -> None:
        reader, path = self._make_reader_with_contract_log([
            json.dumps({"level": "INFO", "msg": f"line{i}"}) for i in range(5)
        ])
        status1, body1 = self._get_logs("/logs/contract_events", "", reader)
        # Truncate.
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"level": "INFO", "msg": "new"}) + "\n")
        status2, body2 = self._get_logs(
            "/logs/contract_events",
            {"offset": str(body1["next_offset"]), "inode": str(body1["inode"])},
            reader,
        )
        self.assertEqual(status2, 200)
        self.assertTrue(body2["metadata"]["rotated"])

    # --- Unknown source ---

    def test_logs_unknown_source(self) -> None:
        reader = LogReader(env={})
        status, body = self._get_logs("/logs/unknown", "", reader)
        self.assertEqual(status, 404)

    def test_logs_source_not_configured(self) -> None:
        reader = LogReader(env={})
        status, body = self._get_logs("/logs/contract_events", "", reader)
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "source_not_configured")

    def test_logs_source_not_found(self) -> None:
        reader = LogReader(env={"INKSTATUTE_CONTRACT_LOG_PATH": "/nonexistent/file.jsonl"})
        status, body = self._get_logs("/logs/contract_events", "", reader)
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "source_not_found")

    # --- Validation ---

    def test_logs_invalid_level(self) -> None:
        reader, _ = self._make_reader_with_contract_log([
            json.dumps({"level": "INFO", "msg": "x"}),
        ])
        status, body = self._get_logs("/logs/contract_events", {"level": "TRACE"}, reader)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_level")

    def test_logs_negative_offset(self) -> None:
        reader, _ = self._make_reader_with_contract_log([
            json.dumps({"level": "INFO", "msg": "x"}),
        ])
        status, body = self._get_logs("/logs/contract_events", {"offset": "-1"}, reader)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_offset")

    # --- Feature flag / log_reader None ---

    def test_logs_admin_api_disabled(self) -> None:
        flags = RuntimeFeatureFlags()
        reader = LogReader(env={})
        status, body = handle_admin_get(
            "/logs",
            "",
            self.headers,
            read_model=None,
            feedback_queue=[],
            feature_flags=flags,
            env=self.env,
            log_reader=reader,
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "admin_api_disabled")

    def test_logs_log_reader_none(self) -> None:
        status, body = self._get_logs("/logs", "", None)
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["code"], "log_reader_unavailable")

    # --- RBAC ---

    def test_logs_rbac_admin_allowed(self) -> None:
        self._test_rbac_role(Role.ADMIN, 200)

    def test_logs_rbac_operator_allowed(self) -> None:
        self._test_rbac_role(Role.OPERATOR, 200)

    def test_logs_rbac_lawyer_denied(self) -> None:
        self._test_rbac_role(Role.LAWYER, 403)

    def test_logs_rbac_viewer_denied(self) -> None:
        self._test_rbac_role(Role.VIEWER, 403)

    def _test_rbac_role(self, role: Role, expected_status: int) -> None:
        rbac_secret = "test-secret"
        flags = RuntimeFeatureFlags(
            admin_api_enabled=True, rbac_enabled=True, multi_tenant_enabled=False,
        )
        token = issue_token(rbac_secret, role=role, tenant_id="default")
        reader = LogReader(env={})
        status, _ = handle_admin_get(
            "/logs",
            "",
            {"Authorization": f"Bearer {token}"},
            read_model=None,
            feedback_queue=[],
            feature_flags=flags,
            env={},
            rbac_secret=rbac_secret,
            log_reader=reader,
        )
        self.assertEqual(status, expected_status)

    # --- wecom_stdout via process_supervisor ---

    def test_logs_wecom_stdout(self) -> None:
        log_path = _make_text(["INFO: wecom started"])
        self.addCleanup(lambda: Path(log_path).unlink(missing_ok=True))
        supervisor = MagicMock()
        supervisor.status.return_value = _FakeRecord(log_path=log_path)
        reader = LogReader(
            env={"INKSTATUTE_PROCESS_LOG_DIR": str(Path(log_path).parent)},
            process_supervisor=supervisor,
        )
        status, body = self._get_logs("/logs/wecom_stdout", "", reader)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["lines"]), 1)

    # --- RBAC scan ---

    def test_rbac_scan_passes(self) -> None:
        self.assertIn("/logs", ROUTE_PREFIXES)
        self.assertIn("/logs", PERMISSIONS_MATRIX)
        allowed = PERMISSIONS_MATRIX["/logs"]
        self.assertIn(Role.ADMIN, allowed)
        self.assertIn(Role.OPERATOR, allowed)


if __name__ == "__main__":
    unittest.main()
