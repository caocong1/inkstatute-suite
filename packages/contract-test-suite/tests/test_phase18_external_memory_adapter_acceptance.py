from __future__ import annotations

import json
import re
import unittest
from collections.abc import Iterable, Mapping
from typing import Any

from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle


PHASE18_FIXTURE = LOCAL_FIXTURE_ROOT / "phase18_external_memory_adapter_acceptance.json"
RAW_PAYLOAD_KEYS = {
    "raw_payload",
    "raw_text",
    "payload_text",
    "full_text",
    "document_text",
    "customer_document_text",
    "case_facts",
    "callback_body",
}
FORBIDDEN_TEXT_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN"),
    re.compile(r"password\s*[:=]", re.IGNORECASE),
    re.compile(r"secret\s*[:=]", re.IGNORECASE),
    re.compile(r"token\s*[:=]", re.IGNORECASE),
    re.compile(r"/home/[^\s]+"),
    re.compile(r"\bgateway\b", re.IGNORECASE),
    re.compile(r"\badmin\b", re.IGNORECASE),
    re.compile(r"\bdebug\b", re.IGNORECASE),
    re.compile(r"(^|\s)/(new|resume|help|status|debug|memory)\b", re.IGNORECASE),
)
REQUIRED_LIVE_LEGAL_GATES = {
    "privacy_review",
    "tenant_isolation_evidence",
    "deletion_export_evidence",
    "data_residency_review",
    "security_secret_review",
    "human_review_policy",
    "latency_relevance_eval",
    "operator_runbook",
    "incident_response",
    "user_deletion_export_procedure",
}


class Phase18ExternalMemoryAdapterAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixture = json.loads(PHASE18_FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_validates_with_existing_bundle_validator(self) -> None:
        self.assertEqual(self.fixture["fixture_id"], "phase18-external-memory-adapter-acceptance-001")
        validate_event_bundle(self.fixture, self.schemas)

    def test_adapter_decisions_keep_external_providers_out_of_default_legal_path(self) -> None:
        manifests = {item["provider"]: item for item in self.fixture["metadata"]["adapter_manifests"]}

        self.assertEqual(manifests["platform_native"]["decision"], "accepted_for_current_legal_use")
        self.assertTrue(manifests["platform_native"]["default_for_legal_memory"])

        for provider in ("mem0", "zep", "hindsight", "openviking", "reme"):
            with self.subTest(provider=provider):
                manifest = manifests[provider]
                self.assertEqual(manifest["decision"], "accepted_for_sanitized_spike")
                self.assertTrue(manifest["sanitized_fixture_only"])
                self.assertFalse(manifest["default_for_legal_memory"])
                self.assertFalse(manifest["approved_for_live_legal_memory"])
                self.assertIn("live_legal_memory_gate", manifest["required_gates"])

    def test_live_legal_memory_gate_is_complete(self) -> None:
        gates = set(self.fixture["metadata"]["live_legal_memory_gates"])

        self.assertLessEqual(REQUIRED_LIVE_LEGAL_GATES, gates)

    def test_memory_evidence_links_to_context_bundle(self) -> None:
        events = self.fixture["events"]
        context_bundle = events["context_bundle"]
        memory_records = {item["memory_id"]: item for item in events["memory_records"]}
        memory_uses = events["memory_uses"]

        self.assertEqual(context_bundle["memory_refs"], ["memory-phase18-adapter-contract-001"])
        self.assertIn("memory-phase18-adapter-contract-001", memory_records)
        self.assertEqual(memory_records["memory-phase18-adapter-contract-001"]["status"], "active")
        self.assertEqual(memory_uses[0]["context_bundle_id"], context_bundle["context_bundle_id"])
        self.assertEqual(memory_uses[0]["memory_id"], "memory-phase18-adapter-contract-001")

    def test_external_adapter_candidate_is_pending_human_review_no_auto_modify(self) -> None:
        candidate = self.fixture["events"]["memory_candidates"][0]

        self.assertEqual(candidate["status"], "pending")
        self.assertTrue(candidate["requires_human_review"])
        self.assertTrue(candidate["metadata"]["no_auto_modify"])
        self.assertEqual(candidate["proposed_action"], "review_external_memory_adapter_for_future_use")

    def test_provider_source_refs_are_official_or_local_evidence_refs(self) -> None:
        manifests = self.fixture["metadata"]["adapter_manifests"]
        source_text = "\n".join(ref for manifest in manifests for ref in manifest["source_refs"])

        self.assertIn("https://docs.mem0.ai/api-reference", source_text)
        self.assertIn("https://help.getzep.com/quick-start-guide", source_text)
        self.assertIn("https://hindsight.vectorize.io", source_text)
        self.assertIn("https://openviking.ai", source_text)
        self.assertIn("https://reme.agentscope.io", source_text)
        self.assertIn("律师助理 Bot 的 Agent 记忆组件选型研究.md", source_text)
        self.assertIn("packages/platform-runtime/src/platform_runtime/memory_adapters.py", source_text)

    def test_lawyer_research_candidates_keep_explicit_roles_and_gates(self) -> None:
        manifests = {item["provider"]: item for item in self.fixture["metadata"]["adapter_manifests"]}

        self.assertEqual(
            manifests["hindsight"]["candidate_role"],
            "audit_focused_recall_retain_reflect_spike",
        )
        self.assertIn("license_review", manifests["openviking"]["required_gates"])
        self.assertIn("concurrency_permission_review", manifests["reme"]["required_gates"])

    def test_fixture_is_reference_first_and_privacy_safe(self) -> None:
        text = json.dumps(self.fixture, ensure_ascii=False, sort_keys=True)
        self.assertIn("raw_payload_ref", text)
        self.assertIn("fixture://", text)
        self.assertIn("adapter://", text)
        self.assertIn("memory://", text)

        for object_path, value in iter_mapping_values(self.fixture):
            with self.subTest(path=object_path):
                self.assertEqual(RAW_PAYLOAD_KEYS & set(value), set())

        for text_path, value in iter_string_values(self.fixture):
            with self.subTest(path=text_path):
                for pattern in FORBIDDEN_TEXT_PATTERNS:
                    self.assertIsNone(pattern.search(value), f"{text_path} matched {pattern.pattern}")

    def test_prepared_local_verification_commands_are_documented(self) -> None:
        commands = self.fixture["metadata"]["verification_commands"]

        self.assertTrue(any("test_memory_adapter_contract.py" in command for command in commands))
        self.assertTrue(any("test_phase18_external_memory_adapter_acceptance.py" in command for command in commands))
        self.assertTrue(any("test_schema_validation.py" in command for command in commands))


def iter_mapping_values(value: Any, path: str = "$") -> Iterable[tuple[str, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        yield path, value
        for key, item in value.items():
            yield from iter_mapping_values(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_mapping_values(item, f"{path}[{index}]")


def iter_string_values(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield from iter_string_values(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_string_values(item, f"{path}[{index}]")


if __name__ == "__main__":
    unittest.main()
