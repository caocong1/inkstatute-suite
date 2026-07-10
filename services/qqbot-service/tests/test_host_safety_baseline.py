"""Host safety baseline: Protocol freeze, flag OFF, empty deps, Phase 08 preserved."""

from __future__ import annotations

import unittest
from pathlib import Path

from platform_runtime.feature_flags import RuntimeFeatureFlags
from platform_runtime.protocols import BackendAdapter, ChannelAdapter

REPO_ROOT = Path(__file__).resolve().parents[3]
HOST_PYPROJECT = REPO_ROOT / "services" / "qqbot-service" / "pyproject.toml"
PHASE_08_DIR = REPO_ROOT / ".planning" / "phases" / "08-lawyer-trial-acceptance"
PHASE_08_TEMPLATE = PHASE_08_DIR / "08-TRIAL-EVIDENCE-TEMPLATE.json"

CHANNEL_ADAPTER_METHODS = frozenset(
    {
        "channel_id",
        "capabilities",
        "verify_and_ack",
        "normalize_inbound",
        "deliver",
        "health",
    }
)

BACKEND_ADAPTER_METHODS = frozenset(
    {
        "backend_id",
        "capabilities",
        "bootstrap_check",
        "submit_run",
        "get_run",
        "stream_events",
        "cancel_run",
        "submit_approval",
        "collect_artifacts",
    }
)


class HostSafetyBaselineTests(unittest.TestCase):
    def test_channel_adapter_has_exactly_6_methods(self) -> None:
        methods = [m for m in dir(ChannelAdapter) if not m.startswith("_")]
        self.assertEqual(len(methods), 6)
        self.assertEqual(set(methods), CHANNEL_ADAPTER_METHODS)

    def test_backend_adapter_has_exactly_9_methods(self) -> None:
        methods = [m for m in dir(BackendAdapter) if not m.startswith("_")]
        self.assertEqual(len(methods), 9)
        self.assertEqual(set(methods), BACKEND_ADAPTER_METHODS)

    def test_qqbot_channel_enabled_defaults_false(self) -> None:
        self.assertIs(RuntimeFeatureFlags().qqbot_channel_enabled, False)

    def test_host_pyproject_has_empty_dependencies(self) -> None:
        content = HOST_PYPROJECT.read_text(encoding="utf-8")
        self.assertIn("dependencies = []", content)

    def test_phase_08_lawyer_trial_acceptance_dir_preserved(self) -> None:
        self.assertTrue(PHASE_08_DIR.is_dir(), f"missing {PHASE_08_DIR}")
        self.assertTrue(
            PHASE_08_TEMPLATE.is_file(),
            f"missing {PHASE_08_TEMPLATE}",
        )

    def test_host_config_enabled_defaults_false_when_available(self) -> None:
        from qqbot_service import QQBotHostConfig

        self.assertIs(QQBotHostConfig().enabled, False)


if __name__ == "__main__":
    unittest.main()
