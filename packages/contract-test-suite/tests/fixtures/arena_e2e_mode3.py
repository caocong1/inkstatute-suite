"""Mode 3 fixture — Arena Review (3 cross-family agents + synthesis).

Provides ``make_mode3_fixtures()`` returning a dict with:
- ``config``: ``ArenaWorkflowConfig`` with ``mode="mode3_arena_review"``,
  3 agent slots with cross-family backends
- ``adapters``: dict mapping each slot to a ``MockACPBackendAdapter`` with
  self-score responses and cross-review responses containing ``[FINDING]``
  blocks matching the ``_parse_review_findings`` format in ``review.py``
- ``synthesis_adapter``: separate ``MockACPBackendAdapter`` with a
  ``backend_family`` different from all agent slots

GATE-01: E2E integration tests use these fixtures with the full
arena-service HTTP + SSE stack — no real LLM calls.
"""

from __future__ import annotations

import unittest

from arena_engine.mock_acp import MockACPBackendAdapter
from platform_contract.arena_contract import ArenaWorkflowConfig

_TASK = "分析合同效力并提出修改建议"
_SLOTS = ["slot-0", "slot-1", "slot-2"]


def _scored_response(score: int, slot: str) -> str:
    """Build a self-score response with a parseable score."""
    return f"自评分数：{score}/10\n分析结果 from {slot}"


def _finding_response(description: str) -> str:
    """Build a cross-review response with a [FINDING] block."""
    return (
        "[FINDING]\n"
        f"description: {description}\n"
        "confidence: Likely\n"
        "severity: High\n"
        "confirmed: true\n"
        "[/FINDING]"
    )


def make_mode3_fixtures() -> dict:
    """Return Mode 3 fixtures: config, adapters, synthesis_adapter."""
    config = ArenaWorkflowConfig(
        arena_id="e2e-mode3",
        mode="mode3_arena_review",
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
                _scored_response(8, slot),
                _scored_response(8, slot),
                _scored_response(8, slot),
                _finding_response(f"合同第{i + 1}条缺少违约责任条款 from {slot}"),
            ],
            agent_slot=slot,
        )

    synthesis_adapter = MockACPBackendAdapter(
        backend_id="mock-synthesis",
        backend_family="synthesis-family",
        responses=["综合最终版本：合同审查报告"],
        agent_slot="synthesis",
    )

    return {
        "config": config,
        "adapters": adapters,
        "synthesis_adapter": synthesis_adapter,
        "adversarial_adapter": None,
    }


# ---------------------------------------------------------------------------
# Fixture self-tests
# ---------------------------------------------------------------------------


class Mode3FixtureTests(unittest.TestCase):
    """Verify Mode 3 fixture structure."""

    def test_config_mode_and_slots(self) -> None:
        fixtures = make_mode3_fixtures()
        config = fixtures["config"]
        self.assertEqual(config.mode, "mode3_arena_review")
        self.assertEqual(config.agent_slots, ["slot-0", "slot-1", "slot-2"])
        self.assertEqual(config.task_instruction, _TASK)
        self.assertEqual(config.max_rounds, 3)

    def test_adapters_distinct_families(self) -> None:
        fixtures = make_mode3_fixtures()
        adapters = fixtures["adapters"]
        families = {adapter.backend_family() for adapter in adapters.values()}
        self.assertEqual(len(families), 3)

    def test_adapters_include_finding_blocks(self) -> None:
        fixtures = make_mode3_fixtures()
        adapters = fixtures["adapters"]
        for slot in _SLOTS:
            adapter = adapters[slot]
            self.assertIsInstance(adapter, MockACPBackendAdapter)
            self.assertEqual(adapter._agent_slot, slot)
            # Last response is the cross-review with [FINDING]
            finding_resp = adapter._responses[-1]
            self.assertIn("[FINDING]", finding_resp)
            self.assertIn("description:", finding_resp)
            self.assertIn("confidence:", finding_resp)
            self.assertIn("severity:", finding_resp)
            self.assertIn("confirmed:", finding_resp)
            self.assertIn("[/FINDING]", finding_resp)

    def test_synthesis_adapter_separate_family(self) -> None:
        fixtures = make_mode3_fixtures()
        adapters = fixtures["adapters"]
        synthesis = fixtures["synthesis_adapter"]
        self.assertIsNotNone(synthesis)
        self.assertIsInstance(synthesis, MockACPBackendAdapter)
        slot_families = {a.backend_family() for a in adapters.values()}
        self.assertNotIn(synthesis.backend_family(), slot_families)
        self.assertEqual(synthesis.backend_family(), "synthesis-family")

    def test_agent_slots_match_config(self) -> None:
        fixtures = make_mode3_fixtures()
        config = fixtures["config"]
        adapters = fixtures["adapters"]
        for slot in config.agent_slots:
            self.assertIn(slot, adapters)
            self.assertEqual(adapters[slot]._agent_slot, slot)


if __name__ == "__main__":
    unittest.main()
