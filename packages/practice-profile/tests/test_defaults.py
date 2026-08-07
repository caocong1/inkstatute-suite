"""Tests for temporary mode defaults (defaults.py)."""

from __future__ import annotations

import unittest

from inkstatute_practice_profile import (
    TEMPORARY_MODE_TAG,
    PracticeProfile,
    create_temporary_profile,
)


class TemporaryModeTagTests(unittest.TestCase):
    def test_tag_value(self) -> None:
        self.assertEqual(
            TEMPORARY_MODE_TAG,
            "[临时模式 — 配置你的档案以获得定制输出]",
        )


class CreateTemporaryProfileTests(unittest.TestCase):
    def test_returns_practice_profile_with_temporary_mode(self) -> None:
        p = create_temporary_profile("t1", "commercial-legal")
        self.assertIsInstance(p, PracticeProfile)
        self.assertTrue(p.temporary_mode)
        self.assertEqual(p.tenant_id, "t1")
        self.assertEqual(p.plugin, "commercial-legal")

    def test_user_role_is_lawyer(self) -> None:
        p = create_temporary_profile("t1", "commercial-legal")
        self.assertEqual(p.user_role["role"], "律师")

    def test_jurisdiction_identification(self) -> None:
        p = create_temporary_profile("t1", "commercial-legal")
        self.assertEqual(
            p.shared_guardrails["jurisdiction_identification"],
            "中国大陆法律",
        )

    def test_document_style_half_formal_with_statute_no_case(self) -> None:
        p = create_temporary_profile("t1", "commercial-legal")
        self.assertIn("半正式", p.document_style["revision_tone"])
        self.assertIn("法条引用", p.document_style["citation_style"])
        self.assertFalse(p.document_style["case_citation"])

    def test_escalation_matrix_no_auto_escalation(self) -> None:
        p = create_temporary_profile("t1", "commercial-legal")
        self.assertIn("不自动升级", p.escalation_matrix["policy"])

    def test_plugin_configs_risk_appetite_balanced(self) -> None:
        p = create_temporary_profile("t1", "commercial-legal")
        self.assertEqual(
            p.plugin_configs["commercial-legal"]["风险偏好"],
            "平衡型",
        )

    def test_plugin_configs_party_stance(self) -> None:
        p = create_temporary_profile("t1", "commercial-legal")
        self.assertEqual(
            p.plugin_configs["commercial-legal"]["甲方立场"],
            "标记常见风险，不偏向任何一方",
        )
        self.assertEqual(
            p.plugin_configs["commercial-legal"]["乙方立场"],
            "标记常见风险，不偏向任何一方",
        )

    def test_works_for_non_commercial_legal_plugin(self) -> None:
        p = create_temporary_profile("t2", "litigation-legal")
        self.assertEqual(p.plugin, "litigation-legal")
        self.assertIn("litigation-legal", p.plugin_configs)
        self.assertEqual(
            p.plugin_configs["litigation-legal"]["风险偏好"],
            "平衡型",
        )

    def test_works_for_arbitrary_plugin_name(self) -> None:
        p = create_temporary_profile("t3", "data-compliance")
        self.assertEqual(p.plugin, "data-compliance")
        self.assertIn("data-compliance", p.plugin_configs)


if __name__ == "__main__":
    unittest.main()
