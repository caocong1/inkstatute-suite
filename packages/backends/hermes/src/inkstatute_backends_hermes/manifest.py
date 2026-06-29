"""Manifest builders for the concrete Hermes backend adapter."""

from __future__ import annotations

from platform_contract.agent_adapter import (
    AdapterCapabilitySet,
    AgentBackendManifest,
    AgentBackendMode,
)

from .config import HermesBackendConfig


def build_hermes_oneshot_manifest(config: HermesBackendConfig | None = None) -> AgentBackendManifest:
    """Build the reduced default one-shot Hermes backend manifest."""

    resolved = config or HermesBackendConfig()
    return AgentBackendManifest(
        adapter_name="hermes-lawfirm-backend-adapter",
        adapter_version=resolved.adapter_version,
        mode=AgentBackendMode.HERMES,
        backend_version=resolved.backend_version,
        profile_name=resolved.profile_name,
        bundle_id=f"{resolved.profile_name}-profile-bundle",
        capabilities=AdapterCapabilitySet(
            hook_event_support=[],
            invocation_mode="sync",
            feedback_target_support="message_id",
            session_read_support=False,
            artifact_return_support=True,
            trace_support=True,
            no_channel_io=True,
            run_invocation_modes=["oneshot"],
            stream_event_support=False,
            cancel_support=False,
            approval_support=False,
            live_update_support=False,
            parallel_task_support=False,
            session_memory_support=False,
        ),
        metadata={
            "default_lane": "oneshot",
            "ordinary_wecom_channel_owner": "inkstatute_wecom_service",
            "profile_materialization": "external_secret_or_sanitized_bundle_ref",
            "no_channel_io_evidence": (
                "Hermes adapter returns platform objects only; ordinary-user delivery is owned by InkStatute."
            ),
        },
    )


__all__ = ["build_hermes_oneshot_manifest"]

