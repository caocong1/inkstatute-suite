"""Tests for gate status via subprocess isolation (SC3)."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from admin_console_api.gates import GATE_TIMEOUT_SECONDS, handle_gates, run_gate_summary


class GateSubprocessTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("RUN_GATE_SUBPROCESS_TESTS"), "gate subprocess test skipped (set RUN_GATE_SUBPROCESS_TESTS=1 to enable)")
    def test_run_gate_summary_returns_parsed_json(self) -> None:
        result = run_gate_summary()
        self.assertIsInstance(result, dict)
        self.assertIn("passed", result)
        self.assertIsInstance(result["passed"], bool)
        self.assertIn("gates", result)
        self.assertIsInstance(result["gates"], list)

    def test_run_gate_summary_timeout_handling(self) -> None:
        with patch("admin_console_api.gates.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=1)):
            result = run_gate_summary()
        self.assertEqual(result, {"passed": False, "gates": [], "error": "timeout"})

    def test_run_gate_summary_parse_error_handling(self) -> None:
        fake_completed = subprocess.CompletedProcess(
            args=["x"], returncode=0, stdout="not json", stderr="",
        )
        with patch("admin_console_api.gates.subprocess.run", return_value=fake_completed):
            result = run_gate_summary()
        self.assertEqual(result, {"passed": False, "gates": [], "error": "parse_error"})

    def test_run_gate_summary_uses_subprocess_not_import(self) -> None:
        """Verify no gate-internal modules are loaded in the current process."""
        gate_internal_prefixes = (
            "contract_test_suite",
            "platform_contract",
            "run_v2_gates",
        )
        before = set(sys.modules.keys())
        # Mock subprocess.run so no real subprocess is spawned, but the call path
        # is exercised.  No gate modules should be imported in this process.
        fake_completed = subprocess.CompletedProcess(
            args=["x"], returncode=0, stdout='{"passed": true, "gates": []}', stderr="",
        )
        with patch("admin_console_api.gates.subprocess.run", return_value=fake_completed):
            run_gate_summary()
        after = set(sys.modules.keys())
        new_modules = after - before
        for mod in new_modules:
            for prefix in gate_internal_prefixes:
                self.assertFalse(
                    mod.startswith(prefix),
                    f"gate-internal module {mod!r} was imported in-process",
                )

    def test_run_gate_summary_captures_output(self) -> None:
        fake_completed = subprocess.CompletedProcess(
            args=["x"], returncode=0, stdout='{"passed": true, "gates": []}', stderr="",
        )
        with patch("admin_console_api.gates.subprocess.run", return_value=fake_completed) as mock_run:
            result = run_gate_summary()
        call_kwargs = mock_run.call_args.kwargs
        self.assertTrue(call_kwargs.get("capture_output", False))
        # Raw stdout/stderr must not appear in the returned dict.
        self.assertNotIn("stdout", result)
        self.assertNotIn("stderr", result)

    def test_gate_timeout_is_300_seconds(self) -> None:
        self.assertEqual(GATE_TIMEOUT_SECONDS, 300)


class HandleGatesTests(unittest.TestCase):
    def test_handle_gates_returns_200(self) -> None:
        with patch("admin_console_api.gates.run_gate_summary", return_value={
            "passed": True, "gates": [{"name": "platform-contract", "exit_code": 0}],
        }):
            status, body = handle_gates()
        self.assertEqual(status, 200)

    def test_handle_gates_response_shape(self) -> None:
        with patch("admin_console_api.gates.run_gate_summary", return_value={
            "passed": True,
            "gates": [
                {"name": "g1", "exit_code": 0},
                {"name": "g2", "exit_code": 0},
            ],
        }):
            status, body = handle_gates()
        self.assertIs(body["passed"], True)
        self.assertEqual(body["gate_count"], 2)
        self.assertEqual(body["gates_passed"], 2)
        self.assertEqual(body["gates_failed"], 0)
        self.assertEqual(body["metadata"]["source"], "subprocess:run_v2_gates.py")
        self.assertIs(body["metadata"]["read_only"], True)

    def test_handle_gates_with_failed_gate(self) -> None:
        with patch("admin_console_api.gates.run_gate_summary", return_value={
            "passed": False,
            "gates": [
                {"name": "g1", "exit_code": 0},
                {"name": "g2", "exit_code": 1},
            ],
        }):
            status, body = handle_gates()
        self.assertIs(body["passed"], False)
        self.assertEqual(body["gates_passed"], 1)
        self.assertEqual(body["gates_failed"], 1)

    def test_handle_gates_with_error(self) -> None:
        with patch("admin_console_api.gates.run_gate_summary", return_value={
            "passed": False, "gates": [], "error": "timeout",
        }):
            status, body = handle_gates()
        self.assertIs(body["passed"], False)
        self.assertEqual(body["metadata"]["error"], "timeout")

    def test_handle_gates_does_not_expose_raw_stdout(self) -> None:
        with patch("admin_console_api.gates.run_gate_summary", return_value={
            "passed": True, "gates": [{"name": "g1", "exit_code": 0}],
        }):
            status, body = handle_gates()
        self.assertNotIn("stdout", body)
        self.assertNotIn("stderr", body)


if __name__ == "__main__":
    unittest.main()
