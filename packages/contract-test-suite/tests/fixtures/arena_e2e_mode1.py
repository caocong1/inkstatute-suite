"""Mode 1 fixture — Standard Parallel (3 agents, no synthesis).

Provides ``make_mode1_fixtures()`` returning a dict with:
- ``config``: ``ArenaWorkflowConfig`` with ``mode="mode1_parallel"``, 3 agent slots
- ``adapters``: dict mapping each slot to a ``MockACPBackendAdapter`` with
  distinct ``backend_id`` and ``backend_family`` values
- ``synthesis_adapter``: ``None`` (Mode 1 has no synthesis)

GATE-01: E2E integration tests use these fixtures with the full
arena-service HTTP + SSE stack — no real LLM calls.
"""

from __future__ import annotations

import unittest

from arena_engine.mock_acp import MockACPBackendAdapter
from platform_contract.arena_contract import ArenaWorkflowConfig

_TASK = "分析合同效力并提出修改建议"
_SLOTS = ["slot-0", "slot-1", "slot-2"]


def make_mode1_fixtures() -> dict:
    """Return Mode 1 fixtures: config, adapters, synthesis_adapter=None."""
    config = ArenaWorkflowConfig(
        arena_id="e2e-mode1",
        mode="mode1_parallel",
        agent_slots=list(_SLOTS),
        task_instruction=_TASK,
        max_rounds=3,
    )

    adapters: dict[str, MockACPBackendAdapter] = {}
    for i, slot in enumerate(_SLOTS):
        adapters[slot] = MockACPBackendAdapter(
            backend_id=f"mock-{slot}",
            backend_family=f"family-{i}",
            responses=[f"Mode1 result from {slot}"],
            agent_slot=slot,
        )

    return {
        "config": config,
        "adapters": adapters,
        "synthesis_adapter": None,
        "adversarial_adapter": None,
    }


# ---------------------------------------------------------------------------
# Fixture self-tests
# ---------------------------------------------------------------------------


class Mode1FixtureTests(unittest.TestCase):
    """Verify Mode 1 fixture structure."""

    def test_config_mode_and_slots(self) -> None:
        fixtures = make_mode1_fixtures()
        config = fixtures["config"]
        self.assertEqual(config.mode, "mode1_parallel")
        self.assertEqual(config.agent_slots, ["slot-0", "slot-1", "slot-2"])
        self.assertEqual(config.task_instruction, _TASK)
        self.assertEqual(config.max_rounds, 3)

    def test_adapters_are_mock_acp_with_distinct_families(self) -> None:
        fixtures = make_mode1_fixtures()
        adapters = fixtures["adapters"]
        self.assertEqual(len(adapters), 3)
        families = set()
        for i, slot in enumerate(_SLOTS):
            adapter = adapters[slot]
            self.assertIsInstance(adapter, MockACPBackendAdapter)
            self.assertEqual(adapter.backend_id(), f"mock-{slot}")
            self.assertEqual(adapter.backend_family(), f"family-{i}")
            self.assertEqual(adapter._agent_slot, slot)
            families.add(adapter.backend_family())
        self.assertEqual(len(families), 3)

    def test_synthesis_adapter_is_none(self) -> None:
        fixtures = make_mode1_fixtures()
        self.assertIsNone(fixtures["synthesis_adapter"])

    def test_agent_slots_match_config(self) -> None:
        fixtures = make_mode1_fixtures()
        config = fixtures["config"]
        adapters = fixtures["adapters"]
        for slot in config.agent_slots:
            self.assertIn(slot, adapters)
            self.assertEqual(adapters[slot]._agent_slot, slot)


if __name__ == "__main__":
    unittest.main()
