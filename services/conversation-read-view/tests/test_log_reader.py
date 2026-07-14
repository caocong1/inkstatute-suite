"""Tests for the LogReader byte-offset tail-follow log reader (Phase 82)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

from conversation_read_view.log_reader import LogReader


@dataclass
class _FakeRecord:
    name: str = "wecom"
    status: str = "running"
    pid: int | None = 1234
    log_path: str = ""


class LogReaderTests(unittest.TestCase):
    def _make_jsonl(self, lines: list[str], suffix: str = ".jsonl") -> str:
        path = Path(tempfile.mktemp(suffix=suffix))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.addCleanup(path.unlink)
        return str(path)

    def _make_text(self, lines: list[str], suffix: str = ".log") -> str:
        path = Path(tempfile.mktemp(suffix=suffix))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.addCleanup(path.unlink)
        return str(path)

    def _reader(self, env: dict[str, str] | None = None, process_supervisor=None) -> LogReader:
        return LogReader(env=env or {}, process_supervisor=process_supervisor)

    # --- Basic read ---------------------------------------------------

    def test_read_basic(self):
        path = self._make_jsonl([
            json.dumps({"level": "INFO", "msg": "line1"}),
            json.dumps({"level": "INFO", "msg": "line2"}),
            json.dumps({"level": "INFO", "msg": "line3"}),
        ])
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": path})
        result = reader.read("contract_events", offset=0)
        self.assertEqual(result["source"], "contract_events")
        self.assertEqual(len(result["lines"]), 3)
        self.assertEqual(result["next_offset"], os.path.getsize(path))
        self.assertTrue(result["eof"])
        self.assertEqual(result["metadata"]["lines_returned"], 3)

    def test_read_with_offset(self):
        path = self._make_jsonl([
            json.dumps({"level": "INFO", "msg": "line1"}),
            json.dumps({"level": "INFO", "msg": "line2"}),
            json.dumps({"level": "INFO", "msg": "line3"}),
        ])
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": path})
        first = reader.read("contract_events", offset=0, max_lines=1)
        self.assertEqual(len(first["lines"]), 1)
        self.assertFalse(first["eof"])
        second = reader.read("contract_events", offset=first["next_offset"])
        self.assertEqual(len(second["lines"]), 2)
        self.assertTrue(second["eof"])

    # --- Level filtering ----------------------------------------------

    def test_level_filter_json(self):
        path = self._make_jsonl([
            json.dumps({"level": "ERROR", "msg": "err"}),
            json.dumps({"level": "INFO", "msg": "info"}),
            json.dumps({"level": "DEBUG", "msg": "dbg"}),
        ])
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": path})
        result = reader.read("contract_events", offset=0, level="WARN")
        levels = [ln["level"] for ln in result["lines"]]
        self.assertEqual(levels, ["ERROR"])

    def test_level_filter_plain_text(self):
        path = self._make_text([
            "ERROR: something broke",
            "INFO: all good",
            "WARNING: be careful",
        ])
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": path})
        result = reader.read("contract_events", offset=0, level="WARN")
        levels = [ln["level"] for ln in result["lines"]]
        self.assertIn("ERROR", levels)
        self.assertIn("WARN", levels)
        self.assertNotIn("INFO", levels)

    def test_level_filter_info_includes_warn_error(self):
        path = self._make_jsonl([
            json.dumps({"level": "INFO", "msg": "info"}),
            json.dumps({"level": "WARN", "msg": "warn"}),
            json.dumps({"level": "ERROR", "msg": "err"}),
            json.dumps({"level": "DEBUG", "msg": "dbg"}),
        ])
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": path})
        result = reader.read("contract_events", offset=0, level="INFO")
        levels = [ln["level"] for ln in result["lines"]]
        self.assertIn("INFO", levels)
        self.assertIn("WARN", levels)
        self.assertIn("ERROR", levels)
        self.assertNotIn("DEBUG", levels)

    def test_level_alias_warning(self):
        path = self._make_jsonl([
            json.dumps({"level": "WARNING", "msg": "warn"}),
            json.dumps({"level": "CRITICAL", "msg": "crit"}),
        ])
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": path})
        result = reader.read("contract_events", offset=0, level="WARN")
        levels = [ln["level"] for ln in result["lines"]]
        self.assertIn("WARN", levels)
        self.assertIn("ERROR", levels)

    # --- Keyword search -----------------------------------------------

    def test_keyword_search(self):
        path = self._make_jsonl([
            json.dumps({"level": "INFO", "msg": "alpha keyword here"}),
            json.dumps({"level": "INFO", "msg": "beta no match"}),
            json.dumps({"level": "INFO", "msg": "gamma KEYWORD upper"}),
        ])
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": path})
        result = reader.read("contract_events", offset=0, q="keyword")
        self.assertEqual(len(result["lines"]), 2)

    def test_keyword_search_empty_returns_all(self):
        path = self._make_jsonl([
            json.dumps({"level": "INFO", "msg": "line1"}),
            json.dumps({"level": "INFO", "msg": "line2"}),
        ])
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": path})
        result = reader.read("contract_events", offset=0, q="")
        self.assertEqual(len(result["lines"]), 2)

    # --- Privacy scrubbing --------------------------------------------

    def test_privacy_scrub_forbidden_key(self):
        path = self._make_jsonl([
            json.dumps({"level": "INFO", "raw_payload": "secret-data"}),
        ])
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": path})
        result = reader.read("contract_events", offset=0)
        self.assertEqual(len(result["lines"]), 1)
        self.assertIn("[REDACTED", result["lines"][0]["text"])
        self.assertNotIn("secret-data", result["lines"][0]["text"])

    def test_privacy_scrub_clean_jsonl(self):
        path = self._make_jsonl([
            json.dumps({"level": "INFO", "msg": "clean message"}),
        ])
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": path})
        result = reader.read("contract_events", offset=0)
        self.assertIn("clean message", result["lines"][0]["text"])

    def test_privacy_scrub_text_secrets(self):
        path = self._make_text([
            "INFO: connecting with token=my-secret-token-value-123",
        ])
        env = {
            "INKSTATUTE_CONTRACT_LOG_PATH": path,
            "MY_API_TOKEN": "my-secret-token-value-123",
        }
        reader = self._reader(env)
        result = reader.read("contract_events", offset=0)
        self.assertIn("[REDACTED]", result["lines"][0]["text"])
        self.assertNotIn("my-secret-token-value-123", result["lines"][0]["text"])

    # --- Rotation -----------------------------------------------------

    def test_rotation_file_shrink(self):
        path = self._make_jsonl([
            json.dumps({"level": "INFO", "msg": f"line{i}"}) for i in range(5)
        ])
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": path})
        first = reader.read("contract_events", offset=0)
        self.assertEqual(len(first["lines"]), 5)
        # Truncate to 2 lines.
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join([
                json.dumps({"level": "INFO", "msg": "line0"}),
                json.dumps({"level": "INFO", "msg": "line1"}),
            ]) + "\n")
        second = reader.read("contract_events", offset=first["next_offset"], inode=first["inode"])
        self.assertTrue(second["metadata"]["rotated"])
        self.assertEqual(len(second["lines"]), 2)

    def test_rotation_inode_change(self):
        path = self._make_jsonl([
            json.dumps({"level": "INFO", "msg": f"line{i}"}) for i in range(3)
        ])
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": path})
        first = reader.read("contract_events", offset=0)
        old_inode = first["inode"]
        # Delete and recreate.
        os.unlink(path)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"level": "INFO", "msg": "new"}) + "\n")
        second = reader.read("contract_events", offset=first["next_offset"], inode=old_inode)
        self.assertTrue(second["metadata"]["rotated"])
        self.assertEqual(len(second["lines"]), 1)

    # --- Source validation --------------------------------------------

    def test_unknown_source_rejected(self):
        reader = self._reader()
        with self.assertRaises(ValueError):
            reader.read("malicious_source")

    def test_source_not_configured(self):
        reader = self._reader()
        result = reader.read("contract_events")
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "source_not_configured")

    def test_source_not_found(self):
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": "/nonexistent/path/file.jsonl"})
        result = reader.read("contract_events")
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], "source_not_found")

    # --- Max lines ----------------------------------------------------

    def test_max_lines_cap(self):
        path = self._make_jsonl([
            json.dumps({"level": "INFO", "msg": f"line{i}"}) for i in range(10)
        ])
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": path})
        result = reader.read("contract_events", offset=0, max_lines=3)
        self.assertEqual(len(result["lines"]), 3)
        self.assertFalse(result["eof"])

    # --- List sources -------------------------------------------------

    def test_list_sources(self):
        path = self._make_jsonl([json.dumps({"level": "INFO", "msg": "x"})])
        env = {
            "INKSTATUTE_CONTRACT_LOG_PATH": path,
            "INKSTATUTE_RUNTIME_AUDIT_PATH": path,
            "INKSTATUTE_FEEDBACK_QUEUE_PATH": path,
        }
        reader = self._reader(env)
        sources = reader.list_sources()
        self.assertEqual(len(sources), 5)
        names = [s["source"] for s in sources]
        self.assertIn("contract_events", names)
        self.assertIn("runtime_audit", names)
        self.assertIn("feedback", names)
        self.assertIn("wecom_stdout", names)
        self.assertIn("qqbot_stdout", names)
        for s in sources:
            if s["source"] in ("contract_events", "runtime_audit", "feedback"):
                self.assertTrue(s["available"])

    # --- Path traversal -----------------------------------------------

    def test_path_traversal_rejected(self):
        reader = self._reader()
        with self.assertRaises(ValueError):
            reader.read("../etc/passwd")

    def test_path_traversal_compound_rejected(self):
        reader = self._reader()
        with self.assertRaises(ValueError):
            reader.read("contract_events/../../../etc/passwd")

    # --- Edge cases ---------------------------------------------------

    def test_empty_file(self):
        path = Path(tempfile.mktemp(suffix=".jsonl"))
        path.write_text("", encoding="utf-8")
        self.addCleanup(path.unlink)
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": str(path)})
        result = reader.read("contract_events", offset=0)
        self.assertEqual(len(result["lines"]), 0)
        self.assertTrue(result["eof"])
        self.assertEqual(result["next_offset"], 0)

    def test_partial_line(self):
        path = Path(tempfile.mktemp(suffix=".jsonl"))
        path.write_text(json.dumps({"level": "INFO", "msg": "no newline"}), encoding="utf-8")
        self.addCleanup(path.unlink)
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": str(path)})
        result = reader.read("contract_events", offset=0)
        self.assertEqual(len(result["lines"]), 1)
        self.assertEqual(result["next_offset"], os.path.getsize(str(path)))
        self.assertTrue(result["eof"])

    # --- Process supervisor -------------------------------------------

    def test_wecom_stdout_via_process_supervisor(self):
        log_path = self._make_text(["INFO: wecom started"])
        supervisor = MagicMock()
        supervisor.status.return_value = _FakeRecord(log_path=log_path)
        log_dir = str(Path(log_path).parent)
        reader = self._reader({
            "INKSTATUTE_PROCESS_LOG_DIR": log_dir,
        }, process_supervisor=supervisor)
        resolved = reader.resolve_path("wecom_stdout")
        self.assertIsNotNone(resolved)
        result = reader.read("wecom_stdout", offset=0)
        self.assertEqual(len(result["lines"]), 1)
        supervisor.status.assert_called_with("wecom")

    def test_qqbot_stdout_via_process_supervisor(self):
        log_path = self._make_text(["ERROR: qqbot crashed"])
        supervisor = MagicMock()
        supervisor.status.return_value = _FakeRecord(name="qqbot", log_path=log_path)
        log_dir = str(Path(log_path).parent)
        reader = self._reader({
            "INKSTATUTE_PROCESS_LOG_DIR": log_dir,
        }, process_supervisor=supervisor)
        result = reader.read("qqbot_stdout", offset=0)
        self.assertEqual(len(result["lines"]), 1)
        supervisor.status.assert_called_with("qqbot")

    def test_wecom_stdout_fallback_log_dir(self):
        # No process supervisor — should fall back to log_dir / wecom-host.log
        log_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(str(log_dir)))
        log_file = log_dir / "wecom-host.log"
        log_file.write_text("INFO: fallback\n", encoding="utf-8")
        reader = self._reader({"INKSTATUTE_PROCESS_LOG_DIR": str(log_dir)})
        result = reader.read("wecom_stdout", offset=0)
        self.assertEqual(len(result["lines"]), 1)

    # --- No full-file read --------------------------------------------

    def test_no_full_file_read(self):
        lines = [json.dumps({"level": "INFO", "msg": f"line{i}"}) for i in range(10000)]
        path = Path(tempfile.mktemp(suffix=".jsonl"))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.addCleanup(path.unlink)
        reader = self._reader({"INKSTATUTE_CONTRACT_LOG_PATH": str(path)})
        result = reader.read("contract_events", offset=0, max_lines=10)
        self.assertEqual(len(result["lines"]), 10)
        self.assertLess(result["next_offset"], os.path.getsize(str(path)))
        self.assertFalse(result["eof"])


if __name__ == "__main__":
    unittest.main()
