"""Tests for ArtifactStore — reference-first structured output persistence."""

from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from arena_engine.artifact_store import ArtifactStore, RoundArtifact


class ArtifactStoreTests(unittest.TestCase):
    """Cover all 6 ArtifactStore behaviours from Plan 107-02 Task 1."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.storage_dir = self._tmp.name
        self.store = ArtifactStore(storage_dir=self.storage_dir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # Test 1 — store_round_output returns RoundArtifact with raw_payload_ref
    # as a file path and the file exists on disk as JSON
    def test_store_round_output_returns_artifact_with_file_path_ref(self) -> None:
        artifact = self.store.store_round_output(
            arena_id="a-1",
            agent_slot="slot-0",
            round=1,
            content="legal analysis text",
            metadata={"score": 8},
        )
        self.assertIsInstance(artifact, RoundArtifact)
        self.assertEqual(artifact.arena_id, "a-1")
        self.assertEqual(artifact.agent_slot, "slot-0")
        self.assertEqual(artifact.round, 1)
        self.assertEqual(artifact.content, "legal analysis text")
        self.assertEqual(artifact.metadata, {"score": 8})
        # raw_payload_ref is a file path, not the content
        self.assertTrue(artifact.raw_payload_ref.endswith("round_1.json"))
        self.assertNotEqual(artifact.raw_payload_ref, "legal analysis text")
        # The file exists on disk
        ref_path = Path(artifact.raw_payload_ref)
        self.assertTrue(ref_path.exists())
        # The file is valid JSON
        data = json.loads(ref_path.read_text(encoding="utf-8"))
        self.assertEqual(data["content"], "legal analysis text")

    # Test 2 — get_artifact returns the same RoundArtifact with content
    def test_get_artifact_reconstructs_from_disk(self) -> None:
        self.store.store_round_output(
            arena_id="a-1",
            agent_slot="slot-0",
            round=1,
            content="legal analysis text",
            metadata={"score": 8},
        )
        artifact = self.store.get_artifact(
            arena_id="a-1", agent_slot="slot-0", round=1
        )
        self.assertIsNotNone(artifact)
        assert artifact is not None  # for type checker
        self.assertEqual(artifact.content, "legal analysis text")
        self.assertEqual(artifact.arena_id, "a-1")
        self.assertEqual(artifact.agent_slot, "slot-0")
        self.assertEqual(artifact.round, 1)
        self.assertEqual(artifact.metadata, {"score": 8})

    # Test 3 — second store overwrites first; get_artifact returns second
    def test_store_overwrites_same_key(self) -> None:
        self.store.store_round_output(
            arena_id="a-1",
            agent_slot="slot-0",
            round=1,
            content="first content",
        )
        self.store.store_round_output(
            arena_id="a-1",
            agent_slot="slot-0",
            round=1,
            content="second content",
        )
        artifact = self.store.get_artifact(
            arena_id="a-1", agent_slot="slot-0", round=1
        )
        self.assertIsNotNone(artifact)
        assert artifact is not None
        self.assertEqual(artifact.content, "second content")

    # Test 4 — list_round_artifacts returns all slots for a round
    def test_list_round_artifacts_returns_all_slots(self) -> None:
        self.store.store_round_output(
            arena_id="a-1", agent_slot="slot-0", round=1, content="alpha"
        )
        self.store.store_round_output(
            arena_id="a-1", agent_slot="slot-1", round=1, content="beta"
        )
        self.store.store_round_output(
            arena_id="a-1", agent_slot="slot-2", round=1, content="gamma"
        )
        artifacts = self.store.list_round_artifacts(arena_id="a-1", round=1)
        self.assertEqual(len(artifacts), 3)
        slots = {a.agent_slot for a in artifacts}
        self.assertEqual(slots, {"slot-0", "slot-1", "slot-2"})

    # Test 5 — RoundArtifact is frozen slotted dataclass
    def test_round_artifact_is_frozen(self) -> None:
        artifact = self.store.store_round_output(
            arena_id="a-1", agent_slot="slot-0", round=1, content="text"
        )
        with self.assertRaises((AttributeError, dataclasses.FrozenInstanceError)):
            artifact.content = "mutated"  # type: ignore[misc]

    # Test 6 — stored JSON contains content but raw_payload_ref is a path
    def test_reference_first_logging(self) -> None:
        artifact = self.store.store_round_output(
            arena_id="a-1", agent_slot="slot-0", round=1, content="legal analysis text"
        )
        ref_path = Path(artifact.raw_payload_ref)
        data = json.loads(ref_path.read_text(encoding="utf-8"))
        # The JSON file on disk contains the content field
        self.assertIn("content", data)
        self.assertEqual(data["content"], "legal analysis text")
        # The raw_payload_ref in the returned artifact is a file path, not content
        self.assertTrue(str(ref_path).endswith(".json"))
        self.assertNotIn("legal analysis text", artifact.raw_payload_ref)


if __name__ == "__main__":
    unittest.main()
