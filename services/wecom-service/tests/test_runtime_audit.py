from __future__ import annotations

import json
from pathlib import Path
import stat
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
