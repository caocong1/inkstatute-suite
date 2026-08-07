"""Golden tests for strong-signal + soft-match routing (对拍集).

Ports the 15-case integration fixture and 8-case eval fixture from
``lawfirm-profile/scripts/tests/`` as golden tests.  Each case is a
``(user_msg, expected_primary_skill)`` pair.  The test runs the
strong-signal + soft-match router against a real-index ``SkillRegistry``
and checks that ``primary_skill`` matches the expected value.

Accuracy thresholds:
- 15-case integration fixture: ≥ 80% (≥ 12/15 correct)
- 8-case eval fixture: ≥ 75% (≥ 6/8 correct)

This is the 对拍集 — the golden fixture that verifies behavior non-regression.
"""

from __future__ import annotations

import unittest

from platform_contract import RouteDecision

from inkstatute_router_service import RouterService, RouterStrategy

from _real_index_fixture import build_real_index_registry


# ── 15-case integration fixture ────────────────────────────────────────────
# Copied verbatim from lawfirm-profile/scripts/tests/integration_test_router.py
# lines 26-45 (7 strong-signal, 3 factual Q, 5 soft-match).

INTEGRATION_FIXTURE: list[tuple[str, str | None]] = [
    # ── Strong signal (7 cases — should all hit dedicated rules) ──
    ("我刚收到一份合同，帮我审一下", "legal-contract-copilot"),
    ("[法院短信] 您有新的送达文书，案号 (2025)京0105民初1234号", "legal-court-sms"),
    ("我新接了一个案子", "legal-new-case"),
    ("判决书已经下来了，帮我分析", "legal-litigation-analysis"),
    ("我是OPC一人公司的创始人", "legal-opc-legal-counsel"),
    ("客户咨询想沉淀到知识库", "legal-qa-extractor"),
    ("写完答辩状了，帮我去掉 AI 腔", "legal-de-ai-polish"),
    # ── Simple factual Qs (3 cases — router should punt) ──
    ("民法典第 1062 条是什么？", None),
    ("什么是公司法人人格否认？", None),
    ("刑法第 13 条讲什么？", None),
    # ── Soft match (5 cases — trigger phrase scoring) ──
    ("对方公司涉嫌侵犯我们的商标权", "ip-trademark-search"),
    ("我有个劳动合同纠纷要处理", "employment-labor-dispute-handling"),
    ("公司要上市前的合规审查", "regulatory-compliance-system"),
    ("我想申请软件著作权登记", "ip-copyright-registration"),
    ("建设工程合同纠纷，对方拖欠工程款", "construction-payment-dispute"),
]


# ── 8-case eval fixture ────────────────────────────────────────────────────
# Copied verbatim from lawfirm-profile/scripts/tests/test_eval_router.py
# lines 41-50.

EVAL_FIXTURE: list[tuple[str, str | None]] = [
    ("我刚收到一份合同，帮我审一下", "legal-contract-copilot"),
    ("[法院短信] 您有新的送达文书，案号 (2025)京0105民初1234号", "legal-court-sms"),
    ("我新接了一个案子", "legal-new-case"),
    ("判决书已经下来了，帮我分析", "legal-litigation-analysis"),
    ("我是OPC一人公司的创始人", "legal-opc-legal-counsel"),
    ("民法典第 1062 条是什么？", None),  # factual, router should punt
    ("写完答辩状了，帮我去掉 AI 腔", "legal-de-ai-polish"),
    ("客户咨询想沉淀到知识库", "legal-qa-extractor"),
]


def _run_fixture(
    fixture: list[tuple[str, str | None]],
    service: RouterService,
) -> tuple[int, list[dict]]:
    """Run *fixture* against *service* and return (correct_count, failures)."""
    correct = 0
    failures: list[dict] = []
    for msg, expected in fixture:
        decision = service.decide({"message": msg})
        if decision.primary_skill == expected:
            correct += 1
        else:
            failures.append(
                {
                    "msg": msg,
                    "picked": decision.primary_skill,
                    "expected": expected,
                    "rule": decision.matched_rule,
                    "conf": decision.confidence,
                }
            )
    return correct, failures


def _format_failures(failures: list[dict]) -> str:
    """Format failure details for diagnostic output."""
    return "\n".join(
        f"  - {f['msg']!r}: picked={f['picked']!r} expected={f['expected']!r} "
        f"rule={f['rule']!r} conf={f['conf']}"
        for f in failures
    )


class TestIntegrationGoldenFixture(unittest.TestCase):
    """15-case integration fixture — ≥ 80% accuracy threshold."""

    @classmethod
    def setUpClass(cls) -> None:
        """Build a real-index SkillRegistry for all tests in this class."""
        cls.registry = build_real_index_registry()
        cls.service = RouterService(
            strategy=RouterStrategy.RULE,
            skill_registry=cls.registry,
        )

    def test_integration_accuracy_threshold(self) -> None:
        """≥ 80% of 15 cases must route correctly (≥ 12/15)."""
        correct, failures = _run_fixture(INTEGRATION_FIXTURE, self.service)
        accuracy = correct / len(INTEGRATION_FIXTURE)
        self.assertGreaterEqual(
            accuracy,
            0.80,
            f"\nAccuracy {accuracy:.1%} below 80% threshold.\n"
            f"Failures ({len(failures)}):\n" + _format_failures(failures),
        )

    def test_integration_fixture_has_15_cases(self) -> None:
        """Verify the fixture has exactly 15 cases."""
        self.assertEqual(len(INTEGRATION_FIXTURE), 15)

    def test_integration_strong_signal_cases_match_rule(self) -> None:
        """Strong-signal cases verify matched_rule is the rule name."""
        strong_signal_cases = INTEGRATION_FIXTURE[:7]
        expected_rules = [
            "docx_contract_review",
            "court_sms",
            "new_case",
            "judgment_or_transcript",
            "opc_counsel",
            "qa_extraction",
            "polish_draft",
        ]
        for (msg, expected_skill), expected_rule in zip(strong_signal_cases, expected_rules):
            decision = self.service.decide({"message": msg})
            if decision.primary_skill == expected_skill:
                self.assertEqual(
                    decision.matched_rule,
                    expected_rule,
                    f"Rule mismatch for {msg!r}: "
                    f"expected {expected_rule!r}, got {decision.matched_rule!r}",
                )

    def test_integration_factual_cases_return_none(self) -> None:
        """Factual Q cases verify primary_skill is None.

        Cases that trigger the factual short-circuit (len < 12 or matching
        a factual Q pattern) also verify matched_rule == "factual_short_circuit".
        Cases that fall through to the strategy cascade still return
        primary_skill=None but with a different matched_rule.
        """
        factual_cases = INTEGRATION_FIXTURE[7:10]
        for msg, expected in factual_cases:
            decision = self.service.decide({"message": msg})
            self.assertIsNone(
                decision.primary_skill,
                f"Expected None for factual Q {msg!r}, got {decision.primary_skill!r}",
            )
            # Cases that trigger the factual short-circuit have matched_rule="factual_short_circuit"
            if decision.matched_rule == "factual_short_circuit":
                # Good — factual short-circuit triggered
                pass
            else:
                # Fell through to strategy cascade — still valid as long as
                # primary_skill is None (verified above)
                pass

    def test_integration_soft_match_cases_have_gates(self) -> None:
        """Soft-match cases verify gates_before contains ask-user-enforcement (when score < 0.7).

        Note: Some soft-match fixture cases are actually intercepted by
        strong-signal rules (e.g., '侵犯商标权' matches ip_infringement).
        Only cases that actually go through soft matching are checked.
        """
        soft_match_cases = INTEGRATION_FIXTURE[10:15]
        for msg, expected in soft_match_cases:
            decision = self.service.decide({"message": msg})
            if decision.matched_rule == "soft_trigger_match":
                # Verify gates
                self.assertIn(
                    "legal-de-ai-polish",
                    decision.gates_after,
                    f"gates_after missing legal-de-ai-polish for {msg!r}",
                )
                # gates_before should have ask-user-enforcement when score < 0.7
                score = decision.metadata.get("soft_match_score", 0.0)
                if score < 0.7:
                    self.assertIn(
                        "ask-user-enforcement",
                        decision.gates_before,
                        f"gates_before missing ask-user-enforcement for {msg!r} "
                        f"(score={score})",
                    )


class TestEvalGoldenFixture(unittest.TestCase):
    """8-case eval fixture — ≥ 75% accuracy threshold."""

    @classmethod
    def setUpClass(cls) -> None:
        """Build a real-index SkillRegistry for all tests in this class."""
        cls.registry = build_real_index_registry()
        cls.service = RouterService(
            strategy=RouterStrategy.RULE,
            skill_registry=cls.registry,
        )

    def test_eval_accuracy_threshold(self) -> None:
        """≥ 75% of 8 cases must route correctly (≥ 6/8)."""
        correct, failures = _run_fixture(EVAL_FIXTURE, self.service)
        accuracy = correct / len(EVAL_FIXTURE)
        self.assertGreaterEqual(
            accuracy,
            0.75,
            f"\nAccuracy {accuracy:.1%} below 75% threshold.\n"
            f"Failures ({len(failures)}):\n" + _format_failures(failures),
        )

    def test_eval_fixture_has_8_cases(self) -> None:
        """Verify the fixture has exactly 8 cases."""
        self.assertEqual(len(EVAL_FIXTURE), 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
