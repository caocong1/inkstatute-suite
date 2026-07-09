"""Contract freeze not-violated tests (SAFETY-02, SAFETY-06).

Verifies that the contract freeze is not violated by Phase 43:

- ``ChannelAdapter`` Protocol still has exactly 6 methods.
- ``FeedbackSource`` enum still has exactly 4 values.
- ``Channel.QQBOT == "qqbot"`` (existing enum value, not removed).
- ``qqbot_channel_enabled`` feature flag still defaults to ``False``.
- ``protocols.py`` was not modified (runtime introspection of method count).
- ``feature_flags.py`` was not modified (runtime introspection of flag default).
- No ``platform-contract`` schema files were modified (covered by existing
  ``test_contract_freeze.py`` SHA-256 baseline; this test serves as a
  qqbot-package-local assertion that ``FeedbackSource`` values are unchanged).

This is a verification-only test — it does NOT create or modify contract files.
"""

from __future__ import annotations

import unittest
from dataclasses import fields
from pathlib import Path

from platform_contract.enums import Channel, FeedbackSource
from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.protocols import ChannelAdapter


class ContractFreezeNotViolatedTests(unittest.TestCase):
    """Assert frozen contract surfaces are unchanged after Phase 43."""

    def test_channel_adapter_method_count_is_6(self) -> None:
        methods = [m for m in dir(ChannelAdapter) if not m.startswith("_")]
        self.assertEqual(len(methods), 6)
        expected = {
            "channel_id",
            "capabilities",
            "verify_and_ack",
            "normalize_inbound",
            "deliver",
            "health",
        }
        self.assertEqual(set(methods), expected)

    def test_qqbot_pyproject_dependencies_remain_empty(self) -> None:
        """ADAPTER-04 / T-65-SC: Phase 65 must not add qqbot package dependencies."""
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        self.assertIn("dependencies = []", content)

    def test_feedback_source_has_exactly_4_values(self) -> None:
        values = [v.value for v in FeedbackSource]
        self.assertEqual(len(values), 4)
        expected = {"card_button", "text_command", "web_form", "admin_annotation"}
        self.assertEqual(set(values), expected)

    def test_channel_enum_includes_qqbot(self) -> None:
        self.assertEqual(Channel.QQBOT.value, "qqbot")

    def test_qqbot_channel_enabled_defaults_false(self) -> None:
        flags = RuntimeFeatureFlags()
        self.assertIs(flags.qqbot_channel_enabled, False)

    def test_protocols_py_not_modified_during_phase_43(self) -> None:
        """Runtime introspection: ChannelAdapter still has 6 methods.

        The existing ``test_contract_freeze.py`` in the contract-test-suite
        covers the SHA-256 baseline hash for ``packages/platform-contract/``
        schema files.  This test uses runtime introspection (same approach
        as ``test_contract_count_freeze.py``) to confirm ``protocols.py``
        was not modified to change the ChannelAdapter method count.
        """
        methods = [m for m in dir(ChannelAdapter) if not m.startswith("_")]
        self.assertEqual(len(methods), 6)

    def test_feature_flags_py_not_modified_during_phase_43(self) -> None:
        """Runtime introspection: qqbot_channel_enabled field exists with default False."""
        field_names = [f.name for f in fields(RuntimeFeatureFlags)]
        self.assertIn("qqbot_channel_enabled", field_names)
        flags = RuntimeFeatureFlags()
        self.assertIs(flags.qqbot_channel_enabled, False)

    def test_no_platform_contract_files_modified(self) -> None:
        """Qqbot-package-local assertion that FeedbackSource values are unchanged.

        The existing ``test_contract_freeze.py`` in the contract-test-suite
        compares SHA-256 hashes against the v1.5 baseline for all 31 contract
        surface files.  This test serves as a qqbot-package-local assertion
        that ``FeedbackSource`` values are unchanged via runtime introspection.
        It does NOT re-implement the baseline hash comparison.
        """
        values = [v.value for v in FeedbackSource]
        expected = {"card_button", "text_command", "web_form", "admin_annotation"}
        self.assertEqual(set(values), expected)
        self.assertEqual(len(values), 4)


if __name__ == "__main__":
    unittest.main()
