from __future__ import annotations

import unittest

from platform_runtime import RuntimeFeatureDisabledError, RuntimeFeatureFlags


class RuntimeFeatureFlagsTests(unittest.TestCase):
    def test_all_runtime_lanes_default_to_false(self) -> None:
        flags = RuntimeFeatureFlags()

        self.assertFalse(flags.run_runtime_enabled)
        self.assertFalse(flags.streaming_lane_enabled)
        self.assertFalse(flags.channel_delivery_enabled)
        self.assertFalse(flags.approval_lane_enabled)
        self.assertFalse(flags.contract_log_enabled)

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


if __name__ == "__main__":
    unittest.main()
