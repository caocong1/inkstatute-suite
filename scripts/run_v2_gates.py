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
    skill_registry_src = repo_root / "packages" / "skill-registry" / "src"
    router_service_src = repo_root / "packages" / "router-service" / "src"
    codex_backend_src = repo_root / "packages" / "backends" / "codex" / "src"
    provider_model_backend_src = repo_root / "packages" / "backends" / "provider_model" / "src"
    admin_api_src = repo_root / "services" / "admin-console-api" / "src"
    rbac_src = repo_root / "packages" / "rbac" / "src"
    channel_core_src = repo_root / "packages" / "channel-core" / "src"
    qqbot_src = repo_root / "packages" / "channels" / "qqbot" / "src"
    qqbot_service_src = repo_root / "services" / "qqbot-service" / "src"
    web_sse_src = repo_root / "packages" / "channels" / "web_sse" / "src"
    wecom_channel_src = repo_root / "packages" / "channels" / "wecom" / "src"
    mcp_registry_src = repo_root / "packages" / "mcp-registry" / "src"
    sdk_ts_src = repo_root / "packages" / "platform-sdk-ts" / "src"
    model_gateway_src = repo_root / "packages" / "model-gateway" / "src"
    multi_agent_src = repo_root / "packages" / "multi-agent-adapter" / "src"
    admin_web_ui_src = repo_root / "services" / "admin-web-ui" / "src"
    lawyer_web_chat_src = repo_root / "services" / "lawyer-web-chat" / "src"
    operator_config_src = repo_root / "packages" / "operator-config" / "src"

    return (
        Gate(
            "platform-contract",
            (py, "-m", "unittest", "discover", "-s", "packages/platform-contract/tests"),
            (platform_src,),
        ),
        Gate(
            "wecom-service",
            (py, "-m", "unittest", "discover", "-s", "services/wecom-service/tests"),
            (wecom_src, channel_core_src, platform_src, contract_src, platform_runtime_src),
        ),
        Gate(
            "hermes-contract-layer",
            (py, "-m", "unittest", "discover", "-s", "services/hermes-contract-layer/tests"),
            (hermes_src, platform_src, contract_src, router_service_src, skill_registry_src),
        ),
        Gate(
            "conversation-read-view",
            (py, "-m", "unittest", "discover", "services/conversation-read-view/tests"),
            (read_view_src, feedback_src, contract_src, platform_src, platform_runtime_src),
        ),
        Gate(
            "skill-registry",
            (py, "-m", "unittest", "discover", "-s", "packages/skill-registry/tests"),
            (skill_registry_src, platform_src, platform_runtime_src, rbac_src),
        ),
        Gate(
            "operator-config",
            (py, "-m", "unittest", "discover", "-s", "packages/operator-config/tests"),
            (operator_config_src, platform_runtime_src),
        ),
        Gate(
            "router-service",
            (py, "-m", "unittest", "discover", "-s", "packages/router-service/tests"),
            (router_service_src, platform_src, skill_registry_src, mcp_registry_src),
        ),
        Gate(
            "mcp-registry",
            (py, "-m", "unittest", "discover", "-s", "packages/mcp-registry/tests"),
            (mcp_registry_src, platform_src, platform_runtime_src),
        ),
        Gate(
            "codex-backend",
            (py, "-m", "unittest", "discover", "-s", "packages/backends/codex/tests"),
            (codex_backend_src, platform_src, platform_runtime_src, wecom_src, channel_core_src),
        ),
        Gate(
            "provider-model-backend",
            (py, "-m", "unittest", "discover", "-s", "packages/backends/provider_model/tests"),
            (provider_model_backend_src, platform_src, platform_runtime_src, wecom_src, channel_core_src),
        ),
        Gate(
            "model-gateway",
            (py, "-m", "unittest", "discover", "-s", "packages/model-gateway/tests"),
            (model_gateway_src, platform_src, platform_runtime_src),
        ),
        Gate(
            "multi-agent-adapter",
            (py, "-m", "unittest", "discover", "-s", "packages/multi-agent-adapter/tests"),
            (multi_agent_src, platform_src, platform_runtime_src),
        ),
        Gate(
            "admin-console-api",
            (py, "-m", "unittest", "discover", "-s", "services/admin-console-api/tests"),
            (admin_api_src, rbac_src, read_view_src, feedback_src, contract_src, platform_src, platform_runtime_src, operator_config_src),
        ),
        Gate(
            "admin-web-ui",
            (py, "-m", "unittest", "discover", "-s", "services/admin-web-ui/tests"),
            (admin_web_ui_src, admin_api_src, rbac_src, read_view_src, feedback_src, contract_src, platform_src, platform_runtime_src, operator_config_src),
        ),
        Gate(
            "lawyer-web-chat",
            (py, "-m", "unittest", "discover", "-s", "services/lawyer-web-chat/tests"),
            (lawyer_web_chat_src, rbac_src, web_sse_src, channel_core_src, contract_src, platform_src, platform_runtime_src),
        ),
        Gate(
            "rbac",
            (py, "-m", "unittest", "discover", "-s", "packages/rbac/tests"),
            (rbac_src, admin_api_src, platform_src, platform_runtime_src, read_view_src, feedback_src, contract_src, operator_config_src),
        ),
        Gate(
            "rbac-annotation-scan",
            (py, "scripts/scan_rbac_annotations.py"),
            (rbac_src, admin_api_src, read_view_src, feedback_src, contract_src, platform_src, platform_runtime_src, operator_config_src),
        ),
        Gate(
            "qqbot-channel",
            (py, "-m", "unittest", "discover", "-s", "packages/channels/qqbot/tests"),
            # feedback_src: Phase 66 e2e tests import feedback_service.queue (not a new gate).
            (qqbot_src, channel_core_src, platform_src, contract_src, platform_runtime_src, feedback_src),
        ),
        Gate(
            "qqbot-service",
            (py, "-m", "unittest", "discover", "-s", "services/qqbot-service/tests"),
            (qqbot_service_src, qqbot_src, channel_core_src, platform_src, contract_src, platform_runtime_src, feedback_src),
        ),
        Gate(
            "web-sse-channel",
            (py, "-m", "unittest", "discover", "-s", "packages/channels/web_sse/tests"),
            (web_sse_src, channel_core_src, platform_src, contract_src, platform_runtime_src),
        ),
        Gate(
            "wecom-channel",
            (py, "-m", "unittest", "discover", "-s", "packages/channels/wecom/tests"),
            (wecom_channel_src, channel_core_src, platform_src, contract_src, platform_runtime_src, wecom_src),
        ),
        Gate(
            "platform-sdk-ts",
            (py, "-m", "unittest", "discover", "-s", "packages/platform-sdk-ts/tests"),
            (sdk_ts_src, platform_src, contract_src, platform_runtime_src),
        ),
        Gate(
            "feedback-service",
            (py, "-m", "unittest", "discover", "services/feedback-service/tests"),
            (feedback_src, wecom_src, channel_core_src, contract_src, platform_src, platform_runtime_src),
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
            (contract_src, platform_src, platform_runtime_src, wecom_src, hermes_src, hermes_backend_src, read_view_src, feedback_src, solution_loader_src, lawfirm_solution_src, demo_non_legal_solution_src, skill_registry_src, router_service_src, codex_backend_src, provider_model_backend_src, admin_api_src, rbac_src, channel_core_src, qqbot_src, qqbot_service_src, mcp_registry_src, model_gateway_src),
        ),
        Gate(
            "v2-acceptance-traceability",
            (py, "scripts/audit_v2_requirements.py", "--check-gaps"),
        ),
        Gate(
            "gate-coverage-meta-test",
            (py, "-m", "unittest", "packages/contract-test-suite/tests/test_gate_coverage.py"),
            (contract_src, platform_src),
        ),
        Gate(
            "compileall",
            (
                py,
                "-m",
                "compileall",
                "packages/platform-contract/src",
                "packages/contract-test-suite/src",
                "packages/platform-runtime/src",
                "packages/operator-config/src",
                "packages/skill-registry/src",
                "packages/router-service/src",
                "packages/mcp-registry/src",
                "packages/rbac/src",
                "packages/backends/codex/src",
                "packages/backends/provider_model/src",
                "packages/model-gateway/src",
                "packages/multi-agent-adapter/src",
                "services/admin-web-ui/src",
                "services/lawyer-web-chat/src",
                "services/wecom-service/src",
                "services/hermes-contract-layer/src",
                "services/feedback-service/src",
                "services/conversation-read-view/src",
                "services/admin-console-api/src",
                "packages/channel-core/src",
                "packages/channels/qqbot/src",
                "services/qqbot-service/src",
                "packages/backends/hermes/src",
                "packages/solution-loader/src",
                "solutions/lawfirm/src",
                "solutions/demo_non_legal/src",
                "scripts/run_v2_gates.py",
                "scripts/audit_v2_requirements.py",
                "scripts/generate_gap_evidence_reports.py",
                "scripts/generate_v2_readiness_report.py",
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
