from __future__ import annotations

import unittest

from contract_test_suite.paths import REPO_ROOT


WORKFLOW = REPO_ROOT / ".github" / "workflows" / "v2-contract-gates.yml"
ROOT_README = REPO_ROOT / "README.md"
CONTRACT_README = REPO_ROOT / "packages" / "contract-test-suite" / "README.md"
FORBIDDEN_WORKFLOW_TEXT = (
    "upload-artifact",
    ".db",
    ".sqlite",
    ".log",
    "media",
    "callback body",
    "customer",
    "raw_payload",
)


class CiWorkflowContractTests(unittest.TestCase):
    def test_workflow_wraps_local_v2_gate_runner(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("name: V2 Contract Gates", text)
        self.assertIn('python-version: "3.11"', text)
        self.assertIn("python scripts/run_v2_gates.py", text)

    def test_workflow_does_not_upload_unsafe_artifacts(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        for forbidden in FORBIDDEN_WORKFLOW_TEXT:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_docs_preserve_fixture_runtime_and_phase8_boundary(self) -> None:
        root_text = ROOT_README.read_text(encoding="utf-8")
        contract_text = CONTRACT_README.read_text(encoding="utf-8")

        self.assertIn("V2 Contract Gates", root_text)
        self.assertIn("python scripts/run_v2_gates.py", root_text)
        self.assertIn("Phase 7 Gates", contract_text)
        self.assertIn("runtime input", contract_text)
        self.assertIn("not provided", contract_text)
        self.assertIn("Phase 8 owns live lawyer-trial acceptance", contract_text)


if __name__ == "__main__":
    unittest.main()

