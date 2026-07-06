"""Comprehensive test suite for scripts/audit_v2_requirements.py.

Tests cover:
  1. Script execution and CLI modes
  2. JSON sidecar generation and determinism
  3. Requirement registry completeness
  4. Three-level verification and classification
  5. Evidence collection (files, tests, gates, schemas, fixtures)
  6. PRD Section 10 mapping coverage
  7. Gap-check mode exit codes
  8. Single-requirement mode
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "audit_v2_requirements.py"


def _load_audit_module():
    """Load the audit script as a module via importlib."""
    spec = importlib.util.spec_from_file_location(
        "audit_v2_requirements", SCRIPT_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load audit module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_v2_requirements"] = module
    spec.loader.exec_module(module)
    return module


audit = _load_audit_module()


class TestAuditScriptRuns(unittest.TestCase):
    """1. test_audit_script_runs_without_error"""

    def test_audit_script_runs_without_error(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("Traceability Matrix", result.stdout)


class TestAuditJsonSidecar(unittest.TestCase):
    """2. test_audit_produces_json_sidecar"""

    def test_audit_produces_json_sidecar(self):
        sidecar_path = REPO_ROOT / "acceptance" / "v2-traceability.json"
        backup = sidecar_path.read_bytes() if sidecar_path.exists() else None
        try:
            data = audit.build_traceability_json(REPO_ROOT)
            written_path = audit.write_sidecar(data, REPO_ROOT)
            self.assertTrue(written_path.exists())
            self.assertEqual(written_path, sidecar_path)
            loaded = json.loads(written_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema_version"], "1.0")
        finally:
            if backup is not None:
                sidecar_path.write_bytes(backup)
            else:
                sidecar_path.unlink(missing_ok=True)
                accept_dir = REPO_ROOT / "acceptance"
                if accept_dir.exists() and not any(accept_dir.iterdir()):
                    accept_dir.rmdir()


class TestAuditDeterminism(unittest.TestCase):
    """3. test_audit_is_deterministic"""

    def test_audit_is_deterministic(self):
        data1 = audit.build_traceability_json(REPO_ROOT)
        data2 = audit.build_traceability_json(REPO_ROOT)
        json1 = json.dumps(data1, indent=2, sort_keys=True)
        json2 = json.dumps(data2, indent=2, sort_keys=True)
        self.assertEqual(json1, json2, "Two runs produced different JSON")

    def test_audit_deterministic_via_subprocess(self):
        """Verify byte-identical output across two subprocess runs."""
        sidecar_path = REPO_ROOT / "acceptance" / "v2-traceability.json"
        backup = sidecar_path.read_bytes() if sidecar_path.exists() else None
        env = os.environ.copy()
        try:
            result1 = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--json"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
            content1 = sidecar_path.read_text(encoding="utf-8")
            result2 = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--json"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
            content2 = sidecar_path.read_text(encoding="utf-8")
            self.assertEqual(result1.returncode, 0)
            self.assertEqual(result2.returncode, 0)
            self.assertEqual(content1, content2, "Two subprocess runs produced different JSON")
        finally:
            if backup is not None:
                sidecar_path.write_bytes(backup)
            else:
                sidecar_path.unlink(missing_ok=True)
                accept_dir = REPO_ROOT / "acceptance"
                if accept_dir.exists() and not any(accept_dir.iterdir()):
                    accept_dir.rmdir()


class TestAuditCoversAllRequirements(unittest.TestCase):
    """4. test_audit_covers_all_10_requirements"""

    EXPECTED_REQ_IDS = {
        "WECOM-01",
        "ADAPTER-01",
        "HERMES-01",
        "OUTPUT-01",
        "LOOP-01",
        "FEEDBACK-01",
        "READVIEW-01",
        "OBSERVE-01",
        "COMPOSE-01",
        "TRIAL-01",
    }

    def test_audit_covers_all_10_requirements(self):
        data = audit.build_traceability_json(REPO_ROOT)
        actual_ids = {req["req_id"] for req in data["requirements"]}
        self.assertEqual(actual_ids, self.EXPECTED_REQ_IDS)
        self.assertEqual(len(data["requirements"]), 10)

    def test_registry_has_10_entries(self):
        self.assertEqual(len(audit.REQUIREMENT_REGISTRY), 10)


class TestAuditHumanGateClassification(unittest.TestCase):
    """5. test_audit_classifies_human_gate_correctly"""

    def test_audit_classifies_human_gate_correctly(self):
        data = audit.build_traceability_json(REPO_ROOT)
        trial_req = next(
            r for r in data["requirements"] if r["req_id"] == "TRIAL-01"
        )
        self.assertEqual(trial_req["status"], "human_gate")
        self.assertTrue(trial_req["human_gate"])

    def test_human_gate_overrides_probes(self):
        """Even if all probes pass, human_gate requirement is classified as human_gate."""
        req = next(r for r in audit.REQUIREMENT_REGISTRY if r.req_id == "TRIAL-01")
        verification = {
            "level_1_schema": {"passed": True, "evidence": "pass"},
            "level_2_library": {"passed": True, "evidence": "pass"},
            "level_3_wiring": {"passed": True, "evidence": "pass"},
        }
        self.assertEqual(audit.classify(req, verification), "human_gate")


class TestAuditThreeLevelVerification(unittest.TestCase):
    """6. test_audit_three_level_verification_catches_partial"""

    def test_three_level_catches_partial(self):
        """A requirement with L1+L2 passing but L3 failing classifies as partial."""
        req = audit.RequirementSpec(
            req_id="TEST-PARTIAL",
            description="Test requirement",
            prd_section="10.2",
            human_gate=False,
            probes=(
                audit.VerificationProbe(
                    level=1,
                    kind="schema",
                    target="test",
                    checker=audit._check_no_schema(),
                ),
                audit.VerificationProbe(
                    level=2,
                    kind="library",
                    target="test",
                    checker=audit._check_no_schema(),
                ),
                audit.VerificationProbe(
                    level=3,
                    kind="wiring",
                    target="test",
                    checker=lambda root: (False, "wiring missing"),
                ),
            ),
            evidence_hints=audit.EvidenceHints(),
        )
        verification = audit.run_verification(req, REPO_ROOT)
        self.assertTrue(verification["level_1_schema"]["passed"])
        self.assertTrue(verification["level_2_library"]["passed"])
        self.assertFalse(verification["level_3_wiring"]["passed"])
        self.assertEqual(audit.classify(req, verification), "partial")

    def test_three_level_catches_gap(self):
        """A requirement with L1 failing classifies as gap."""
        req = audit.RequirementSpec(
            req_id="TEST-GAP",
            description="Test requirement",
            prd_section="10.2",
            human_gate=False,
            probes=(
                audit.VerificationProbe(
                    level=1,
                    kind="schema",
                    target="test",
                    checker=lambda root: (False, "schema missing"),
                ),
                audit.VerificationProbe(
                    level=2,
                    kind="library",
                    target="test",
                    checker=audit._check_no_schema(),
                ),
                audit.VerificationProbe(
                    level=3,
                    kind="wiring",
                    target="test",
                    checker=audit._check_no_schema(),
                ),
            ),
            evidence_hints=audit.EvidenceHints(),
        )
        verification = audit.run_verification(req, REPO_ROOT)
        self.assertFalse(verification["level_1_schema"]["passed"])
        self.assertEqual(audit.classify(req, verification), "gap")

    def test_three_level_satisfied(self):
        """A requirement with all 3 levels passing classifies as satisfied."""
        req = audit.RequirementSpec(
            req_id="TEST-SATISFIED",
            description="Test requirement",
            prd_section="10.2",
            human_gate=False,
            probes=(
                audit.VerificationProbe(
                    level=1,
                    kind="schema",
                    target="test",
                    checker=audit._check_no_schema(),
                ),
                audit.VerificationProbe(
                    level=2,
                    kind="library",
                    target="test",
                    checker=audit._check_no_schema(),
                ),
                audit.VerificationProbe(
                    level=3,
                    kind="wiring",
                    target="test",
                    checker=audit._check_no_schema(),
                ),
            ),
            evidence_hints=audit.EvidenceHints(),
        )
        verification = audit.run_verification(req, REPO_ROOT)
        self.assertEqual(audit.classify(req, verification), "satisfied")


class TestAuditEvidenceBundle(unittest.TestCase):
    """7. test_audit_evidence_bundle_contains_file_paths"""

    def test_evidence_bundle_contains_implementation_files(self):
        req = next(r for r in audit.REQUIREMENT_REGISTRY if r.req_id == "WECOM-01")
        evidence = audit.collect_evidence(req, REPO_ROOT)
        self.assertTrue(len(evidence["implementation_files"]) > 0)
        for f_path in evidence["implementation_files"]:
            self.assertTrue(
                (REPO_ROOT / f_path).exists(),
                f"Implementation file does not exist: {f_path}",
            )

    def test_evidence_includes_test_modules(self):
        """12. test_audit_evidence_includes_test_modules"""
        req = next(r for r in audit.REQUIREMENT_REGISTRY if r.req_id == "WECOM-01")
        evidence = audit.collect_evidence(req, REPO_ROOT)
        self.assertTrue(len(evidence["test_modules"]) > 0)
        for f_path in evidence["test_modules"]:
            self.assertTrue(
                (REPO_ROOT / f_path).exists(),
                f"Test module does not exist: {f_path}",
            )

    def test_evidence_includes_gate_names(self):
        """13. test_audit_evidence_includes_gate_names"""
        req = next(r for r in audit.REQUIREMENT_REGISTRY if r.req_id == "WECOM-01")
        evidence = audit.collect_evidence(req, REPO_ROOT)
        self.assertTrue(len(evidence["gate_suites"]) > 0)
        self.assertIn("wecom-service", evidence["gate_suites"])

    def test_evidence_includes_schema_ids(self):
        """14. test_audit_evidence_includes_schema_ids"""
        req = next(r for r in audit.REQUIREMENT_REGISTRY if r.req_id == "WECOM-01")
        evidence = audit.collect_evidence(req, REPO_ROOT)
        self.assertTrue(len(evidence["schema_ids"]) > 0)
        self.assertIn("channel_message.schema.json", evidence["schema_ids"])
        self.assertIn("channel_delivery.schema.json", evidence["schema_ids"])

    def test_evidence_includes_fixtures(self):
        """15. test_audit_evidence_includes_fixtures"""
        req = next(r for r in audit.REQUIREMENT_REGISTRY if r.req_id == "LOOP-01")
        evidence = audit.collect_evidence(req, REPO_ROOT)
        self.assertTrue(len(evidence["fixtures"]) > 0)
        for f_path in evidence["fixtures"]:
            self.assertTrue(
                (REPO_ROOT / f_path).exists(),
                f"Fixture does not exist: {f_path}",
            )


class TestAuditPrdMapping(unittest.TestCase):
    """8. test_audit_prd_mapping_covers_sections_10_1_to_10_4"""

    def test_prd_mapping_covers_all_sections(self):
        sections = {m.section for m in audit.PRD_SECTION_10_MAPPING}
        self.assertIn("10.1", sections)
        self.assertIn("10.2", sections)
        self.assertIn("10.3", sections)
        self.assertIn("10.4", sections)

    def test_prd_mapping_in_json(self):
        data = audit.build_traceability_json(REPO_ROOT)
        mapping = data["prd_section_10_mapping"]
        sections = {m["section"] for m in mapping}
        self.assertEqual(sections, {"10.1", "10.2", "10.3", "10.4"})

    def test_prd_mapping_section_10_2_has_tests(self):
        """Each 10.2 criterion maps to at least one test."""
        data = audit.build_traceability_json(REPO_ROOT)
        for entry in data["prd_section_10_mapping"]:
            if entry["section"] == "10.2":
                self.assertTrue(
                    len(entry["tests"]) > 0,
                    f"10.2 criterion has no tests: {entry['criterion']}",
                )


class TestAuditCheckGapsMode(unittest.TestCase):
    """9. test_audit_check_gaps_exits_nonzero_on_gap
    10. test_audit_check_gaps_exits_zero_on_no_gaps"""

    def test_check_gaps_exits_zero_on_no_gaps(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--check-gaps"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("PASS", result.stdout)

    def test_check_gaps_exits_nonzero_on_gap(self):
        """Simulate a gap by patching the classify function to return gap for one req."""
        import io
        from contextlib import redirect_stdout

        original_classify = audit.classify

        def mock_classify(req, verification):
            if req.req_id == "WECOM-01":
                return "gap"
            return original_classify(req, verification)

        with patch.object(audit, "classify", mock_classify), redirect_stdout(io.StringIO()):
            exit_code = audit.main(["--check-gaps"])
        self.assertEqual(exit_code, 1)


class TestAuditSingleRequirementMode(unittest.TestCase):
    """11. test_audit_single_requirement_mode"""

    def test_single_requirement_mode_prints_bundle(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--requirement", "WECOM-01"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Requirement: WECOM-01", result.stdout)
        self.assertIn("Evidence:", result.stdout)
        self.assertIn("Verification:", result.stdout)
        self.assertIn("Implementation files", result.stdout)

    def test_single_requirement_mode_unknown_req(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--requirement", "NONEXIST-01"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unknown requirement", result.stderr)


class TestAuditGateList(unittest.TestCase):
    """Verify the 19 gates are registered in run_v2_gates.py."""

    def test_v2_gates_includes_traceability_gate(self):
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "run_v2_gates.py"), "--list"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0)
        gate_names = result.stdout.strip().split("\n")
        self.assertIn("v2-acceptance-traceability", gate_names)
        self.assertIn("skill-registry", gate_names)
        self.assertIn("router-service", gate_names)
        self.assertIn("codex-backend", gate_names)
        self.assertIn("provider-model-backend", gate_names)
        self.assertIn("admin-console-api", gate_names)
        self.assertIn("rbac", gate_names)
        self.assertIn("rbac-annotation-scan", gate_names)
        self.assertIn("mcp-registry", gate_names)
        self.assertIn("qqbot-channel", gate_names)
        self.assertIn("web-sse-channel", gate_names)
        self.assertIn("wecom-channel", gate_names)
        self.assertIn("platform-sdk-ts", gate_names)
        self.assertIn("model-gateway", gate_names)
        self.assertIn("multi-agent-adapter", gate_names)
        self.assertIn("gate-coverage-meta-test", gate_names)
        self.assertEqual(len(gate_names), 24)


if __name__ == "__main__":
    unittest.main()
