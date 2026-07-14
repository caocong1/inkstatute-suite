"""Gate status views via subprocess isolation (SC3).

Runs ``scripts/run_v2_gates.py --json-summary`` via ``subprocess.run`` — no
gate internals are imported in the admin-console-api process.  The subprocess
loads gate modules in a separate process, keeping the admin API decoupled from
gate implementation details.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

GATE_SCRIPT = "scripts/run_v2_gates.py"
GATE_TIMEOUT_SECONDS = 300


def _repo_root() -> Path:
    """Return the repository root (4 parents up from this module)."""

    return Path(__file__).resolve().parents[4]


def _count_gates(gates: list[dict[str, Any]], exit_code: int) -> int:
    """Count gates whose ``exit_code`` matches the given value."""

    return sum(1 for g in gates if g.get("exit_code") == exit_code)


def run_gate_summary(
    repo_root: str | Path | None = None,
    *,
    timeout_seconds: int = GATE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run ``run_v2_gates.py --json-summary`` via subprocess and parse output.

    Returns a dict with ``passed`` (bool) and ``gates`` (list).  On timeout or
    JSON parse failure, returns an error dict — never raises.
    ``timeout_seconds`` overrides the default 300s ceiling (e.g. for the
    unified health endpoint which uses a shorter 30s timeout).
    """

    root = Path(repo_root) if repo_root is not None else _repo_root()
    script = root / GATE_SCRIPT

    try:
        completed = subprocess.run(
            [sys.executable, str(script), "--json-summary"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(root),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"passed": False, "gates": [], "error": "timeout"}

    try:
        summary = json.loads(completed.stdout)
    except (json.JSONDecodeError, ValueError):
        return {"passed": False, "gates": [], "error": "parse_error"}

    return summary


def handle_gates(repo_root: str | Path | None = None) -> tuple[int, dict[str, Any]]:
    """Return a 200 response with the gate summary from subprocess.

    Raw stdout/stderr from the subprocess is never exposed in the response.
    """

    summary = run_gate_summary(repo_root)
    gates = summary.get("gates", [])
    metadata: dict[str, Any] = {
        "source": "subprocess:run_v2_gates.py",
        "read_only": True,
        "admin_api": True,
    }
    if "error" in summary:
        metadata["error"] = summary["error"]

    return 200, {
        "passed": summary.get("passed", False),
        "gate_count": len(gates),
        "gates_passed": _count_gates(gates, 0),
        "gates_failed": len(gates) - _count_gates(gates, 0),
        "gates": gates,
        "metadata": metadata,
    }


__all__ = ["run_gate_summary", "handle_gates", "GATE_TIMEOUT_SECONDS"]
