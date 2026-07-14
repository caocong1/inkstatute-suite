"""Tests for scripts/start-console.sh (POLISH-04).

Verifies the startup script has env loading, both service launches,
JSON PID file, and trap cleanup.
"""

from __future__ import annotations

import unittest
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "start-console.sh"


class TestStartupScript(unittest.TestCase):
    """Validate start-console.sh structure and required patterns."""

    def setUp(self) -> None:
        self.assertTrue(_SCRIPT_PATH.is_file(), f"Missing script: {_SCRIPT_PATH}")
        self.content = _SCRIPT_PATH.read_text(encoding="utf-8")

    def test_script_has_set_euo_pipefail(self) -> None:
        """Script must start with set -euo pipefail for strict error handling."""
        self.assertIn("set -euo pipefail", self.content)

    def test_script_sources_env(self) -> None:
        """Script must source the env file with set -a / set +a bracketing."""
        self.assertIn("source", self.content)
        self.assertIn("set -a", self.content)
        self.assertIn("set +a", self.content)

    def test_script_launches_both_services(self) -> None:
        """Script must launch admin_web_ui and admin_console_api."""
        self.assertIn("admin_web_ui", self.content)
        self.assertIn("admin_console_api", self.content)

    def test_script_writes_pid_file(self) -> None:
        """Script must write a JSON PID file to ~/.inkstatute/console-pids.json."""
        self.assertIn("console-pids.json", self.content)
        self.assertIn(".inkstatute", self.content)

    def test_script_has_trap_cleanup(self) -> None:
        """Script must have a trap that kills child processes on exit."""
        self.assertIn("trap", self.content)
        self.assertIn("kill", self.content)


if __name__ == "__main__":
    unittest.main()
