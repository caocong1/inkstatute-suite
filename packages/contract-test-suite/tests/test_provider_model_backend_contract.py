"""Cross-package contract tests for the provider_model backend adapter prototype.

These tests verify that the real ``build_provider_model_manifest()`` (not a
synthetic fixture) passes through the platform contract validation and the
WeCom service runtime selector with ``live_acceptance_allowed=False``.  They
also assert the SAFETY-02 contract-count freeze invariants (9 BackendAdapter
methods, 14 AdapterCapabilitySet fields) hold for the provider_model adapter.
"""

from __future__ import annotations

import unittest
from dataclasses import fields

from platform_contract.agent_adapter import (
    AdapterCapabilitySet,
    AgentBackendMode,
    validate_agent_backend_manifest,
)
from wecom_service.agent_backend import select_agent_backend

from inkstatute_backends_provider_model import (
    ProviderModelBackendAdapter,
    ProviderModelBackendConfig,
    build_provider_model_manifest,
    provider_model_prototype_capabilities,
)


class ProviderModelBackendContractTests(unittest.TestCase):
    """Verify the real provider_model adapter satisfies the platform contract."""

    # ------------------------------------------------------------------
    # Manifest validation
    # ------------------------------------------------------------------

    def test_real_provider_model_manifest_validates_clean(self) -> None:
        """The real provider_model manifest must produce zero validation issues."""
        manifest = build_provider_model_manifest()
        self.assertEqual(validate_agent_backend_manifest(manifest), [])

    def test_real_provider_model_manifest_selects_as_contract_compatible_not_live(self) -> None:
        """The real provider_model manifest must select as contract-compatible but not live."""
        selection = select_agent_backend(
            {"agent_backend": {"mode": "provider_model"}},
            [build_provider_model_manifest()],
        )
        self.assertEqual(selection.mode, "provider_model")
        self.assertTrue(selection.contract_compatible)
        self.assertFalse(selection.live_acceptance_allowed)

    def test_real_provider_model_manifest_production_ready_is_false(self) -> None:
        """The provider_model prototype must declare production_ready=False."""
        manifest = build_provider_model_manifest()
        self.assertIs(manifest.metadata["production_ready"], False)

    def test_real_provider_model_manifest_no_channel_io_is_true(self) -> None:
        """The provider_model prototype must declare no_channel_io=True."""
        manifest = build_provider_model_manifest()
        self.assertIs(manifest.capabilities.no_channel_io, True)

    def test_real_provider_model_manifest_invocation_mode_is_direct_llm(self) -> None:
        """The provider_model prototype must declare invocation_mode=direct_llm."""
        manifest = build_provider_model_manifest()
        self.assertEqual(manifest.capabilities.invocation_mode, "direct_llm")

    # ------------------------------------------------------------------
    # SAFETY-02 contract-count freeze
    # ------------------------------------------------------------------

    def test_provider_model_capabilities_field_count_matches_freeze_baseline(self) -> None:
        """AdapterCapabilitySet must still have exactly 15 fields (SAFETY-02)."""
        self.assertEqual(len(fields(AdapterCapabilitySet)), 15)
        caps = provider_model_prototype_capabilities()
        self.assertEqual(len(fields(caps)), 15)

    def test_provider_model_adapter_exposes_exactly_9_backend_adapter_methods(self) -> None:
        """ProviderModelBackendAdapter must expose exactly 9 BackendAdapter methods."""
        adapter = ProviderModelBackendAdapter()
        expected_methods = (
            "backend_id",
            "capabilities",
            "bootstrap_check",
            "submit_run",
            "get_run",
            "stream_events",
            "cancel_run",
            "submit_approval",
            "collect_artifacts",
        )
        methods = [
            m for m in expected_methods if callable(getattr(adapter, m, None))
        ]
        self.assertEqual(len(methods), 9)

    def test_provider_model_adapter_mode_matches_enum(self) -> None:
        """The provider_model manifest mode must be AgentBackendMode.PROVIDER_MODEL."""
        self.assertEqual(build_provider_model_manifest().mode, AgentBackendMode.PROVIDER_MODEL)

    def test_provider_model_manifest_artifact_return_support_is_true(self) -> None:
        """The provider_model prototype must declare artifact_return_support=True."""
        manifest = build_provider_model_manifest()
        self.assertIs(manifest.capabilities.artifact_return_support, True)


if __name__ == "__main__":
    unittest.main()
