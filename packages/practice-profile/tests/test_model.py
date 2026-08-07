"""Tests for PracticeProfile dataclass (model.py)."""

from __future__ import annotations

import dataclasses
import unittest

from inkstatute_practice_profile import PracticeProfile


class PracticeProfileDataclassTests(unittest.TestCase):
    def test_is_frozen_dataclass_with_slots(self) -> None:
        p = PracticeProfile(tenant_id="t1", plugin="commercial-legal")
        self.assertTrue(dataclasses.is_dataclass(p))
        # frozen
        with self.assertRaises(dataclasses.FrozenInstanceError):
            p.tenant_id = "t2"  # type: ignore[misc]
        # slots — no __dict__
        with self.assertRaises(AttributeError):
            p.__dict__  # type: ignore[attr-defined]

    def test_all_expected_fields_present(self) -> None:
        field_names = {f.name for f in dataclasses.fields(PracticeProfile)}
        expected = {
            "tenant_id",
            "plugin",
            "identity",
            "user_role",
            "integrations",
            "escalation_matrix",
            "document_style",
            "shared_guardrails",
            "plugin_configs",
            "temporary_mode",
            "updated_at",
        }
        self.assertEqual(field_names, expected)

    def test_header_fields_are_json_objects(self) -> None:
        p = PracticeProfile(
            tenant_id="t1",
            plugin="commercial-legal",
            identity={"org_name": "某律所"},
            user_role={"role": "律师"},
            integrations={"contract_mgmt": "已连接"},
            escalation_matrix={"policy": "不自动升级"},
            document_style={"revision_tone": "半正式"},
            shared_guardrails={"jurisdiction_identification": "中国大陆法律"},
        )
        self.assertIsInstance(p.identity, dict)
        self.assertIsInstance(p.user_role, dict)
        self.assertIsInstance(p.integrations, dict)
        self.assertIsInstance(p.escalation_matrix, dict)
        self.assertIsInstance(p.document_style, dict)
        self.assertIsInstance(p.shared_guardrails, dict)

    def test_plugin_configs_is_dict_of_json_objects(self) -> None:
        p = PracticeProfile(
            tenant_id="t1",
            plugin="commercial-legal",
            plugin_configs={
                "commercial-legal": {"审查立场": {"风险偏好": "平衡型"}},
                "litigation-legal": {"风险校准": {"severity": "高"}},
            },
        )
        self.assertIsInstance(p.plugin_configs, dict)
        self.assertIsInstance(p.plugin_configs["commercial-legal"], dict)
        self.assertEqual(
            p.plugin_configs["commercial-legal"]["审查立场"]["风险偏好"],
            "平衡型",
        )

    def test_defaults(self) -> None:
        p = PracticeProfile(tenant_id="t1", plugin="commercial-legal")
        self.assertEqual(p.identity, {})
        self.assertEqual(p.user_role, {})
        self.assertEqual(p.integrations, {})
        self.assertEqual(p.escalation_matrix, {})
        self.assertEqual(p.document_style, {})
        self.assertEqual(p.shared_guardrails, {})
        self.assertEqual(p.plugin_configs, {})
        self.assertFalse(p.temporary_mode)
        self.assertIsNone(p.updated_at)

    def test_to_json_serializes_all_fields(self) -> None:
        p = PracticeProfile(
            tenant_id="t1",
            plugin="commercial-legal",
            identity={"org_name": "某律所"},
            user_role={"role": "律师"},
            integrations={"contract_mgmt": "已连接"},
            escalation_matrix={"policy": "不自动升级"},
            document_style={"revision_tone": "半正式"},
            shared_guardrails={"jurisdiction_identification": "中国大陆法律"},
            plugin_configs={"commercial-legal": {"风险偏好": "平衡型"}},
            temporary_mode=True,
            updated_at="2026-08-11T00:00:00Z",
        )
        j = p.to_json()
        self.assertEqual(j["tenant_id"], "t1")
        self.assertEqual(j["plugin"], "commercial-legal")
        self.assertEqual(j["identity"], {"org_name": "某律所"})
        self.assertEqual(j["user_role"], {"role": "律师"})
        self.assertEqual(j["integrations"], {"contract_mgmt": "已连接"})
        self.assertEqual(j["escalation_matrix"], {"policy": "不自动升级"})
        self.assertEqual(j["document_style"], {"revision_tone": "半正式"})
        self.assertEqual(
            j["shared_guardrails"],
            {"jurisdiction_identification": "中国大陆法律"},
        )
        self.assertEqual(
            j["plugin_configs"],
            {"commercial-legal": {"风险偏好": "平衡型"}},
        )
        self.assertTrue(j["temporary_mode"])
        self.assertEqual(j["updated_at"], "2026-08-11T00:00:00Z")

    def test_from_json_round_trip_lossless(self) -> None:
        p = PracticeProfile(
            tenant_id="t1",
            plugin="commercial-legal",
            identity={"org_name": "某律所"},
            user_role={"role": "律师"},
            integrations={"contract_mgmt": "已连接"},
            escalation_matrix={"policy": "不自动升级"},
            document_style={"revision_tone": "半正式"},
            shared_guardrails={"jurisdiction_identification": "中国大陆法律"},
            plugin_configs={"commercial-legal": {"风险偏好": "平衡型"}},
            temporary_mode=True,
            updated_at="2026-08-11T00:00:00Z",
        )
        p2 = PracticeProfile.from_json(p.to_json())
        self.assertEqual(p, p2)

    def test_temporary_mode_flag_serializes_correctly(self) -> None:
        p = PracticeProfile(
            tenant_id="t1",
            plugin="commercial-legal",
            temporary_mode=True,
        )
        j = p.to_json()
        self.assertTrue(j["temporary_mode"])
        p2 = PracticeProfile.from_json(j)
        self.assertTrue(p2.temporary_mode)

    def test_plugin_configs_defaults_to_empty_dict(self) -> None:
        p = PracticeProfile(tenant_id="t1", plugin="commercial-legal")
        self.assertEqual(p.plugin_configs, {})


if __name__ == "__main__":
    unittest.main()
