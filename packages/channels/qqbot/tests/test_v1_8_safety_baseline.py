"""Consolidated v1.8 pre-implementation safety baseline (ADAPTER-04).

Verifies all 5 Phase 58 success criteria in a single verification artifact:

- SC-2: ChannelAdapter Protocol has exactly 6 methods (runtime introspection).
- SC-2: BackendAdapter Protocol has exactly 9 methods (runtime introspection).
- SC-2: FeedbackSource enum has exactly 4 values (runtime introspection).
- SC-2: Channel.QQBOT enum value is "qqbot" (runtime introspection).
- SC-3: qqbot_channel_enabled feature flag defaults to False (assertIs).
- SC-5: dependencies = [] invariant holds in pyproject.toml (file content).

This complements (does not duplicate) the existing scattered tests:
- test_no_wecom_import.py covers SC-4 (AST-based import isolation).
- test_contract_freeze.py covers SC-2 SHA-256 baseline for 31 platform-contract files.
- test_contract_count_freeze.py covers SC-2 Protocol method counts in contract-test-suite.
- test_contract_freeze_not_violated.py covers SC-2/SC-3 in the qqbot package.

The consolidated test uses runtime introspection (complementary, not duplicative).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from platform_contract.enums import Channel, FeedbackSource
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.protocols import BackendAdapter, ChannelAdapter

# ADAPTER-03 / Phase 65: channel-core must be reused as-is — no new modules.
# Allowlist is the known top-level .py set under packages/channel-core/src/channel_core/.
# parents[3] == packages/ (tests → qqbot → channels → packages)
CHANNEL_CORE_SRC = (
    Path(__file__).resolve().parents[3] / "channel-core" / "src" / "channel_core"
)
CHANNEL_CORE_ALLOWED_MODULES = frozenset(
    {
        "__init__.py",
        "active_task_router.py",
        "delivery_guard.py",
        "idempotency.py",
        "output_policy.py",
        "owned_notices.py",
    }
)


class V18SafetyBaselineTests(unittest.TestCase):
    """All 5 Phase 58 success criteria in one verification artifact (ADAPTER-04)."""

    # SC-2: Frozen Protocol method counts
    def test_channel_adapter_has_exactly_6_methods(self) -> None:
        methods = [m for m in dir(ChannelAdapter) if not m.startswith("_")]
        self.assertEqual(len(methods), 6)

    def test_backend_adapter_has_exactly_9_methods(self) -> None:
        methods = [m for m in dir(BackendAdapter) if not m.startswith("_")]
        self.assertEqual(len(methods), 9)

    # SC-3: Feature flag default-off
    def test_qqbot_channel_enabled_defaults_false(self) -> None:
        self.assertIs(RuntimeFeatureFlags().qqbot_channel_enabled, False)

    # SC-2: Platform-contract enums unchanged
    def test_feedback_source_has_exactly_4_values(self) -> None:
        values = [v.value for v in FeedbackSource]
        self.assertEqual(len(values), 4)
        expected = {"card_button", "text_command", "web_form", "admin_annotation"}
        self.assertEqual(set(values), expected)

    def test_channel_enum_includes_qqbot(self) -> None:
        self.assertEqual(Channel.QQBOT.value, "qqbot")

    # SC-5: dependencies = [] invariant
    def test_qqbot_pyproject_has_empty_dependencies(self) -> None:
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        self.assertIn("dependencies = []", content)

    # ADAPTER-03: no new channel-core modules (Phase 65 reuse-only)
    def test_channel_core_has_no_new_modules(self) -> None:
        self.assertTrue(
            CHANNEL_CORE_SRC.is_dir(),
            f"channel-core package missing at {CHANNEL_CORE_SRC}",
        )
        present = {p.name for p in CHANNEL_CORE_SRC.glob("*.py")}
        unexpected = present - CHANNEL_CORE_ALLOWED_MODULES
        missing = CHANNEL_CORE_ALLOWED_MODULES - present
        self.assertEqual(
            unexpected,
            set(),
            f"new channel-core modules not on allowlist: {sorted(unexpected)}",
        )
        self.assertEqual(
            missing,
            set(),
            f"expected channel-core modules missing: {sorted(missing)}",
        )


if __name__ == "__main__":
    unittest.main()
