from __future__ import annotations

import copy
import json
import unittest
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from contract_test_suite.fixture_replay import assert_platform_foundation_relationships
from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import load_schemas, validate_event_bundle


PHASE10_FIXTURE_PATH = LOCAL_FIXTURE_ROOT / "phase10_runruntime_fake_backend.json"
ASYNC_TASK_STATES = {
    "queued",
    "running",
    "waiting_for_user",
    "succeeded",
    "failed",
    "cancelled",
}
RAW_PAYLOAD_KEYS = {
    "raw_payload",
    "raw_text",
    "payload_text",
    "full_text",
    "document_text",
    "customer_document_text",
    "case_facts",
}
SENSITIVE_TEXT_MARKERS = {
    "secret",
    "token",
    "password",
    "customer document",
    "client name",
    "legal payload",
    "original leak",
}
POLICY_EVIDENCE_KEYS = {
    "action",
    "rule_id",
    "input_hash_prefix",
    "input_length",
    "privacy",
}


class Phase10RunRuntimeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixture = json.loads(PHASE10_FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fixture_validates_and_relationships_replay(self) -> None:
        validate_event_bundle(self.fixture, self.schemas)
        assert_platform_foundation_relationships(self.fixture, PHASE10_FIXTURE_PATH)

        events = self.fixture["events"]
        run_id = events["run"]["run_id"]
        turn_id = events["agent_turn"]["turn_id"]
        result_id = events["agent_result"]["result_id"]
        delivery_id = events["channel_delivery"]["delivery_id"]
        artifact_ids = {artifact["artifact_id"] for artifact in events["artifact_records"]}
        step_ids = {step["step_id"] for step in events["run_steps"]}

        self.assertEqual(events["channel_message"]["run_id"], run_id)
        self.assertEqual(events["run"]["channel_message_id"], events["channel_message"]["message_id"])
        self.assertEqual(events["run"]["turn_id"], turn_id)
        self.assertEqual(events["agent_result"]["metadata"]["run_id"], run_id)
        self.assertEqual(events["channel_delivery"]["run_id"], run_id)
        self.assertEqual(events["channel_delivery"]["result_id"], result_id)
        self.assertEqual(events["feedback_event"]["feedback_target"], delivery_id)

        for event in events["run_events"]:
            self.assertEqual(event["run_id"], run_id)
            if "step_id" in event:
                self.assertIn(event["step_id"], step_ids)
            if "artifact_id" in event:
                self.assertIn(event["artifact_id"], artifact_ids)

        for artifact in events["agent_result"]["artifacts"]:
            self.assertIn(artifact["artifact_id"], artifact_ids)
        for artifact in events["channel_delivery"]["artifacts"]:
            self.assertIn(artifact["artifact_id"], artifact_ids)

    def test_run_status_and_event_sequence_are_locked(self) -> None:
        events = self.fixture["events"]
        self.assertIn(events["run"]["status"], ASYNC_TASK_STATES)

        seq_values = [event["seq"] for event in events["run_events"]]
        self.assertEqual(seq_values, list(range(len(seq_values))))

        mutated = copy.deepcopy(self.fixture)
        mutated["events"]["run_events"][2]["seq"] = 7
        with self.assertRaisesRegex(AssertionError, r"gap-free"):
            assert_gap_free_run_event_sequence(mutated)

    def test_no_raw_payload_fields_or_sensitive_payload_text(self) -> None:
        for object_path, value in iter_mapping_values(self.fixture):
            with self.subTest(path=object_path):
                forbidden_keys = RAW_PAYLOAD_KEYS & set(value)
                self.assertEqual(forbidden_keys, set(), f"{object_path} has raw payload-like keys")

        for text_path, value in iter_string_values(self.fixture):
            normalized = value.lower()
            with self.subTest(path=text_path):
                for marker in SENSITIVE_TEXT_MARKERS:
                    self.assertNotIn(marker, normalized)

        mutated = copy.deepcopy(self.fixture)
        mutated["events"]["run"]["raw_payload"] = {"unsafe": True}
        with self.assertRaisesRegex(AssertionError, r"raw_payload"):
            assert_no_raw_payload_like_keys(mutated)

    def test_output_policy_evidence_is_sanitized_hash_only(self) -> None:
        events = self.fixture["events"]
        policy_events = [
            event
            for event in events["run_events"]
            if isinstance(event.get("metadata"), Mapping) and "output_policy" in event["metadata"]
        ]
        self.assertEqual(len(policy_events), 2)

        allowed, blocked = policy_events
        self.assertEqual(allowed["metadata"]["output_policy"]["action"], "allow")
        self.assertIn("message_delta", allowed)
        self.assertEqual(blocked["metadata"]["output_policy"]["action"], "block")
        self.assertNotIn("message_delta", blocked)
        self.assertIs(blocked["metadata"]["visible_text_removed"], True)

        for event in policy_events:
            evidence = event["metadata"]["output_policy"]
            self.assertEqual(set(evidence), POLICY_EVIDENCE_KEYS)
            self.assertRegex(evidence["input_hash_prefix"], r"^[0-9a-f]{12}$")
            self.assertIsInstance(evidence["input_length"], int)
            self.assertEqual(evidence["privacy"], "no_original_blocked_text_stored")

        top_level_evidence = self.fixture["metadata"]["output_policy_evidence"]
        self.assertEqual(set(top_level_evidence["allowed_delta"]), POLICY_EVIDENCE_KEYS | {"event_id"})
        self.assertEqual(set(top_level_evidence["blocked_delta"]), POLICY_EVIDENCE_KEYS | {"event_id"})

    def test_embedded_zero_channel_metadata_and_not_live_claims(self) -> None:
        metadata = self.fixture["metadata"]
        run_metadata = self.fixture["events"]["run"]["metadata"]
        delivery_metadata = self.fixture["events"]["channel_delivery"]["metadata"]

        for value in (metadata, run_metadata, delivery_metadata):
            self.assertEqual(value["channels"], [])
            self.assertEqual(value["server"], "none")
            self.assertIs(value["not_live_acceptance"], True)

        self.assertEqual(metadata["runtime_mode"], "embedded")
        self.assertEqual(metadata["backend"], "fake")
        self.assertEqual(metadata["backend_adapter"], "FakeBackendAdapter")
        self.assertEqual(self.fixture["events"]["channel_delivery"]["status"], "suppressed")

        mutated = copy.deepcopy(self.fixture)
        mutated["metadata"]["channels"] = ["web"]
        with self.assertRaisesRegex(AssertionError, r"channels"):
            assert_embedded_zero_channel_metadata(mutated)


def assert_gap_free_run_event_sequence(fixture: Mapping[str, Any]) -> None:
    seq_values = [event["seq"] for event in fixture["events"]["run_events"]]
    expected = list(range(len(seq_values)))
    if seq_values != expected:
        raise AssertionError(f"run_events seq values must be gap-free from 0: expected {expected}, got {seq_values}")


def assert_no_raw_payload_like_keys(fixture: Mapping[str, Any]) -> None:
    for object_path, value in iter_mapping_values(fixture):
        forbidden_keys = RAW_PAYLOAD_KEYS & set(value)
        if forbidden_keys:
            raise AssertionError(f"{object_path} has raw payload-like keys: {sorted(forbidden_keys)}")


def assert_embedded_zero_channel_metadata(fixture: Mapping[str, Any]) -> None:
    metadata = fixture["metadata"]
    if metadata.get("channels") != []:
        raise AssertionError(f"metadata.channels must be []: {metadata.get('channels')!r}")
    if metadata.get("server") != "none":
        raise AssertionError(f"metadata.server must be none: {metadata.get('server')!r}")
    if metadata.get("not_live_acceptance") is not True:
        raise AssertionError("metadata.not_live_acceptance must be true")


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
