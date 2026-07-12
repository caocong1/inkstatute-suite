"""Manifest builder for the concrete provider_model backend adapter prototype."""

from __future__ import annotations

from platform_contract.agent_adapter import (
    AdapterCapabilitySet,
    AgentBackendManifest,
    AgentBackendMode,
)

from .config import ProviderModelBackendConfig


def build_provider_model_manifest(
    config: ProviderModelBackendConfig | None = None,
    *,
    stream_event_support: bool = False,
) -> AgentBackendManifest:
    """Build the provider_model prototype backend manifest."""

    resolved = config or ProviderModelBackendConfig()
    return AgentBackendManifest(
        adapter_name="provider-model-prototype-backend-adapter",
        adapter_version=resolved.adapter_version,
        mode=AgentBackendMode.PROVIDER_MODEL,
        backend_version=resolved.backend_version,
        profile_name=None,
        bundle_id=None,
        capabilities=provider_model_prototype_capabilities(
            stream_event_support=stream_event_support,
            supports_vision=bool(resolved.supports_vision),
        ),
        metadata={
            "default_lane": "oneshot",
            "production_ready": False,
            "no_channel_io_evidence": "Provider model adapter returns platform objects only.",
            "ordinary_wecom_channel_owner": "inkstatute_wecom_service",
            "prototype": True,
            "invocation_mode": "direct_llm",
        },
    )


def provider_model_prototype_capabilities(
    *,
    stream_event_support: bool = False,
    supports_vision: bool = False,
) -> AdapterCapabilitySet:
    """Return the reduced provider_model prototype capability set (15 fields)."""

    return AdapterCapabilitySet(
        hook_event_support=[],
        invocation_mode="direct_llm",
        feedback_target_support="generated",
        session_read_support=False,
        artifact_return_support=True,
        trace_support=False,
        no_channel_io=True,
        run_invocation_modes=["oneshot"],
        stream_event_support=stream_event_support,
        cancel_support=False,
        approval_support=False,
        live_update_support=False,
        parallel_task_support=False,
        session_memory_support=True,
        supports_vision=supports_vision,
    )


__all__ = ["build_provider_model_manifest", "provider_model_prototype_capabilities"]
