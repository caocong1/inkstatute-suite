"""Arena fixture replay tests — CONTRACT-04.

Validates Arena event streams via JSON Schema validation, seq-based
sorting/resume (deterministic, no duplicates, no loss), and industry-
neutrality checks for non-legal Arena fixtures.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from contract_test_suite.event_stream_replay import (
    resume_from_seq,
    sort_events_by_seq,
)
from contract_test_suite.paths import LOCAL_FIXTURE_ROOT
from contract_test_suite.schema_validation import (
    FORBIDDEN_TOP_LEVEL_FIELDS,
    _validate_schema,
    load_schemas,
)


def _load_raw_records(path: Path) -> list[dict]:
    """Load JSONL lines as raw dicts (envelope + event payload)."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class ArenaFixtureReplayTests(unittest.TestCase):
    """Validate Arena fixture replay: deterministic, no duplicates, no loss."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.arena_stream = LOCAL_FIXTURE_ROOT / "arena_event_stream.jsonl"
        cls.arena_non_legal_stream = LOCAL_FIXTURE_ROOT / "arena_non_legal_event_stream.jsonl"

    # ------------------------------------------------------------------
    # 1. Fixture files exist
    # ------------------------------------------------------------------

    def test_arena_fixture_file_exists(self) -> None:
        """Both Arena fixture JSONL files must exist."""
        self.assertTrue(self.arena_stream.exists(), f"Missing fixture: {self.arena_stream}")
        self.assertTrue(
            self.arena_non_legal_stream.exists(),
            f"Missing fixture: {self.arena_non_legal_stream}",
        )

    # ------------------------------------------------------------------
    # 2. Correct seq order after sorting
    # ------------------------------------------------------------------

    def test_arena_event_stream_has_correct_seq_order(self) -> None:
        """sort_events_by_seq produces seq [0..8] for the Arena stream."""
        records = _load_raw_records(self.arena_stream)
        sorted_records = sort_events_by_seq(records)
        seqs = [r["seq"] for r in sorted_records]
        self.assertEqual(seqs, [0, 1, 2, 3, 4, 5, 6, 7, 8])

    # ------------------------------------------------------------------
    # 3. No duplicate seq values
    # ------------------------------------------------------------------

    def test_arena_event_stream_no_duplicate_seq(self) -> None:
        """All seq values in the Arena stream are unique."""
        records = _load_raw_records(self.arena_stream)
        seqs = [r["seq"] for r in records]
        self.assertEqual(len(set(seqs)), len(seqs))

    # ------------------------------------------------------------------
    # 4. resume_from_seq: no duplicates, no loss
    # ------------------------------------------------------------------

    def test_arena_event_stream_resume_from_seq_no_duplicates_no_loss(self) -> None:
        """resume_from_seq produces correct subsets with no duplicates/loss."""
        records = _load_raw_records(self.arena_stream)
        sorted_records = sort_events_by_seq(records)

        # Resume from seq 3 → events with seq > 3 = [4, 5, 6, 7, 8]
        resumed = resume_from_seq(sorted_records, 3)
        resumed_seqs = [r["seq"] for r in resumed]
        self.assertEqual(resumed_seqs, [4, 5, 6, 7, 8])
        self.assertEqual(len(resumed), 5)
        # No duplicates
        self.assertEqual(len(set(resumed_seqs)), len(resumed_seqs))

        # Resume from seq -1 → all 9 events
        resumed_all = resume_from_seq(sorted_records, -1)
        self.assertEqual(len(resumed_all), 9)
        self.assertEqual([r["seq"] for r in resumed_all], [0, 1, 2, 3, 4, 5, 6, 7, 8])

    # ------------------------------------------------------------------
    # 5. All events validate against their schemas
    # ------------------------------------------------------------------

    def test_arena_event_stream_all_events_validate_against_schemas(self) -> None:
        """Every Arena event payload validates against its JSON Schema."""
        records = _load_raw_records(self.arena_stream)
        for record in records:
            event_key = record["event_key"]
            event = record["event"]
            schema_name = event_key.replace(".", "_")
            with self.subTest(event_key=event_key, seq=record["seq"]):
                self.assertIn(
                    schema_name,
                    self.schemas,
                    f"No schema found for event_key {event_key!r} (looked for {schema_name!r})",
                )
                _validate_schema(
                    self.schemas[schema_name],
                    event,
                    self.schemas,
                    path=(schema_name,),
                )

    # ------------------------------------------------------------------
    # 6. Non-legal stream validates without legal-specific fields
    # ------------------------------------------------------------------

    def test_arena_non_legal_stream_validates_without_legal_fields(self) -> None:
        """Non-legal Arena events validate and have no forbidden top-level fields."""
        records = _load_raw_records(self.arena_non_legal_stream)
        for record in records:
            event_key = record["event_key"]
            event = record["event"]
            schema_name = event_key.replace(".", "_")
            with self.subTest(event_key=event_key, seq=record["seq"]):
                self.assertIn(schema_name, self.schemas)
                _validate_schema(
                    self.schemas[schema_name],
                    event,
                    self.schemas,
                    path=(schema_name,),
                )
                # No forbidden top-level fields in the event dict
                forbidden_present = set(event) & FORBIDDEN_TOP_LEVEL_FIELDS
                self.assertFalse(
                    forbidden_present,
                    f"{event_key} has forbidden top-level fields: {sorted(forbidden_present)}",
                )

    # ------------------------------------------------------------------
    # 7. Deterministic replay — same input produces same output
    # ------------------------------------------------------------------

    def test_arena_event_stream_deterministic_replay(self) -> None:
        """Loading the Arena stream twice produces identical results."""
        load1 = _load_raw_records(self.arena_stream)
        load2 = _load_raw_records(self.arena_stream)

        sorted1 = sort_events_by_seq(load1)
        sorted2 = sort_events_by_seq(load2)

        # Identical seq lists
        seqs1 = [r["seq"] for r in sorted1]
        seqs2 = [r["seq"] for r in sorted2]
        self.assertEqual(seqs1, seqs2)

        # Identical event dicts
        events1 = [r["event"] for r in sorted1]
        events2 = [r["event"] for r in sorted2]
        self.assertEqual(events1, events2)


if __name__ == "__main__":
    unittest.main()
