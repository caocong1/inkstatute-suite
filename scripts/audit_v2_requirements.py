#!/usr/bin/env python3
"""Deterministic V2 requirement audit and traceability matrix generator.

Modes:
  (default)            Print traceability matrix to stdout.
  --json               Write acceptance/v2-traceability.json sidecar.
  --check-gaps         Exit non-zero if any requirement is classified as gap.
  --requirement REQ_ID Print detailed evidence bundle for a single requirement.

The audit reads codebase structure but does NOT re-run tests or gates.
Gate-passing is proven by scripts/run_v2_gates.py; this script proves
traceability and catches the MEM-07/MEM-16 false-positive pattern where
infrastructure is present but production wiring is missing.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR_REL = "packages/platform-contract/src/platform_contract/schemas"
FIXTURE_DIR_RELS = [
    "packages/contract-test-suite/fixtures",
    "packages/platform-contract/fixtures",
]
SIDECAR_REL = "acceptance/v2-traceability.json"
GENERATED_AT_PLACEHOLDER = "deterministic"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerificationProbe:
    """A single verification probe at one of three levels.

    level: 1 (schema), 2 (library surface), 3 (production wiring)
    kind:  "schema", "library", or "wiring"
    target: human-readable description of what is being probed
    checker: callable(repo_root: Path) -> (passed: bool, evidence: str)
    """

    level: int
    kind: str
    target: str
    checker: Callable[[Path], tuple[bool, str]]


@dataclass(frozen=True)
class EvidenceHints:
    """Hints that guide the evidence collector for a requirement."""

    source_dirs: tuple[str, ...] = ()
    test_patterns: tuple[str, ...] = ()
    schema_names: tuple[str, ...] = ()
    fixture_patterns: tuple[str, ...] = ()
    gate_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class RequirementSpec:
    """A single V2 Active requirement with probes and evidence hints."""

    req_id: str
    description: str
    prd_section: str
    human_gate: bool
    probes: tuple[VerificationProbe, ...]
    evidence_hints: EvidenceHints


# ---------------------------------------------------------------------------
# Checker factories
# ---------------------------------------------------------------------------


def _check_schemas_exist(
    schema_names: tuple[str, ...],
) -> Callable[[Path], tuple[bool, str]]:
    """Level 1: verify schema files exist in the platform-contract schema dir."""

    def checker(repo_root: Path) -> tuple[bool, str]:
        schema_dir = repo_root / SCHEMA_DIR_REL
        missing = sorted(
            name for name in schema_names if not (schema_dir / name).exists()
        )
        if missing:
            return False, f"missing schema files: {', '.join(missing)}"
        return True, f"schema files exist: {', '.join(sorted(schema_names))}"

    return checker


def _check_no_schema() -> Callable[[Path], tuple[bool, str]]:
    """Level 1: pass for requirements that have no schema requirement."""

    def checker(_repo_root: Path) -> tuple[bool, str]:
        return True, "no schema requirement for this requirement"

    return checker


def _check_library_surface(
    source_rel: str,
    expected_names: tuple[str, ...],
) -> Callable[[Path], tuple[bool, str]]:
    """Level 2: use ast.parse to verify a source file contains expected names."""

    def checker(repo_root: Path) -> tuple[bool, str]:
        path = repo_root / source_rel
        if not path.exists():
            return False, f"{source_rel} does not exist"
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            return False, f"{source_rel} syntax error: {exc}"
        found_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                found_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        found_names.add(target.id)
        missing = sorted(name for name in expected_names if name not in found_names)
        if missing:
            return False, f"{source_rel} missing expected names: {', '.join(missing)}"
        return True, f"{source_rel}: {', '.join(sorted(expected_names))} found"

    return checker


def _check_files_exist(
    rel_paths: tuple[str, ...],
) -> Callable[[Path], tuple[bool, str]]:
    """Level 2 helper: verify that a set of files exist on disk."""

    def checker(repo_root: Path) -> tuple[bool, str]:
        missing = sorted(
            rel for rel in rel_paths if not (repo_root / rel).exists()
        )
        if missing:
            return False, f"missing files: {', '.join(missing)}"
        return True, f"files exist: {', '.join(sorted(rel_paths))}"

    return checker


def _check_wiring_all(
    wiring_file: str,
    patterns: tuple[str, ...],
) -> Callable[[Path], tuple[bool, str]]:
    """Level 3: verify that ALL regex patterns are found in a production file."""

    def checker(repo_root: Path) -> tuple[bool, str]:
        path = repo_root / wiring_file
        if not path.exists():
            return False, f"{wiring_file} does not exist"
        text = path.read_text(encoding="utf-8")
        missing = sorted(
            pattern for pattern in patterns if not re.search(pattern, text)
        )
        if missing:
            return False, f"{wiring_file} missing wiring patterns: {', '.join(missing)}"
        return True, f"{wiring_file} wiring patterns found: {', '.join(patterns)}"

    return checker


def _check_wiring_any(
    wiring_file: str,
    patterns: tuple[str, ...],
) -> Callable[[Path], tuple[bool, str]]:
    """Level 3: verify that at least one regex pattern is found in a production file."""

    def checker(repo_root: Path) -> tuple[bool, str]:
        path = repo_root / wiring_file
        if not path.exists():
            return False, f"{wiring_file} does not exist"
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            if re.search(pattern, text):
                return True, f"{wiring_file} wiring pattern found: {pattern}"
        return False, f"{wiring_file} missing all wiring patterns: {', '.join(patterns)}"

    return checker


# ---------------------------------------------------------------------------
# Requirement Registry — 10 unchecked V2 Active requirements
# (PROJECT.md lines 43-52)
# ---------------------------------------------------------------------------

WECOM_SRC = "services/wecom-service/src/wecom_service"
HERMES_SRC = "services/hermes-contract-layer/src/hermes_contract_layer"
FEEDBACK_SRC = "services/feedback-service/src/feedback_service"
READVIEW_SRC = "services/conversation-read-view/src/conversation_read_view"
CONTRACT_SUITE_SRC = "packages/contract-test-suite/src/contract_test_suite"

REQUIREMENT_REGISTRY: tuple[RequirementSpec, ...] = (
    # 1. WeCom service
    RequirementSpec(
        req_id="WECOM-01",
        description=(
            "Build InkStatute-owned WeCom service for receive/send, ACK, "
            "message normalization, text/file/card delivery, feedback "
            "callbacks, idempotency, retry, and output policy."
        ),
        prd_section="10.2",
        human_gate=False,
        probes=(
            VerificationProbe(
                level=1,
                kind="schema",
                target="channel_message and channel_delivery schemas exist",
                checker=_check_schemas_exist(
                    ("channel_message.schema.json", "channel_delivery.schema.json")
                ),
            ),
            VerificationProbe(
                level=2,
                kind="library",
                target="wecom_service core modules with expected classes/functions",
                checker=_check_library_surface(
                    f"{WECOM_SRC}/ingress_runtime.py",
                    ("WeComRuntimeIngress",),
                ),
            ),
            VerificationProbe(
                level=3,
                kind="wiring",
                target="ingress_runtime.py imports normalization, session_runtime, active_task_router",
                checker=_check_wiring_all(
                    f"{WECOM_SRC}/ingress_runtime.py",
                    (
                        r"from\s+\.normalization\s+import",
                        r"from\s+\.session_runtime\s+import",
                        r"from\s+\.active_task_router\s+import",
                    ),
                ),
            ),
        ),
        evidence_hints=EvidenceHints(
            source_dirs=(WECOM_SRC,),
            test_patterns=(
                r"test_ingress_runtime",
                r"test_normalization",
                r"test_protocol",
                r"test_delivery_guard",
                r"test_session",
                r"test_task_flow",
                r"test_active_task_router",
                r"test_runtime_audit",
            ),
            schema_names=("channel_message.schema.json", "channel_delivery.schema.json"),
            fixture_patterns=(r"phase5_wecom", r"phase55_wecom"),
            gate_names=("wecom-service",),
        ),
    ),
    # 2. Agent adapter contract
    RequirementSpec(
        req_id="ADAPTER-01",
        description=(
            "Define and implement the agent backend adapter contract and "
            "runtime selector, with Hermes as the first supported mode and "
            "Codex/provider-model modes preserved as contract-compatible "
            "future modes."
        ),
        prd_section="10.2",
        human_gate=False,
        probes=(
            VerificationProbe(
                level=1,
                kind="schema",
                target="agent_adapter_manifest schema exists",
                checker=_check_schemas_exist(("agent_adapter_manifest.schema.json",)),
            ),
            VerificationProbe(
                level=2,
                kind="library",
                target="agent_backend.py and adapter_manifest.py with expected names",
                checker=_check_library_surface(
                    f"{WECOM_SRC}/agent_backend.py",
                    ("select_agent_backend", "AgentBackendSelection"),
                ),
            ),
            VerificationProbe(
                level=3,
                kind="wiring",
                target="agent_backend.py imports from platform_contract.agent_adapter",
                checker=_check_wiring_all(
                    f"{WECOM_SRC}/agent_backend.py",
                    (r"from\s+platform_contract\.agent_adapter\s+import",),
                ),
            ),
        ),
        evidence_hints=EvidenceHints(
            source_dirs=(WECOM_SRC, HERMES_SRC),
            test_patterns=(r"test_agent_backend",),
            schema_names=("agent_adapter_manifest.schema.json",),
            fixture_patterns=(r"phase55_non_hermes_adapter_manifest",),
            gate_names=("wecom-service", "contract-test-suite"),
        ),
    ),
    # 3. Hermes bootstrap
    RequirementSpec(
        req_id="HERMES-01",
        description=(
            "Build a reproducible Hermes agent adapter bootstrap path from a "
            "sanitized lawfirm profile bundle, version/capability matrix, "
            "external secrets/env, and health checks."
        ),
        prd_section="10.4",
        human_gate=False,
        probes=(
            VerificationProbe(
                level=1,
                kind="schema",
                target="agent_adapter_manifest schema exists",
                checker=_check_schemas_exist(("agent_adapter_manifest.schema.json",)),
            ),
            VerificationProbe(
                level=2,
                kind="library",
                target="bootstrap.py with probe_hermes_capabilities and check_sanitized_bundle_manifest",
                checker=_check_library_surface(
                    f"{HERMES_SRC}/bootstrap.py",
                    ("probe_hermes_capabilities", "check_sanitized_bundle_manifest"),
                ),
            ),
            VerificationProbe(
                level=3,
                kind="wiring",
                target="hermes_contract_layer __init__.py exports bootstrap health-check functions",
                checker=_check_wiring_all(
                    f"{HERMES_SRC}/__init__.py",
                    (r"probe_hermes_capabilities", r"check_sanitized_bundle_manifest"),
                ),
            ),
        ),
        evidence_hints=EvidenceHints(
            source_dirs=(HERMES_SRC,),
            test_patterns=(r"test_adapter_bootstrap",),
            schema_names=("agent_adapter_manifest.schema.json",),
            fixture_patterns=(),
            gate_names=("hermes-contract-layer",),
        ),
    ),
    # 4. Output boundary
    RequirementSpec(
        req_id="OUTPUT-01",
        description=(
            "Add an assistant output boundary so ordinary WeCom users see "
            "only InkStatute lawyer-assistant output, not Hermes "
            "gateway/update/command/meta notices."
        ),
        prd_section="10.2",
        human_gate=False,
        probes=(
            VerificationProbe(
                level=1,
                kind="schema",
                target="no schema requirement for output boundary",
                checker=_check_no_schema(),
            ),
            VerificationProbe(
                level=2,
                kind="library",
                target="output_policy.py and owned_notices.py with expected names",
                checker=_check_library_surface(
                    f"{WECOM_SRC}/output_policy.py",
                    ("apply_output_policy", "OutputPolicyDecision"),
                ),
            ),
            VerificationProbe(
                level=3,
                kind="wiring",
                target="sender.py imports and calls apply_output_policy",
                checker=_check_wiring_all(
                    f"{WECOM_SRC}/sender.py",
                    (
                        r"from\s+\.output_policy\s+import",
                        r"apply_output_policy",
                    ),
                ),
            ),
        ),
        evidence_hints=EvidenceHints(
            source_dirs=(WECOM_SRC,),
            test_patterns=(r"test_output_policy",),
            schema_names=(),
            fixture_patterns=(r"phase55_output_policy_cases",),
            gate_names=("wecom-service", "contract-test-suite"),
        ),
    ),
    # 5. WeCom loop validation
    RequirementSpec(
        req_id="LOOP-01",
        description=(
            "Preserve and validate the WeCom task-to-agent-to-reply-to-card-"
            "to-feedback loop through InkStatute WeCom service."
        ),
        prd_section="10.2",
        human_gate=False,
        probes=(
            VerificationProbe(
                level=1,
                kind="schema",
                target="feedback_event, agent_turn, agent_result schemas exist",
                checker=_check_schemas_exist(
                    (
                        "feedback_event.schema.json",
                        "agent_turn.schema.json",
                        "agent_result.schema.json",
                    )
                ),
            ),
            VerificationProbe(
                level=2,
                kind="library",
                target="task_flow.py and active_task_router.py with expected names",
                checker=_check_library_surface(
                    f"{WECOM_SRC}/active_task_router.py",
                    ("route_active_task_turn", "ActiveTaskRoutingDecision"),
                ),
            ),
            VerificationProbe(
                level=3,
                kind="wiring",
                target="session_runtime.py imports route_active_task_turn",
                checker=_check_wiring_all(
                    f"{WECOM_SRC}/session_runtime.py",
                    (
                        r"from\s+\.active_task_router\s+import",
                        r"route_active_task_turn",
                    ),
                ),
            ),
        ),
        evidence_hints=EvidenceHints(
            source_dirs=(WECOM_SRC,),
            test_patterns=(
                r"test_task_flow",
                r"test_phase5_wecom_loop",
                r"test_phase55_wecom_service_loop",
            ),
            schema_names=(
                "feedback_event.schema.json",
                "agent_turn.schema.json",
                "agent_result.schema.json",
            ),
            fixture_patterns=(
                r"phase5_wecom_contract_stream",
                r"phase5_wecom_feedback_loop",
                r"phase55_wecom_service_agent_loop",
            ),
            gate_names=("wecom-service", "contract-test-suite"),
        ),
    ),
    # 6. Feedback normalization
    RequirementSpec(
        req_id="FEEDBACK-01",
        description=(
            "Normalize Hermes feedback into FeedbackEvent records with "
            "dedupe, classification, and human-reviewed skill candidates."
        ),
        prd_section="10.2",
        human_gate=False,
        probes=(
            VerificationProbe(
                level=1,
                kind="schema",
                target="feedback_event schema exists",
                checker=_check_schemas_exist(("feedback_event.schema.json",)),
            ),
            VerificationProbe(
                level=2,
                kind="library",
                target="wecom_normalizer.py, classification.py, queue.py with expected names",
                checker=_check_library_surface(
                    f"{FEEDBACK_SRC}/wecom_normalizer.py",
                    ("normalize_wecom_feedback_records",),
                ),
            ),
            VerificationProbe(
                level=3,
                kind="wiring",
                target="queue.py imports normalize_wecom_feedback_records from wecom_normalizer",
                checker=_check_wiring_all(
                    f"{FEEDBACK_SRC}/queue.py",
                    (
                        r"from\s+\.wecom_normalizer\s+import",
                        r"normalize_wecom_feedback_records",
                    ),
                ),
            ),
        ),
        evidence_hints=EvidenceHints(
            source_dirs=(FEEDBACK_SRC,),
            test_patterns=(
                r"test_wecom_normalizer",
                r"test_feedback_queue",
                r"test_memory_wiring",
            ),
            schema_names=("feedback_event.schema.json",),
            fixture_patterns=(r"phase5_wecom_feedback", r"phase6_read_feedback"),
            gate_names=("feedback-service", "contract-test-suite"),
        ),
    ),
    # 7. Read-only APIs
    RequirementSpec(
        req_id="READVIEW-01",
        description=(
            "Build read-only conversation/task/feedback APIs from contract "
            "logs."
        ),
        prd_section="10.2",
        human_gate=False,
        probes=(
            VerificationProbe(
                level=1,
                kind="schema",
                target="no schema requirement for read-only APIs",
                checker=_check_no_schema(),
            ),
            VerificationProbe(
                level=2,
                kind="library",
                target="api.py, read_model.py, privacy.py with expected names",
                checker=_check_library_surface(
                    f"{READVIEW_SRC}/api.py",
                    ("handle_get",),
                ),
            ),
            VerificationProbe(
                level=3,
                kind="wiring",
                target="api.py reads from contract logs via read_model",
                checker=_check_wiring_all(
                    f"{READVIEW_SRC}/api.py",
                    (r"read_model", r"get_conversation", r"get_task"),
                ),
            ),
        ),
        evidence_hints=EvidenceHints(
            source_dirs=(READVIEW_SRC,),
            test_patterns=(r"test_api", r"test_read_model", r"test_phase6_read_feedback"),
            schema_names=(),
            fixture_patterns=(r"phase6_read_feedback",),
            gate_names=("conversation-read-view", "contract-test-suite"),
        ),
    ),
    # 8. Observability / replay / privacy
    RequirementSpec(
        req_id="OBSERVE-01",
        description=(
            "Enforce observability, replay, privacy, and legal safety "
            "baselines."
        ),
        prd_section="10.2",
        human_gate=False,
        probes=(
            VerificationProbe(
                level=1,
                kind="schema",
                target="memory_use and execution_trace schemas exist",
                checker=_check_schemas_exist(
                    ("memory_use.schema.json", "execution_trace.schema.json")
                ),
            ),
            VerificationProbe(
                level=2,
                kind="library",
                target="privacy_scan.py, event_stream_replay.py, writer.py with expected names",
                checker=_check_library_surface(
                    f"{CONTRACT_SUITE_SRC}/privacy_scan.py",
                    ("scan_privacy_targets", "PrivacyIssue"),
                ),
            ),
            VerificationProbe(
                level=3,
                kind="wiring",
                target="hook.py imports ContractEventWriter from writer.py",
                checker=_check_wiring_all(
                    f"{HERMES_SRC}/hook.py",
                    (r"from\s+\.writer\s+import", r"ContractEventWriter"),
                ),
            ),
        ),
        evidence_hints=EvidenceHints(
            source_dirs=(CONTRACT_SUITE_SRC, HERMES_SRC),
            test_patterns=(
                r"test_privacy_gates",
                r"test_event_stream_replay",
                r"test_thin_layer_boundaries",
            ),
            schema_names=("memory_use.schema.json", "execution_trace.schema.json"),
            fixture_patterns=(r"phase4_.*_event_stream",),
            gate_names=("phase7-privacy-boundary", "contract-test-suite", "hermes-contract-layer"),
        ),
    ),
    # 9. Composability CI
    RequirementSpec(
        req_id="COMPOSE-01",
        description=(
            "Enforce composability and industry-neutral contract behavior "
            "in CI."
        ),
        prd_section="10.3",
        human_gate=False,
        probes=(
            VerificationProbe(
                level=1,
                kind="schema",
                target="no schema requirement for composability CI",
                checker=_check_no_schema(),
            ),
            VerificationProbe(
                level=2,
                kind="library",
                target="boundary_checks.py with expected names",
                checker=_check_library_surface(
                    f"{CONTRACT_SUITE_SRC}/boundary_checks.py",
                    ("BoundaryAllowlistPolicy", "assert_platform_contract_import_boundary"),
                ),
            ),
            VerificationProbe(
                level=3,
                kind="wiring",
                target="run_v2_gates.py includes contract-test-suite gate that discovers composability tests",
                checker=_check_wiring_all(
                    "scripts/run_v2_gates.py",
                    (
                        r"contract-test-suite",
                        r"packages/contract-test-suite/tests",
                    ),
                ),
            ),
        ),
        evidence_hints=EvidenceHints(
            source_dirs=(CONTRACT_SUITE_SRC,),
            test_patterns=(
                r"test_composability",
                r"test_boundary_allowlist",
                r"test_ci_workflow_contract",
            ),
            schema_names=(),
            fixture_patterns=(r"non_legal_", r"platform_foundation_non_legal"),
            gate_names=("contract-test-suite",),
        ),
    ),
    # 10. Lawyer trial (human gate)
    RequirementSpec(
        req_id="TRIAL-01",
        description=(
            "Complete the five-workday lawyer trial acceptance criteria."
        ),
        prd_section="10.4",
        human_gate=True,
        probes=(
            VerificationProbe(
                level=1,
                kind="schema",
                target="no schema requirement for lawyer trial",
                checker=_check_no_schema(),
            ),
            VerificationProbe(
                level=2,
                kind="library",
                target="trial_acceptance.py with expected names",
                checker=_check_library_surface(
                    f"{CONTRACT_SUITE_SRC}/trial_acceptance.py",
                    ("evaluate_trial_acceptance", "TrialAcceptanceReport"),
                ),
            ),
            VerificationProbe(
                level=3,
                kind="wiring",
                target="lawyer trial is a human gate — no production wiring required",
                checker=_check_no_schema(),
            ),
        ),
        evidence_hints=EvidenceHints(
            source_dirs=(CONTRACT_SUITE_SRC,),
            test_patterns=(r"test_trial_acceptance",),
            schema_names=(),
            fixture_patterns=(),
            gate_names=("contract-test-suite",),
        ),
    ),
)


# ---------------------------------------------------------------------------
# PRD Section 10 criterion-to-test mapping
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PRDCriterionMapping:
    """Maps a PRD §10 acceptance criterion to tests and fixtures."""

    section: str
    criterion: str
    tests: tuple[str, ...]
    fixtures: tuple[str, ...]
    gate: str


PRD_SECTION_10_MAPPING: tuple[PRDCriterionMapping, ...] = (
    PRDCriterionMapping(
        section="10.1",
        criterion="README.md explains V2 positioning, repo structure, V2 doc entry",
        tests=("(manual) README.md exists",),
        fixtures=(),
        gate="(manual)",
    ),
    PRDCriterionMapping(
        section="10.1",
        criterion="V2-PRD.md covers goals, current state, feature scope, non-goals, contract schemas, safety/compliance, acceptance",
        tests=("(manual) docs/requirements/V2-PRD.md exists",),
        fixtures=(),
        gate="(manual)",
    ),
    PRDCriterionMapping(
        section="10.1",
        criterion=".gitignore excludes keys, logs, databases, caches, runtime state, customer docs, build artifacts",
        tests=("(manual) .gitignore exists",),
        fixtures=(),
        gate="(manual)",
    ),
    PRDCriterionMapping(
        section="10.1",
        criterion="Repository is a git repository",
        tests=("(manual) .git/ exists",),
        fixtures=(),
        gate="(manual)",
    ),
    PRDCriterionMapping(
        section="10.2",
        criterion="contract-test-suite passing in CI main branch",
        tests=(
            "packages/contract-test-suite/tests/test_schema_validation.py",
            "packages/contract-test-suite/tests/test_fixture_replay.py",
            "packages/contract-test-suite/tests/test_event_stream_replay.py",
        ),
        fixtures=(
            "packages/contract-test-suite/fixtures/phase4_success_event_stream.jsonl",
            "packages/contract-test-suite/fixtures/phase5_wecom_contract_stream.jsonl",
        ),
        gate="contract-test-suite",
    ),
    PRDCriterionMapping(
        section="10.2",
        criterion="WeCom service contract tests cover callback verification, ACK, normalization, outbound policy, send envelope, feedback idempotency, no-secret logging",
        tests=(
            "services/wecom-service/tests/test_ingress_runtime.py",
            "services/wecom-service/tests/test_normalization.py",
            "services/wecom-service/tests/test_output_policy.py",
            "services/wecom-service/tests/test_protocol.py",
        ),
        fixtures=(
            "packages/contract-test-suite/fixtures/phase5_wecom_contract_stream.jsonl",
            "packages/contract-test-suite/fixtures/phase55_output_policy_cases.json",
        ),
        gate="wecom-service",
    ),
    PRDCriterionMapping(
        section="10.2",
        criterion="schema validation: 5 schema field validation, enum validation, required validation all pass",
        tests=(
            "packages/contract-test-suite/tests/test_schema_validation.py",
        ),
        fixtures=(),
        gate="contract-test-suite",
    ),
    PRDCriterionMapping(
        section="10.2",
        criterion="fixture replay: golden samples convert from Hermes hook output to standard events",
        tests=(
            "packages/contract-test-suite/tests/test_fixture_replay.py",
        ),
        fixtures=(
            "packages/contract-test-suite/fixtures/phase4_success_event_stream.jsonl",
            "packages/contract-test-suite/fixtures/phase5_wecom_contract_stream.jsonl",
        ),
        gate="contract-test-suite",
    ),
    PRDCriterionMapping(
        section="10.2",
        criterion="relationship integrity: message -> task -> route -> response -> feedback chain unbroken",
        tests=(
            "packages/contract-test-suite/tests/test_fixture_replay.py",
            "packages/contract-test-suite/tests/test_event_stream_replay.py",
        ),
        fixtures=(
            "packages/contract-test-suite/fixtures/phase4_success_event_stream.jsonl",
            "packages/contract-test-suite/fixtures/phase5_wecom_contract_stream.jsonl",
        ),
        gate="contract-test-suite",
    ),
    PRDCriterionMapping(
        section="10.2",
        criterion="contract log coverage >= 95%: real tasks must have both AgentTurn and AgentResult",
        tests=(
            "packages/contract-test-suite/tests/test_coverage_report.py",
        ),
        fixtures=(),
        gate="contract-test-suite",
    ),
    PRDCriterionMapping(
        section="10.2",
        criterion="output boundary fixture: backend gateway/update/command/meta samples blocked or rewritten",
        tests=(
            "services/wecom-service/tests/test_output_policy.py",
            "packages/contract-test-suite/tests/test_thin_layer_boundaries.py",
        ),
        fixtures=(
            "packages/contract-test-suite/fixtures/phase55_output_policy_cases.json",
        ),
        gate="contract-test-suite",
    ),
    PRDCriterionMapping(
        section="10.3",
        criterion="composability synthesis tasks (non-legal + legal mix) all schema-valid, relationship-complete, no legal field leakage",
        tests=(
            "packages/contract-test-suite/tests/test_composability.py",
            "packages/contract-test-suite/tests/test_boundary_allowlist.py",
        ),
        fixtures=(
            "packages/contract-test-suite/fixtures/non_legal_education_task.json",
            "packages/contract-test-suite/fixtures/non_legal_finance_tax_task.json",
            "packages/contract-test-suite/fixtures/platform_foundation_non_legal_run.json",
        ),
        gate="contract-test-suite",
    ),
    PRDCriterionMapping(
        section="10.4",
        criterion="at least 1 lawyer uses WeCom bot for 5 consecutive workdays, 15+ real tasks, 12+ with business output, 3+ task types",
        tests=(
            "packages/contract-test-suite/tests/test_trial_acceptance.py",
        ),
        fixtures=(),
        gate="(human gate)",
    ),
    PRDCriterionMapping(
        section="10.4",
        criterion="long-task success rate >= 80%, normal task success rate >= 85%, feedback collection rate >= 60%",
        tests=(
            "packages/contract-test-suite/tests/test_trial_acceptance.py",
        ),
        fixtures=(),
        gate="(human gate)",
    ),
    PRDCriterionMapping(
        section="10.4",
        criterion="Hermes lawfirm profile WeCom template card feedback link does not regress; V2 live acceptance uses InkStatute WeCom service",
        tests=(
            "packages/contract-test-suite/tests/test_phase55_wecom_service_loop.py",
            "packages/contract-test-suite/tests/test_phase5_wecom_loop.py",
        ),
        fixtures=(
            "packages/contract-test-suite/fixtures/phase55_wecom_service_agent_loop.json",
            "packages/contract-test-suite/fixtures/phase5_wecom_feedback_loop_fixture.json",
        ),
        gate="contract-test-suite",
    ),
)


# ---------------------------------------------------------------------------
# Evidence collector
# ---------------------------------------------------------------------------


def _collect_implementation_files(
    hints: EvidenceHints, repo_root: Path
) -> list[str]:
    """Collect source files from hinted source directories."""
    result: list[str] = []
    for source_dir_rel in hints.source_dirs:
        source_dir = repo_root / source_dir_rel
        if not source_dir.is_dir():
            continue
        for py_file in sorted(source_dir.rglob("*.py")):
            if py_file.name == "__init__.py":
                continue
            result.append(str(py_file.relative_to(repo_root)))
    return sorted(set(result))


def _derive_test_dirs(source_dirs: tuple[str, ...]) -> list[str]:
    """Derive test directories from source directories.

    E.g. 'services/wecom-service/src/wecom_service' -> 'services/wecom-service/tests'
    """
    test_dirs: list[str] = []
    for source_dir in source_dirs:
        parts = source_dir.split("/")
        try:
            src_idx = parts.index("src")
        except ValueError:
            continue
        test_dir = "/".join(parts[:src_idx]) + "/tests"
        test_dirs.append(test_dir)
    return sorted(set(test_dirs))


def _collect_test_modules(
    hints: EvidenceHints, repo_root: Path
) -> list[str]:
    """Collect test files matching the hinted patterns in relevant test dirs."""
    result: list[str] = []
    test_dir_rels = _derive_test_dirs(hints.source_dirs)
    compiled_patterns = [re.compile(p) for p in hints.test_patterns]
    for test_dir_rel in test_dir_rels:
        test_dir = repo_root / test_dir_rel
        if not test_dir.is_dir():
            continue
        for test_file in sorted(test_dir.rglob("test_*.py")):
            name = test_file.stem
            if any(pattern.search(name) for pattern in compiled_patterns):
                result.append(str(test_file.relative_to(repo_root)))
    return sorted(set(result))


def _collect_schema_ids(hints: EvidenceHints, repo_root: Path) -> list[str]:
    """Collect schema file names from hinted schema names."""
    schema_dir = repo_root / SCHEMA_DIR_REL
    result: list[str] = []
    for name in hints.schema_names:
        if (schema_dir / name).exists():
            result.append(name)
    return sorted(set(result))


def _collect_fixtures(hints: EvidenceHints, repo_root: Path) -> list[str]:
    """Collect fixture file paths matching hinted patterns."""
    result: list[str] = []
    compiled_patterns = [re.compile(p) for p in hints.fixture_patterns]
    for fixture_dir_rel in FIXTURE_DIR_RELS:
        fixture_dir = repo_root / fixture_dir_rel
        if not fixture_dir.is_dir():
            continue
        for fixture_file in sorted(fixture_dir.iterdir()):
            if not fixture_file.is_file():
                continue
            name = fixture_file.name
            if any(pattern.search(name) for pattern in compiled_patterns):
                result.append(str(fixture_file.relative_to(repo_root)))
    return sorted(set(result))


def _collect_phase_references(test_modules: list[str]) -> list[str]:
    """Extract phase numbers from test file names (e.g., test_phase5_* -> Phase 5)."""
    phases: set[int] = set()
    for test_path in test_modules:
        match = re.search(r"test_phase(\d+)", test_path)
        if match:
            phases.add(int(match.group(1)))
    return sorted(f"Phase {p}" for p in phases)


def collect_evidence(req: RequirementSpec, repo_root: Path) -> dict[str, Any]:
    """Collect the full evidence bundle for a requirement."""
    implementation_files = _collect_implementation_files(req.evidence_hints, repo_root)
    test_modules = _collect_test_modules(req.evidence_hints, repo_root)
    schema_ids = _collect_schema_ids(req.evidence_hints, repo_root)
    fixtures = _collect_fixtures(req.evidence_hints, repo_root)
    phase_references = _collect_phase_references(test_modules)
    return {
        "implementation_files": implementation_files,
        "test_modules": test_modules,
        "gate_suites": sorted(req.evidence_hints.gate_names),
        "schema_ids": schema_ids,
        "fixtures": fixtures,
        "phase_references": phase_references,
    }


# ---------------------------------------------------------------------------
# Three-level verification and classification
# ---------------------------------------------------------------------------


def run_verification(
    req: RequirementSpec, repo_root: Path
) -> dict[str, dict[str, Any]]:
    """Run all probes for a requirement and return the verification result.

    A level is considered passed only when *every* probe at that level passes.
    If a probe's checker raises, the probe is treated as failed (and thus the
    level fails) so a single unreadable file cannot abort the whole audit.
    """
    levels: dict[int, dict[str, Any]] = {}
    for probe in req.probes:
        try:
            passed, evidence = probe.checker(repo_root)
        except Exception as exc:  # noqa: BLE001 - audit must not crash the gate
            passed, evidence = False, f"{probe.kind} probe error: {exc}"
        prior = levels.get(probe.level)
        if prior is None:
            levels[probe.level] = {"passed": passed, "evidence": evidence}
        else:
            # Aggregate: all probes at a level must pass.
            levels[probe.level] = {
                "passed": prior["passed"] and passed,
                "evidence": f"{prior['evidence']}; {evidence}",
            }
    return {
        "level_1_schema": levels.get(1, {"passed": False, "evidence": "no level-1 probe"}),
        "level_2_library": levels.get(2, {"passed": False, "evidence": "no level-2 probe"}),
        "level_3_wiring": levels.get(3, {"passed": False, "evidence": "no level-3 probe"}),
    }


def classify(req: RequirementSpec, verification: dict[str, dict[str, Any]]) -> str:
    """Classify a requirement based on its verification results."""
    if req.human_gate:
        return "human_gate"
    l1 = verification.get("level_1_schema", {}).get("passed", False)
    l2 = verification.get("level_2_library", {}).get("passed", False)
    l3 = verification.get("level_3_wiring", {}).get("passed", False)
    if l1 and l2 and l3:
        return "satisfied"
    if l1 and l2 and not l3:
        return "partial"
    return "gap"


# ---------------------------------------------------------------------------
# JSON sidecar builder
# ---------------------------------------------------------------------------


def build_traceability_json(repo_root: Path) -> dict[str, Any]:
    """Build the complete traceability matrix as a JSON-serializable dict."""
    requirements_data: list[dict[str, Any]] = []
    for req in REQUIREMENT_REGISTRY:
        evidence = collect_evidence(req, repo_root)
        verification = run_verification(req, repo_root)
        status = classify(req, verification)
        requirements_data.append(
            {
                "req_id": req.req_id,
                "description": req.description,
                "status": status,
                "prd_section": req.prd_section,
                "human_gate": req.human_gate,
                "phase_reference": ", ".join(evidence["phase_references"]),
                "evidence": {
                    "implementation_files": evidence["implementation_files"],
                    "test_modules": evidence["test_modules"],
                    "gate_suites": evidence["gate_suites"],
                    "schema_ids": evidence["schema_ids"],
                    "fixtures": evidence["fixtures"],
                },
                "verification": verification,
            }
        )
    prd_mapping_data = [
        {
            "section": mapping.section,
            "criterion": mapping.criterion,
            "tests": list(mapping.tests),
            "fixtures": list(mapping.fixtures),
            "gate": mapping.gate,
        }
        for mapping in PRD_SECTION_10_MAPPING
    ]
    return {
        "schema_version": "1.0",
        "generated_at": GENERATED_AT_PLACEHOLDER,
        "requirements": requirements_data,
        "prd_section_10_mapping": prd_mapping_data,
    }


def write_sidecar(data: dict[str, Any], repo_root: Path) -> Path:
    """Write the traceability JSON sidecar to acceptance/v2-traceability.json."""
    sidecar_path = repo_root / SIDECAR_REL
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return sidecar_path


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def format_matrix(data: dict[str, Any]) -> str:
    """Format the traceability matrix as a human-readable table."""
    lines: list[str] = []
    lines.append("V2 Requirement Audit — Traceability Matrix")
    lines.append("=" * 70)
    for req in data["requirements"]:
        status_marker = {
            "satisfied": "[OK]",
            "partial": "[PARTIAL]",
            "gap": "[GAP]",
            "human_gate": "[HUMAN GATE]",
        }.get(req["status"], "[?]")
        lines.append(f"  {status_marker:14s} {req['req_id']:12s} {req['status']}")
        lines.append(f"  {'':14s} {'':12s} {req['description'][:80]}")
        v = req["verification"]
        for level_key, label in (
            ("level_1_schema", "L1 Schema"),
            ("level_2_library", "L2 Library"),
            ("level_3_wiring", "L3 Wiring"),
        ):
            passed = v[level_key]["passed"]
            mark = "PASS" if passed else "FAIL"
            lines.append(f"  {'':14s} {'':12s}   {label}: {mark}")
        lines.append("")
    gap_count = sum(1 for r in data["requirements"] if r["status"] == "gap")
    partial_count = sum(1 for r in data["requirements"] if r["status"] == "partial")
    satisfied_count = sum(1 for r in data["requirements"] if r["status"] == "satisfied")
    human_gate_count = sum(1 for r in data["requirements"] if r["status"] == "human_gate")
    lines.append("-" * 70)
    lines.append(
        f"Summary: {satisfied_count} satisfied, {partial_count} partial, "
        f"{gap_count} gap, {human_gate_count} human_gate"
    )
    return "\n".join(lines)


def format_single_requirement(
    req: RequirementSpec, repo_root: Path
) -> str:
    """Format a detailed evidence bundle for a single requirement."""
    evidence = collect_evidence(req, repo_root)
    verification = run_verification(req, repo_root)
    status = classify(req, verification)
    lines: list[str] = []
    lines.append(f"Requirement: {req.req_id}")
    lines.append(f"Description: {req.description}")
    lines.append(f"PRD Section: {req.prd_section}")
    lines.append(f"Status: {status}")
    lines.append(f"Human Gate: {req.human_gate}")
    lines.append("")
    lines.append("Evidence:")
    lines.append(f"  Implementation files ({len(evidence['implementation_files'])}):")
    for f_path in evidence["implementation_files"]:
        lines.append(f"    - {f_path}")
    lines.append(f"  Test modules ({len(evidence['test_modules'])}):")
    for f_path in evidence["test_modules"]:
        lines.append(f"    - {f_path}")
    lines.append(f"  Gate suites: {', '.join(evidence['gate_suites'])}")
    lines.append(f"  Schema IDs: {', '.join(evidence['schema_ids']) or '(none)'}")
    lines.append(f"  Fixtures ({len(evidence['fixtures'])}):")
    for f_path in evidence["fixtures"]:
        lines.append(f"    - {f_path}")
    lines.append(f"  Phase references: {', '.join(evidence['phase_references']) or '(none)'}")
    lines.append("")
    lines.append("Verification:")
    for level_key, label in (
        ("level_1_schema", "Level 1 (Schema)"),
        ("level_2_library", "Level 2 (Library)"),
        ("level_3_wiring", "Level 3 (Wiring)"),
    ):
        v = verification[level_key]
        mark = "PASS" if v["passed"] else "FAIL"
        lines.append(f"  {label}: {mark}")
        lines.append(f"    {v['evidence']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic V2 requirement audit and traceability matrix generator."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write acceptance/v2-traceability.json sidecar.",
    )
    parser.add_argument(
        "--check-gaps",
        action="store_true",
        help="Exit non-zero if any requirement is classified as gap.",
    )
    parser.add_argument(
        "--requirement",
        type=str,
        default=None,
        help="Print detailed evidence bundle for a single requirement (by req_id).",
    )
    args = parser.parse_args(argv)

    repo_root = REPO_ROOT

    # Single-requirement mode
    if args.requirement is not None:
        req = next(
            (r for r in REQUIREMENT_REGISTRY if r.req_id == args.requirement),
            None,
        )
        if req is None:
            print(f"Unknown requirement: {args.requirement}", file=sys.stderr)
            print(
                f"Available: {', '.join(r.req_id for r in REQUIREMENT_REGISTRY)}",
                file=sys.stderr,
            )
            return 1
        print(format_single_requirement(req, repo_root))
        return 0

    # Build full traceability data
    data = build_traceability_json(repo_root)

    # JSON sidecar mode
    if args.json:
        sidecar_path = write_sidecar(data, repo_root)
        print(f"Wrote {sidecar_path.relative_to(repo_root)}")
        gap_count = sum(1 for r in data["requirements"] if r["status"] == "gap")
        partial_count = sum(1 for r in data["requirements"] if r["status"] == "partial")
        satisfied_count = sum(
            1 for r in data["requirements"] if r["status"] == "satisfied"
        )
        human_gate_count = sum(
            1 for r in data["requirements"] if r["status"] == "human_gate"
        )
        print(
            f"Summary: {satisfied_count} satisfied, {partial_count} partial, "
            f"{gap_count} gap, {human_gate_count} human_gate"
        )
        return 0

    # Gap-check mode
    if args.check_gaps:
        gap_count = sum(1 for r in data["requirements"] if r["status"] == "gap")
        if gap_count > 0:
            gap_ids = sorted(
                r["req_id"] for r in data["requirements"] if r["status"] == "gap"
            )
            print(f"FAIL: {gap_count} requirement(s) classified as gap: {', '.join(gap_ids)}")
            return 1
        print("PASS: no requirements classified as gap")
        return 0

    # Default: print matrix
    print(format_matrix(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
