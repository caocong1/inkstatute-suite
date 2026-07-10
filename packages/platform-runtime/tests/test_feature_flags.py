from __future__ import annotations

import unittest
from dataclasses import fields

from platform_runtime import RuntimeFeatureDisabledError, RuntimeFeatureFlags


class RuntimeFeatureFlagsTests(unittest.TestCase):
    def test_all_runtime_lanes_default_to_false(self) -> None:
        flags = RuntimeFeatureFlags()

        self.assertFalse(flags.run_runtime_enabled)
        self.assertFalse(flags.streaming_lane_enabled)
        self.assertFalse(flags.channel_delivery_enabled)
        self.assertFalse(flags.approval_lane_enabled)
        self.assertFalse(flags.contract_log_enabled)
        self.assertFalse(flags.context_assembly_enabled)
        self.assertFalse(flags.router_service_enabled)
        self.assertFalse(flags.skill_registry_enabled)
        self.assertFalse(flags.admin_api_enabled)
        self.assertFalse(flags.qqbot_channel_enabled)
        self.assertFalse(flags.codex_backend_enabled)
        self.assertFalse(flags.provider_model_backend_enabled)

    def test_all_flags_default_to_false_via_introspection(self) -> None:
        default_flags = RuntimeFeatureFlags()

        for field in fields(RuntimeFeatureFlags):
            with self.subTest(flag=field.name):
                self.assertFalse(getattr(default_flags, field.name))

    def test_explicit_opt_in_satisfies_require_enabled(self) -> None:
        flags = RuntimeFeatureFlags(run_runtime_enabled=True)

        flags.require_enabled("run_runtime_enabled")

    def test_disabled_flag_raises_package_error(self) -> None:
        flags = RuntimeFeatureFlags()

        with self.assertRaisesRegex(
            RuntimeFeatureDisabledError,
            "runtime feature flag disabled: run_runtime_enabled",
        ):
            flags.require_enabled("run_runtime_enabled")

    def test_unknown_flag_raises_deterministic_error(self) -> None:
        flags = RuntimeFeatureFlags()

        with self.assertRaisesRegex(
            RuntimeFeatureDisabledError,
            "unknown runtime feature flag: missing_lane",
        ):
            flags.require_enabled("missing_lane")


class M3FeatureFlagDefaultTests(unittest.TestCase):
    """Verify all 9 M3 feature flags default to False and require_enabled gates them."""

    M3_FLAGS = (
        "session_memory_enabled",
        "mcp_registry_enabled",
        "model_gateway_enabled",
        "multi_agent_enabled",
        "skill_registry_write_enabled",
        "hybrid_routing_enabled",
        "web_sse_channel_enabled",
        "rbac_enabled",
        "multi_tenant_enabled",
    )

    def test_all_m3_flags_default_false(self) -> None:
        flags = RuntimeFeatureFlags()
        for flag_name in self.M3_FLAGS:
            with self.subTest(flag=flag_name):
                self.assertIs(getattr(flags, flag_name), False)

    def test_all_m3_flags_require_enabled_raises_when_false(self) -> None:
        flags = RuntimeFeatureFlags()
        for flag_name in self.M3_FLAGS:
            with self.subTest(flag=flag_name):
                with self.assertRaises(RuntimeFeatureDisabledError):
                    flags.require_enabled(flag_name)

    def test_all_m3_flags_require_enabled_passes_when_true(self) -> None:
        for flag_name in self.M3_FLAGS:
            with self.subTest(flag=flag_name):
                kwargs = {flag_name: True}
                flags = RuntimeFeatureFlags(**kwargs)
                flags.require_enabled(flag_name)

    def test_all_m3_flags_field_exists(self) -> None:
        field_names = {f.name for f in fields(RuntimeFeatureFlags)}
        for flag_name in self.M3_FLAGS:
            with self.subTest(flag=flag_name):
                self.assertIn(flag_name, field_names)



class OperatorConfigFeatureFlagTests(unittest.TestCase):
    """CFG-02: operator_config_enabled defaults OFF and is gated by require_enabled."""

    FLAG = "operator_config_enabled"

    def test_operator_config_enabled_defaults_false(self) -> None:
        flags = RuntimeFeatureFlags()
        self.assertIs(flags.operator_config_enabled, False)

    def test_operator_config_require_enabled_raises_when_false(self) -> None:
        flags = RuntimeFeatureFlags()
        with self.assertRaisesRegex(
            RuntimeFeatureDisabledError,
            "runtime feature flag disabled: operator_config_enabled",
        ):
            flags.require_enabled(self.FLAG)

    def test_operator_config_require_enabled_passes_when_true(self) -> None:
        flags = RuntimeFeatureFlags(operator_config_enabled=True)
        flags.require_enabled(self.FLAG)

    def test_operator_config_flag_field_exists(self) -> None:
        field_names = {f.name for f in fields(RuntimeFeatureFlags)}
        self.assertIn(self.FLAG, field_names)


class WeComChannelFeatureFlagTests(unittest.TestCase):
    """CHAN-03: wecom_channel_enabled defaults OFF (parity with qqbot_channel_enabled)."""

    FLAG = "wecom_channel_enabled"

    def test_wecom_channel_enabled_defaults_false(self) -> None:
        flags = RuntimeFeatureFlags()
        self.assertIs(flags.wecom_channel_enabled, False)

    def test_wecom_channel_require_enabled_raises_when_false(self) -> None:
        flags = RuntimeFeatureFlags()
        with self.assertRaisesRegex(
            RuntimeFeatureDisabledError,
            "runtime feature flag disabled: wecom_channel_enabled",
        ):
            flags.require_enabled(self.FLAG)

    def test_wecom_channel_require_enabled_passes_when_true(self) -> None:
        flags = RuntimeFeatureFlags(wecom_channel_enabled=True)
        flags.require_enabled(self.FLAG)

    def test_wecom_channel_flag_field_exists(self) -> None:
        field_names = {f.name for f in fields(RuntimeFeatureFlags)}
        self.assertIn(self.FLAG, field_names)


if __name__ == "__main__":
    unittest.main()
