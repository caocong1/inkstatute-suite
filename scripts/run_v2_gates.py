#!/usr/bin/env python3
"""Run InkStatute V2 local gates from the repository root."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Gate:
    name: str
    command: tuple[str, ...]
    pythonpath: tuple[str, ...] = ()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run InkStatute V2 contract gates.")
    parser.add_argument("--list", action="store_true", help="List gate names and exit.")
    parser.add_argument("--json-summary", action="store_true", help="Print a sanitized JSON gate summary.")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    gates = _gates(repo_root)
    if args.list:
        for gate in gates:
            print(gate.name)
        return 0

    results: list[dict[str, object]] = []
    for gate in gates:
        exit_code = _run_gate(repo_root, gate)
        results.append({"name": gate.name, "exit_code": exit_code})
        if exit_code != 0:
            if args.json_summary:
                print(json.dumps({"passed": False, "gates": results}, indent=2, sort_keys=True))
            return exit_code

    if args.json_summary:
        print(json.dumps({"passed": True, "gates": results}, indent=2, sort_keys=True))
    return 0


def _gates(repo_root: Path) -> tuple[Gate, ...]:
    py = sys.executable
    platform_src = repo_root / "packages" / "platform-contract" / "src"
    contract_src = repo_root / "packages" / "contract-test-suite" / "src"
    wecom_src = repo_root / "services" / "wecom-service" / "src"
    hermes_src = repo_root / "services" / "hermes-contract-layer" / "src"
    feedback_src = repo_root / "services" / "feedback-service" / "src"
    read_view_src = repo_root / "services" / "conversation-read-view" / "src"
    hermes_backend_src = repo_root / "packages" / "backends" / "hermes" / "src"
    platform_runtime_src = repo_root / "packages" / "platform-runtime" / "src"
    solution_loader_src = repo_root / "packages" / "solution-loader" / "src"
    lawfirm_solution_src = repo_root / "solutions" / "lawfirm" / "src"
    demo_non_legal_solution_src = repo_root / "solutions" / "demo_non_legal" / "src"

    return (
        Gate(
            "platform-contract",
            (py, "-m", "unittest", "discover", "-s", "packages/platform-contract/tests"),
            (platform_src,),
        ),
        Gate(
            "wecom-service",
            (py, "-m", "unittest", "discover", "-s", "services/wecom-service/tests"),
            (wecom_src, platform_src, contract_src),
        ),
        Gate(
            "hermes-contract-layer",
            (py, "-m", "unittest", "discover", "-s", "services/hermes-contract-layer/tests"),
            (hermes_src, platform_src, contract_src),
        ),
        Gate(
            "conversation-read-view",
            (py, "-m", "unittest", "discover", "services/conversation-read-view/tests"),
            (read_view_src, feedback_src, contract_src),
        ),
        Gate(
            "feedback-service",
            (py, "-m", "unittest", "discover", "services/feedback-service/tests"),
            (feedback_src, wecom_src, contract_src),
        ),
        Gate(
            "phase7-privacy-boundary",
            (
                py,
                "-m",
                "unittest",
                "packages/contract-test-suite/tests/test_privacy_gates.py",
                "packages/contract-test-suite/tests/test_thin_layer_boundaries.py",
            ),
            (contract_src, platform_src),
        ),
        Gate(
            "contract-test-suite",
            (py, "-m", "unittest", "discover", "-s", "packages/contract-test-suite/tests"),
            (contract_src, platform_src, platform_runtime_src, wecom_src, hermes_src, hermes_backend_src, read_view_src, feedback_src, solution_loader_src, lawfirm_solution_src, demo_non_legal_solution_src),
        ),
        Gate(
            "compileall",
            (
                py,
                "-m",
                "compileall",
                "packages/platform-contract/src",
                "packages/contract-test-suite/src",
                "services/wecom-service/src",
                "services/hermes-contract-layer/src",
                "services/feedback-service/src",
                "services/conversation-read-view/src",
                "scripts/run_v2_gates.py",
            ),
        ),
    )


def _run_gate(repo_root: Path, gate: Gate) -> int:
    print(f"==> {gate.name}", flush=True)
    env = os.environ.copy()
    if gate.pythonpath:
        paths = [str(path) for path in gate.pythonpath]
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = os.pathsep.join(paths + ([existing] if existing else []))
    completed = subprocess.run(gate.command, cwd=repo_root, env=env, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
