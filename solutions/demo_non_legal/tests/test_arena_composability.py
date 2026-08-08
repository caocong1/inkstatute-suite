"""Arena event composability tests for the demo_non_legal solution.

Verifies that arena lifecycle event payloads contain NO legal-specific
fields in top-level required positions (GATE-02).  Arena events must be
industry-neutral — the same event vocabulary serves legal and non-legal
domains.  ``metadata.agent_slot`` is the generic demultiplexing key and
is not legal-specific.
"""

from __future__ import annotations

import dataclasses
import unittest
from dataclasses import fields
from typing import Any

from platform_contract.arena_contract import ArenaWorkflowConfig
from platform_contract.enums import RunEventType
from platform_contract.unified_events import (
    ArenaAdversarialChallengeCompletedPayload,
    ArenaEarlyStopTriggeredPayload,
    ArenaReviewCompletedPayload,
    ArenaScoreRecordedPayload,
    ArenaSynthesisCompletedPayload,
    ArenaSynthesisStartedPayload,
    ArenaWorkflowCompletedPayload,
    ArenaWorkflowStartedPayload,
)

# Legal-specific keywords that must never appear as field names in
# platform-level (industry-neutral) schemas.
LEGAL_KEYWORDS = frozenset(
    {"lawyer", "legal", "lawfirm", "attorney", "counsel", "statute", "fagui", "wenshu"}
)

# ArenaMode values as defined in packages/platform-sdk-ts/src/events.ts.
ARENA_MODE_VALUES = ("standard", "self_score", "arena_review", "adversarial")


def _required_fields(dataclass_cls: type) -> set[str]:
    """Return the set of field names that have no default value.

    A field is *required* when it has neither ``default`` nor
    ``default_factory`` (i.e. both are ``dataclasses.MISSING``).
    """
    return {
        f.name
        for f in fields(dataclass_cls)
        if f.default is dataclasses.MISSING
        and f.default_factory is dataclasses.MISSING  # type: ignore[misc]
    }


def _walk(prefix: str, value: Any) -> list[str]:
    """Recursively check *value* for legal-specific field names.

    Same pattern as ``test_demo_non_legal_solution.py`` lines 75-86,
    but checks against the expanded ``LEGAL_KEYWORDS`` set.
    """
    hits: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k.lower() in LEGAL_KEYWORDS:
                hits.append(f"{prefix}.{k}" if prefix else k)
            hits.extend(_walk(f"{prefix}.{k}" if prefix else str(k), v))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            hits.extend(_walk(f"{prefix}[{i}]", v))
    return hits


class ArenaComposabilityTests(unittest.TestCase):
    """Arena lifecycle events are industry-neutral (GATE-02)."""

    # -- Test 1: ArenaWorkflowStartedPayload --------------------------------

    def test_arena_workflow_started_no_legal_fields(self) -> None:
        required = _required_fields(ArenaWorkflowStartedPayload)
        self.assertEqual(required, {"arena_id", "mode"})
        self.assertEqual(required & LEGAL_KEYWORDS, set())

    # -- Test 2: ArenaScoreRecordedPayload ----------------------------------

    def test_arena_score_recorded_no_legal_fields(self) -> None:
        required = _required_fields(ArenaScoreRecordedPayload)
        self.assertEqual(required, {"arena_id", "agent_slot", "round", "score"})
        self.assertEqual(required & LEGAL_KEYWORDS, set())

    # -- Test 3: ArenaReviewCompletedPayload --------------------------------

    def test_arena_review_completed_no_legal_fields(self) -> None:
        required = _required_fields(ArenaReviewCompletedPayload)
        self.assertEqual(
            required, {"arena_id", "reviewer_slot", "reviewed_slot", "round"}
        )
        self.assertEqual(required & LEGAL_KEYWORDS, set())

    # -- Test 4: ArenaSynthesis events --------------------------------------

    def test_arena_synthesis_events_no_legal_fields(self) -> None:
        for cls in (ArenaSynthesisStartedPayload, ArenaSynthesisCompletedPayload):
            with self.subTest(cls=cls.__name__):
                required = _required_fields(cls)
                self.assertEqual(required, {"arena_id", "round"})
                self.assertEqual(required & LEGAL_KEYWORDS, set())

    # -- Test 5: ArenaAdversarialChallengeCompletedPayload ------------------

    def test_arena_adversarial_challenge_no_legal_fields(self) -> None:
        required = _required_fields(ArenaAdversarialChallengeCompletedPayload)
        self.assertEqual(
            required,
            {"arena_id", "challenger_slot", "challenged_slot", "round"},
        )
        self.assertEqual(required & LEGAL_KEYWORDS, set())

    # -- Test 6: ArenaEarlyStopTriggeredPayload ------------------------------

    def test_arena_early_stop_no_legal_fields(self) -> None:
        required = _required_fields(ArenaEarlyStopTriggeredPayload)
        self.assertEqual(required, {"arena_id", "reason", "round"})
        self.assertEqual(required & LEGAL_KEYWORDS, set())

    # -- Test 7: ArenaWorkflowConfig ----------------------------------------

    def test_arena_workflow_config_no_legal_fields(self) -> None:
        required = _required_fields(ArenaWorkflowConfig)
        self.assertEqual(
            required,
            {"arena_id", "mode", "agent_slots", "task_instruction"},
        )
        self.assertEqual(required & LEGAL_KEYWORDS, set())

    # -- Test 8: ArenaMode values are not legal-specific ---------------------

    def test_arena_mode_values_not_legal_specific(self) -> None:
        for mode in ARENA_MODE_VALUES:
            with self.subTest(mode=mode):
                for keyword in LEGAL_KEYWORDS:
                    self.assertNotIn(keyword, mode.lower())

    # -- Test 9: Full arena event sequence is composable ---------------------

    def test_arena_events_composable_with_demo_non_legal(self) -> None:
        """A minimal arena event sequence contains no legal-specific
        field names at any level (recursive check)."""
        sequence = [
            {
                "event_type": RunEventType.ARENA_WORKFLOW_STARTED.value,
                "payload": dataclasses.asdict(
                    ArenaWorkflowStartedPayload(
                        arena_id="demo-arena-1",
                        mode="standard",
                        agent_slots=["slot-a", "slot-b"],
                        metadata={"agent_slot": "slot-a"},
                    )
                ),
            },
            {
                "event_type": RunEventType.ARENA_SCORE_RECORDED.value,
                "payload": dataclasses.asdict(
                    ArenaScoreRecordedPayload(
                        arena_id="demo-arena-1",
                        agent_slot="slot-a",
                        round=1,
                        score=85,
                        metadata={"agent_slot": "slot-a"},
                    )
                ),
            },
            {
                "event_type": RunEventType.ARENA_REVIEW_COMPLETED.value,
                "payload": dataclasses.asdict(
                    ArenaReviewCompletedPayload(
                        arena_id="demo-arena-1",
                        reviewer_slot="slot-b",
                        reviewed_slot="slot-a",
                        round=1,
                        findings=[],
                        metadata={"agent_slot": "slot-b"},
                    )
                ),
            },
            {
                "event_type": RunEventType.ARENA_SYNTHESIS_COMPLETED.value,
                "payload": dataclasses.asdict(
                    ArenaSynthesisCompletedPayload(
                        arena_id="demo-arena-1",
                        round=1,
                        metadata={"agent_slot": "slot-a"},
                    )
                ),
            },
            {
                "event_type": RunEventType.ARENA_WORKFLOW_COMPLETED.value,
                "payload": dataclasses.asdict(
                    ArenaWorkflowCompletedPayload(
                        arena_id="demo-arena-1",
                        mode="standard",
                        status="completed",
                        agent_slots=["slot-a", "slot-b"],
                        metadata={"agent_slot": "slot-a"},
                    )
                ),
            },
        ]
        hits = _walk("", sequence)
        self.assertEqual(hits, [], f"Legal-specific fields found: {hits}")

    # -- Test 10: metadata.agent_slot is not legal-specific ------------------

    def test_metadata_agent_slot_is_not_legal_specific(self) -> None:
        self.assertNotIn("agent_slot", LEGAL_KEYWORDS)


if __name__ == "__main__":
    unittest.main()
