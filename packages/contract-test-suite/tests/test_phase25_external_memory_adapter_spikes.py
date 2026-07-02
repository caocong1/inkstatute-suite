"""Contract tests for Phase 25 external memory adapter spikes and final recommendation fixture."""

from __future__ import annotations

import json
import re
import unittest
from collections.abc import Iterable, Mapping
from typing import Any

from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle


PHASE25_FIXTURE = LOCAL_FIXTURE_ROOT / "phase25_external_memory_adapter_spikes.json"

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
    re.compile(r"(^|\s)/(new|resume|help|status|memory)\b", re.IGNORECASE),
)


class Phase25ExternalAdapterSpikesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixture = json.loads(PHASE25_FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_id_and_schema_validation(self) -> None:
        self.assertEqual(
            self.fixture["fixture_id"],
            "phase25-external-memory-adapter-spikes-001",
        )
        validate_event_bundle(self.fixture, self.schemas)

    def test_spike_evaluation_evidence_documents_all_xmem_requirements(self) -> None:
        """spike_evaluation_evidence must document XMEM-01..XMEM-05."""
        evidence = self.fixture["metadata"]["spike_evaluation_evidence"]

        self.assertTrue(evidence["xmem_01_zep_style_evaluated_via_adapter_boundary"])
        self.assertTrue(evidence["xmem_02_reme_style_evaluated_via_adapter_boundary"])
        self.assertTrue(evidence["xmem_03_mem0_style_poc_not_legal_production_default"])
        self.assertTrue(evidence["xmem_04_all_manifests_document_required_fields"])
        self.assertTrue(evidence["xmem_05_recommendation_produced_with_evidence"])
        self.assertAlmostEqual(evidence["native_baseline_score"], 1.0)
        self.assertTrue(evidence["all_spike_specs_sanitized_fixture_only"])

    def test_three_spike_comparisons_present(self) -> None:
        """XMEM-01/02/03: fixture must include all three candidate spike comparisons."""
        comparisons = self.fixture["metadata"]["spike_comparisons"]
        candidate_ids = {c["candidate_id"] for c in comparisons}

        self.assertIn("zep_style_graph", candidate_ids)
        self.assertIn("reme_style_file_auditable", candidate_ids)
        self.assertIn("mem0_style_quick_poc", candidate_ids)

    def test_xmem04_comparison_fields_present(self) -> None:
        """XMEM-04: each comparison must document deployment_model, data_residency, secrets, raw_payload_blocked, tenant_isolation, delete_export_support."""
        required_fields = [
            "deployment_model", "data_residency", "secrets_required",
            "raw_payload_blocked", "tenant_isolation", "delete_export_support",
        ]
        for comp in self.fixture["metadata"]["spike_comparisons"]:
            with self.subTest(candidate=comp["candidate_id"]):
                for field in required_fields:
                    self.assertIn(field, comp, f"{comp['candidate_id']} missing {field!r}")

    def test_zep_style_not_approved_due_to_raw_payload(self) -> None:
        """XMEM-01: Zep-style raw_payload_blocked=False must result in keep_native."""
        zep = next(c for c in self.fixture["metadata"]["spike_comparisons"] if c["candidate_id"] == "zep_style_graph")
        self.assertFalse(zep["raw_payload_blocked"])
        self.assertEqual(zep["recommended_action"], "keep_native")

    def test_mem0_not_approved_no_tenant_isolation(self) -> None:
        """XMEM-03: Mem0-style must be keep_native due to no_built_in tenant isolation."""
        mem0 = next(c for c in self.fixture["metadata"]["spike_comparisons"] if c["candidate_id"] == "mem0_style_quick_poc")
        self.assertEqual(mem0["tenant_isolation"], "no_built_in")
        self.assertEqual(mem0["recommended_action"], "keep_native")

    def test_final_recommendation_present_and_valid(self) -> None:
        """XMEM-05: final_recommendation must be non-empty with rationale and evidence_refs."""
        rec = self.fixture["metadata"]["final_recommendation"]

        self.assertGreater(len(rec["recommended_default"]), 0)
        self.assertGreater(len(rec["rationale"]), 20)
        self.assertGreater(len(rec["evidence_refs"]), 0)

        valid_prefixes = ("platform_native_only", "defer_all_external", "add_")
        self.assertTrue(
            any(rec["recommended_default"].startswith(p) for p in valid_prefixes),
            f"Unexpected recommendation: {rec['recommended_default']!r}",
        )

    def test_final_recommendation_evidence_refs_are_uris(self) -> None:
        """XMEM-05: evidence_refs must all be URI strings."""
        for ref in self.fixture["metadata"]["final_recommendation"]["evidence_refs"]:
            self.assertIn("://", ref, f"evidence_ref must be a URI, got {ref!r}")

    def test_trace_metadata_records_candidates_and_recommendation(self) -> None:
        """XMEM-05: execution_trace metadata must record candidates_evaluated and recommendation."""
        trace_meta = self.fixture["events"]["execution_trace"]["metadata"]

        self.assertEqual(trace_meta["candidates_evaluated"], 3)
        self.assertGreater(len(trace_meta["recommended_default"]), 0)

    def test_fixture_is_privacy_safe(self) -> None:
        """No forbidden raw payload keys or secret-like values."""
        for object_path, value in iter_mapping_values(self.fixture):
            with self.subTest(path=object_path):
                forbidden = RAW_PAYLOAD_KEYS & set(value)
                self.assertEqual(forbidden, set(), f"{object_path}: forbidden keys {forbidden}")

        for text_path, value in iter_string_values(self.fixture):
            with self.subTest(path=text_path):
                for pattern in FORBIDDEN_TEXT_PATTERNS:
                    self.assertIsNone(
                        pattern.search(value),
                        f"{text_path} matched forbidden pattern {pattern.pattern!r}",
                    )

    def test_verification_commands_cover_required_files(self) -> None:
        commands = self.fixture["metadata"]["verification_commands"]

        self.assertTrue(any("test_memory_adapter_spikes.py" in cmd for cmd in commands))
        self.assertTrue(any("test_phase25_external_memory_adapter_spikes.py" in cmd for cmd in commands))
        self.assertTrue(any("test_schema_validation.py" in cmd for cmd in commands))


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
