from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from wecom_service.runtime_audit import append_runtime_audit, parse_bool_env


class RuntimeAuditTests(unittest.TestCase):
    def test_append_runtime_audit_writes_private_full_payload_with_secret_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"

            append_runtime_audit(
                path,
                kind="bot_inbound",
                direction="inbound",
                payload={"text": "审查合同", "access_token": "secret-token-value"},
                include_payload=True,
                metadata={"message_id": "msg-1", "secret": "abc"},
            )

            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["kind"], "bot_inbound")
            self.assertEqual(record["payload"]["text"], "审查合同")
            self.assertEqual(record["payload"]["access_token"], "[REDACTED]")
            self.assertEqual(record["metadata"]["secret"], "[REDACTED]")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_append_runtime_audit_can_store_summary_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"

            record = append_runtime_audit(
                path,
                kind="hermes_response",
                direction="inbound",
                payload={"stdout": "法律意见正文"},
                include_payload=False,
            )

            self.assertNotIn("payload", record)
            self.assertIn("sha256_16", record["payload_summary"])

    def test_parse_bool_env(self) -> None:
        self.assertTrue(parse_bool_env(None, default=True))
        self.assertFalse(parse_bool_env("0", default=True))
        self.assertFalse(parse_bool_env("false", default=True))
        self.assertTrue(parse_bool_env("1", default=False))

    def test_chmod_oserror_is_silently_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"

            with patch("os.chmod", side_effect=OSError("permission denied")):
                record = append_runtime_audit(
                    path,
                    kind="test_chmod",
                    direction="outbound",
                    payload={"data": "value"},
                )

            self.assertEqual(record["kind"], "test_chmod")
            self.assertTrue(path.exists())

    def test_redact_secrets_handles_tuples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"

            record = append_runtime_audit(
                path,
                kind="tuple_test",
                direction="inbound",
                payload=("item1", "item2"),
                include_payload=True,
            )

            self.assertEqual(record["payload"], ["item1", "item2"])

    def test_redact_secrets_handles_nested_lists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"

            record = append_runtime_audit(
                path,
                kind="list_test",
                direction="inbound",
                payload={"items": ["a", "b"], "nested_secret": "val"},
                include_payload=True,
            )

            self.assertEqual(record["payload"]["items"], ["a", "b"])

    def test_redact_known_env_secret_values_in_strings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"

            with patch.dict(os.environ, {"MY_SECRET_TOKEN": "supersecretvalue123"}, clear=False):
                record = append_runtime_audit(
                    path,
                    kind="env_redact_test",
                    direction="inbound",
                    payload={"text": "The value is supersecretvalue123 here"},
                    include_payload=True,
                )

            self.assertIn("[REDACTED]", record["payload"]["text"])
            self.assertNotIn("supersecretvalue123", record["payload"]["text"])

    def test_stable_json_fallback_for_non_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"

            record = append_runtime_audit(
                path,
                kind="non_serializable",
                direction="inbound",
                payload=object(),
            )

            self.assertIn("sha256_16", record["payload_summary"])
            self.assertIsInstance(record["payload_summary"]["length"], int)

    def test_parse_bool_env_edge_cases(self) -> None:
        self.assertFalse(parse_bool_env("", default=False))
        self.assertTrue(parse_bool_env("", default=True))
        self.assertFalse(parse_bool_env("no", default=True))
        self.assertFalse(parse_bool_env("off", default=True))
        self.assertTrue(parse_bool_env("yes", default=False))
        self.assertTrue(parse_bool_env("true", default=False))


if __name__ == "__main__":
    unittest.main()
