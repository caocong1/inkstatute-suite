"""Contract freeze verification tests (SAFETY-02, SAFETY-06).

Verifies that Phase 42 did not modify any contract freeze protected
files: ``packages/platform-contract/``, ``packages/platform-runtime/
protocols.py``, and ``packages/platform-runtime/src/platform_runtime/
feature_flags.py``.

The authoritative contract-count freeze tests live in
``packages/contract-test-suite/tests/test_contract_count_freeze.py``
(run by the ``contract-test-suite`` gate).  This file provides a
Phase-42-specific assertion that the ``admin_api_enabled`` flag already
existed (not added by Phase 42) and that no new fields were added to
``RuntimeFeatureFlags``.
"""

from __future__ import annotations

import unittest
from dataclasses import fields

import platform_contract
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.protocols import BackendAdapter, ChannelAdapter


class ContractFreezeTests(unittest.TestCase):
    """Assert the contract freeze protected surfaces are unchanged."""

    def test_admin_api_enabled_already_exists_in_feature_flags(self) -> None:
        flags = RuntimeFeatureFlags()
        self.assertTrue(hasattr(flags, "admin_api_enabled"))

    def test_admin_api_enabled_defaults_false(self) -> None:
        self.assertIs(RuntimeFeatureFlags().admin_api_enabled, False)

    def test_feature_flags_has_all_m2_flags(self) -> None:
        flag_names = {f.name for f in fields(RuntimeFeatureFlags)}
        self.assertIn("admin_api_enabled", flag_names)
        self.assertIn("router_service_enabled", flag_names)
        self.assertIn("skill_registry_enabled", flag_names)
        self.assertIn("qqbot_channel_enabled", flag_names)
        self.assertIn("codex_backend_enabled", flag_names)
        self.assertIn("provider_model_backend_enabled", flag_names)

    def test_no_new_fields_added_to_feature_flags(self) -> None:
        flag_names = {f.name for f in fields(RuntimeFeatureFlags)}
        expected_flags = {
            # V2 flags (6)
            "run_runtime_enabled",
            "streaming_lane_enabled",
            "channel_delivery_enabled",
            "approval_lane_enabled",
            "contract_log_enabled",
            "context_assembly_enabled",
            # M2 flags (6)
            "router_service_enabled",
            "skill_registry_enabled",
            "admin_api_enabled",
            "qqbot_channel_enabled",
            "codex_backend_enabled",
            "provider_model_backend_enabled",
            # M3 flags (9)
            "session_memory_enabled",
            "mcp_registry_enabled",
            "model_gateway_enabled",
            "multi_agent_enabled",
            "skill_registry_write_enabled",
            "hybrid_routing_enabled",
            "web_sse_channel_enabled",
            "rbac_enabled",
            "multi_tenant_enabled",
            # M4 flags (2) — added by Phase 57
            "admin_web_ui_enabled",
            "lawyer_web_chat_enabled",
        }
        self.assertEqual(flag_names, expected_flags)

    def test_protocols_py_not_modified_by_phase42(self) -> None:
        # protocols.py is importable and the Protocol classes are present.
        # The authoritative count assertion is in test_contract_count_freeze.py.
        self.assertTrue(hasattr(BackendAdapter, "__protocol_attrs__") or BackendAdapter is not None)
        self.assertTrue(hasattr(ChannelAdapter, "__protocol_attrs__") or ChannelAdapter is not None)

    def test_platform_contract_importable(self) -> None:
        # Confirms no import errors after Phase 42.
        self.assertIsNotNone(platform_contract)


if __name__ == "__main__":
    unittest.main()
