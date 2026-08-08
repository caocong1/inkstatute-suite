from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
import re
import sys
from typing import Any
import unittest

REPO_ROOT = Path(__file__).resolve().parents[3]
for source_path in (
    REPO_ROOT / "packages" / "platform-contract" / "src",
):
    sys.path.insert(0, str(source_path))

from contract_test_suite.fixture_replay import assert_relationship_integrity
from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle
from wecom_service.agent_backend import select_agent_backend
from wecom_service.output_policy import apply_output_policy


def build_hermes_adapter_manifest(
    *,
    backend_version: str,
    profile_name: str,
    adapter_version: str = "0.1.0",
    no_channel_io: bool = True,
) -> dict[str, Any]:
    """Build a backend-neutral manifest for the Hermes lawfirm adapter.

    Inlined from the retired hermes_contract_layer.adapter_manifest module
    (Phase 104-02: legacy convergence).
    """
    return {
        "adapter_name": "hermes-lawfirm-agent-adapter",
        "adapter_version": adapter_version,
        "mode": "hermes",
        "backend_version": backend_version,
        "profile_name": profile_name,
        "bundle_id": "lawfirm-profile-bundle",
        "capabilities": {
            "hook_event_support": [
                "agent:end",
                "gateway:startup",
                "response_filter_contract_result_recorder",
            ],
            "invocation_mode": "sync",
            "feedback_target_support": "message_id",
            "session_read_support": True,
            "artifact_return_support": True,
            "trace_support": True,
            "no_channel_io": no_channel_io,
        },
        "metadata": {
            "after_filter_recorder_dir": "response_filter_contract_result_recorder",
            "manifest_hook_name": "contract_result_recorder",
            "repo_hook_artifacts": [
                "hooks/response_filter_contract_result_recorder",
                "response_filter_contract_result_recorder",
            ],
            "ordinary_wecom_channel_owner": "inkstatute_wecom_service",
            "no_channel_io_evidence": "Hermes adapter returns platform events/results; WeCom send is owned by InkStatute service.",
            "source_status": "repo_fixture_manifest",
            "production_ready": True,
        },
    }


PHASE55_LOOP = LOCAL_FIXTURE_ROOT / "phase55_wecom_service_agent_loop.json"
PHASE55_POLICY = LOCAL_FIXTURE_ROOT / "phase55_output_policy_cases.json"
SECRET_LIKE = re.compile(
    r"(sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN|password\s*[:=]|secret\s*[:=]|token\s*[:=])",
    re.IGNORECASE,
)


class Phase55WeComServiceLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()

    def test_phase55_fixture_validates_relationships_and_no_channel_io(self) -> None:
        fixture = _load_json(PHASE55_LOOP)

        validate_event_bundle(fixture, self.schemas)
        report = assert_relationship_integrity([PHASE55_LOOP], max_breakage_rate=0.0, schemas=self.schemas)
        selection = select_agent_backend(
            {"agent_backend": {"mode": "hermes"}},
            [build_hermes_adapter_manifest(backend_version="hermes-fixture-1", profile_name="lawfirm")],
        )

        self.assertEqual(report.broken_relationship_count, 0)
        self.assertTrue(selection.live_acceptance_allowed)
        self.assertIs(fixture["adapter_manifest"]["capabilities"]["no_channel_io"], True)
        self.assertEqual(fixture["send_envelope"]["sender"], "inkstatute_wecom_service")
        self.assertNotRegex(_visible_text(fixture["send_envelope"]).lower(), r"hermes|gateway|/help|debug")

    def test_output_policy_cases_cover_allow_rewrite_and_block(self) -> None:
        cases = _load_json(PHASE55_POLICY)["cases"]
        actions = set()

        for case in cases:
            with self.subTest(case=case["id"]):
                decision = apply_output_policy(case["input"])
                actions.add(decision.action)
                self.assertEqual(decision.action, case["expected_action"])
                if decision.action in {"block", "rewrite"}:
                    self.assertNotRegex((decision.visible_text or "").lower(), r"hermes|gateway|/help|debug|stack")
                if case["expected_action"] == "allow":
                    self.assertEqual(decision.visible_text, case["input"])

        self.assertEqual(actions, {"allow", "rewrite", "block"})

    def test_route_mismatch_feedback_remains_human_review_only(self) -> None:
        feedback = _load_json(PHASE55_LOOP)["events"]["feedback_event"]

        self.assertTrue(feedback["route_mismatch"])
        self.assertTrue(feedback["skill_candidate"]["requires_human_review"])
        self.assertTrue(feedback["skill_candidate"]["metadata"]["no_auto_modify"])
        self.assertTrue(feedback["metadata"]["no_auto_modify"])

    def test_phase55_fixtures_are_reference_first_and_secret_free(self) -> None:
        for path in (PHASE55_LOOP, PHASE55_POLICY):
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(SECRET_LIKE.search(text))
                self.assert_no_exact_raw_payload_key(_load_json(path))

    def assert_no_exact_raw_payload_key(self, value: Any) -> None:
        if isinstance(value, Mapping):
            self.assertNotIn("raw_payload", value)
            for child in value.values():
                self.assert_no_exact_raw_payload_key(child)
        elif isinstance(value, list):
            for child in value:
                self.assert_no_exact_raw_payload_key(child)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _visible_text(envelope: Mapping[str, Any]) -> str:
    text = envelope.get("text")
    if isinstance(text, Mapping):
        content = text.get("content")
        if isinstance(content, str):
            return content
    return ""


if __name__ == "__main__":
    unittest.main()
