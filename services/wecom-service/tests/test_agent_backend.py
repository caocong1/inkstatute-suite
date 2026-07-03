from __future__ import annotations

import unittest

from platform_contract.agent_adapter import (
    AdapterCapabilitySet,
    AgentBackendManifest,
    AgentBackendMode,
)

from wecom_service.agent_backend import AgentBackendSelectionError, select_agent_backend


class AgentBackendSelectorTests(unittest.TestCase):
    def test_selects_valid_hermes_manifest_for_live_acceptance(self) -> None:
        manifest = self.manifest(AgentBackendMode.HERMES, no_channel_io=True)

        selection = select_agent_backend({"agent_backend": {"mode": "hermes"}}, [manifest])

        self.assertEqual(selection.mode, "hermes")
        self.assertIs(selection.manifest, manifest)
        self.assertTrue(selection.live_acceptance_allowed)

    def test_rejects_hermes_manifest_without_no_channel_io(self) -> None:
        manifest = self.manifest(AgentBackendMode.HERMES, no_channel_io=False)

        with self.assertRaises(AgentBackendSelectionError):
            select_agent_backend({"agent_backend": {"mode": "hermes"}}, [manifest])

    def test_codex_future_manifest_is_contract_compatible_not_live_ready(self) -> None:
        manifest = self.manifest(AgentBackendMode.CODEX, no_channel_io=True, production_ready=False)

        selection = select_agent_backend({"agent_backend": {"mode": "codex"}}, [manifest])

        self.assertEqual(selection.mode, "codex")
        self.assertTrue(selection.contract_compatible)
        self.assertFalse(selection.live_acceptance_allowed)

    def test_non_hermes_manifest_production_ready_bypass_is_blocked(self) -> None:
        for mode in (AgentBackendMode.CODEX, AgentBackendMode.PROVIDER_MODEL):
            with self.subTest(mode=mode):
                manifest = self.manifest(mode, no_channel_io=True, production_ready=True)

                selection = select_agent_backend({"agent_backend": {"mode": mode.value}}, [manifest])

                self.assertEqual(selection.mode, mode.value)
                self.assertTrue(selection.contract_compatible)
                self.assertFalse(selection.live_acceptance_allowed)

    def test_unknown_mode_raises_selection_error(self) -> None:
        with self.assertRaises(AgentBackendSelectionError):
            select_agent_backend({"agent_backend": {"mode": "unknown"}}, [])

    def manifest(
        self,
        mode: AgentBackendMode,
        *,
        no_channel_io: bool,
        production_ready: bool = True,
    ) -> AgentBackendManifest:
        return AgentBackendManifest(
            adapter_name=f"{mode.value}-adapter",
            adapter_version="0.1.0",
            mode=mode,
            backend_version=f"{mode.value}-fixture-1",
            profile_name="lawfirm" if mode is AgentBackendMode.HERMES else None,
            bundle_id="lawfirm-profile-bundle" if mode is AgentBackendMode.HERMES else None,
            capabilities=AdapterCapabilitySet(
                hook_event_support=["agent:end"] if mode is AgentBackendMode.HERMES else [],
                invocation_mode="sync" if mode is AgentBackendMode.HERMES else "async",
                feedback_target_support="message_id" if mode is AgentBackendMode.HERMES else "generated",
                session_read_support=mode is AgentBackendMode.HERMES,
                artifact_return_support=True,
                trace_support=True,
                no_channel_io=no_channel_io,
            ),
            metadata={"production_ready": production_ready},
        )


if __name__ == "__main__":
    unittest.main()
