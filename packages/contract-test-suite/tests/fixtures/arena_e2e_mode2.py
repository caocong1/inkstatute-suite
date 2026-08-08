"""Mode 2 fixture — Self-score Iteration (2 agents, self-scoring).

Provides ``make_mode2_fixtures()`` returning a dict with:
- ``config``: ``ArenaWorkflowConfig`` with ``mode="mode2_iteration"``, 2 agent slots
- ``adapters``: dict mapping each slot to a ``MockACPBackendAdapter`` with
  self-score responses (responses include ``[SCORE]`` blocks and a
  parseable ``自评分数`` score for the self-scoring iteration)
- ``synthesis_adapter``: ``None`` (Mode 2 has no synthesis)

GATE-01: E2E integration tests use these fixtures with the full
arena-service HTTP + SSE stack — no real LLM calls.
"""

from __future__ import annotations

import unittest

from arena_engine.mock_acp import MockACPBackendAdapter
from platform_contract.arena_contract import ArenaWorkflowConfig

_TASK = "分析合同效力并提出修改建议"
_SLOTS = ["slot-0", "slot-1"]


def _scored_response(score: int, round: int, slot: str) -> str:
    """Build a self-score response with a parseable score and [SCORE] marker."""
    return (
        f"[SCORE] round={round}\n"
        f"自评分数：{score}/10\n"
        f"result from {slot}"
    )


def make_mode2_fixtures() -> dict:
    """Return Mode 2 fixtures: config, adapters, synthesis_adapter=None."""
    config = ArenaWorkflowConfig(
        arena_id="e2e-mode2",
        mode="mode2_iteration",
        agent_slots=list(_SLOTS),
        task_instruction=_TASK,
        max_rounds=3,
    )

    adapters: dict[str, MockACPBackendAdapter] = {}
    for i, slot in enumerate(_SLOTS):
        adapters[slot] = MockACPBackendAdapter(
            backend_id=f"mock-{slot}",
            backend_family=f"family-{i}",
            responses=[
                _scored_response(7, 1, slot),
                _scored_response(8, 2, slot),
                _scored_response(9, 3, slot),
            ],
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


class Mode2FixtureTests(unittest.TestCase):
    """Verify Mode 2 fixture structure."""

    def test_config_mode_and_slots(self) -> None:
        fixtures = make_mode2_fixtures()
        config = fixtures["config"]
        self.assertEqual(config.mode, "mode2_iteration")
        self.assertEqual(config.agent_slots, ["slot-0", "slot-1"])
        self.assertEqual(config.task_instruction, _TASK)
        self.assertEqual(config.max_rounds, 3)

    def test_adapters_have_score_responses(self) -> None:
        fixtures = make_mode2_fixtures()
        adapters = fixtures["adapters"]
        self.assertEqual(len(adapters), 2)
        for slot in _SLOTS:
            adapter = adapters[slot]
            self.assertIsInstance(adapter, MockACPBackendAdapter)
            self.assertEqual(adapter._agent_slot, slot)
            # Each adapter has 3 scored responses (for 3 rounds)
            self.assertEqual(len(adapter._responses), 3)
            for resp in adapter._responses:
                self.assertIn("[SCORE]", resp)
                self.assertIn("自评分数", resp)

    def test_adapters_distinct_families(self) -> None:
        fixtures = make_mode2_fixtures()
        adapters = fixtures["adapters"]
        families = {adapter.backend_family() for adapter in adapters.values()}
        self.assertEqual(len(families), 2)

    def test_synthesis_adapter_is_none(self) -> None:
        fixtures = make_mode2_fixtures()
        self.assertIsNone(fixtures["synthesis_adapter"])

    def test_agent_slots_match_config(self) -> None:
        fixtures = make_mode2_fixtures()
        config = fixtures["config"]
        adapters = fixtures["adapters"]
        for slot in config.agent_slots:
            self.assertIn(slot, adapters)
            self.assertEqual(adapters[slot]._agent_slot, slot)


if __name__ == "__main__":
    unittest.main()
