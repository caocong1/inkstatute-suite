"""Mode 4 fixture — Adversarial (3 agents + synthesis + adversarial).

Provides ``make_mode4_fixtures()`` returning a dict with:
- ``config``: ``ArenaWorkflowConfig`` with ``mode="mode4_adversarial"``,
  3 agent slots
- ``adapters``: dict mapping each slot to a ``MockACPBackendAdapter`` with
  self-score responses and cross-review responses containing ``[FINDING]``
  blocks
- ``synthesis_adapter``: separate ``MockACPBackendAdapter`` with a
  ``backend_family`` different from all agent slots
- ``adversarial_adapter``: separate ``MockACPBackendAdapter`` with a
  ``backend_family`` different from all agent slots and the synthesis
  adapter; responses include ``[FINDING]`` blocks with weakness-finding
  content

All ``backend_family`` values are distinct across slots, synthesis, and
adversarial adapters.

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
        "severity: Medium\n"
        "confirmed: true\n"
        "[/FINDING]"
    )


def _adversarial_no_finding_response() -> str:
    """Adversarial response with no [FINDING] blocks — no issues found.

    This causes convergence: score >= 8 and zero high-severity findings.
    """
    return "未发现严重问题。综合回答质量良好。"


def make_mode4_fixtures() -> dict:
    """Return Mode 4 fixtures: config, adapters, synthesis, adversarial."""
    config = ArenaWorkflowConfig(
        arena_id="e2e-mode4",
        mode="mode4_adversarial",
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
        responses=["自评分数：8/10\n综合最终版本：合同审查报告"],
        agent_slot="synthesis",
    )

    adversarial_adapter = MockACPBackendAdapter(
        backend_id="mock-adversarial",
        backend_family="adversarial-family",
        responses=[_adversarial_no_finding_response()],
        agent_slot="adversarial",
    )

    return {
        "config": config,
        "adapters": adapters,
        "synthesis_adapter": synthesis_adapter,
        "adversarial_adapter": adversarial_adapter,
    }


# ---------------------------------------------------------------------------
# Fixture self-tests
# ---------------------------------------------------------------------------


class Mode4FixtureTests(unittest.TestCase):
    """Verify Mode 4 fixture structure."""

    def test_config_mode_and_slots(self) -> None:
        fixtures = make_mode4_fixtures()
        config = fixtures["config"]
        self.assertEqual(config.mode, "mode4_adversarial")
        self.assertEqual(config.agent_slots, ["slot-0", "slot-1", "slot-2"])
        self.assertEqual(config.task_instruction, _TASK)
        self.assertEqual(config.max_rounds, 3)

    def test_adapters_distinct_families(self) -> None:
        fixtures = make_mode4_fixtures()
        adapters = fixtures["adapters"]
        families = {adapter.backend_family() for adapter in adapters.values()}
        self.assertEqual(len(families), 3)

    def test_adapters_include_finding_blocks(self) -> None:
        fixtures = make_mode4_fixtures()
        adapters = fixtures["adapters"]
        for slot in _SLOTS:
            adapter = adapters[slot]
            self.assertIsInstance(adapter, MockACPBackendAdapter)
            self.assertEqual(adapter._agent_slot, slot)
            finding_resp = adapter._responses[-1]
            self.assertIn("[FINDING]", finding_resp)
            self.assertIn("[/FINDING]", finding_resp)

    def test_synthesis_adapter_separate_family(self) -> None:
        fixtures = make_mode4_fixtures()
        adapters = fixtures["adapters"]
        synthesis = fixtures["synthesis_adapter"]
        self.assertIsNotNone(synthesis)
        self.assertIsInstance(synthesis, MockACPBackendAdapter)
        slot_families = {a.backend_family() for a in adapters.values()}
        self.assertNotIn(synthesis.backend_family(), slot_families)

    def test_adversarial_adapter_separate_family(self) -> None:
        fixtures = make_mode4_fixtures()
        adapters = fixtures["adapters"]
        synthesis = fixtures["synthesis_adapter"]
        adversarial = fixtures["adversarial_adapter"]
        self.assertIsNotNone(adversarial)
        self.assertIsInstance(adversarial, MockACPBackendAdapter)
        slot_families = {a.backend_family() for a in adapters.values()}
        self.assertNotIn(adversarial.backend_family(), slot_families)
        self.assertNotIn(adversarial.backend_family(), {synthesis.backend_family()})

    def test_all_families_distinct(self) -> None:
        fixtures = make_mode4_fixtures()
        adapters = fixtures["adapters"]
        synthesis = fixtures["synthesis_adapter"]
        adversarial = fixtures["adversarial_adapter"]
        all_families = (
            {a.backend_family() for a in adapters.values()}
            | {synthesis.backend_family()}
            | {adversarial.backend_family()}
        )
        self.assertEqual(len(all_families), 5)

    def test_agent_slots_match_config(self) -> None:
        fixtures = make_mode4_fixtures()
        config = fixtures["config"]
        adapters = fixtures["adapters"]
        for slot in config.agent_slots:
            self.assertIn(slot, adapters)
            self.assertEqual(adapters[slot]._agent_slot, slot)


if __name__ == "__main__":
    unittest.main()
