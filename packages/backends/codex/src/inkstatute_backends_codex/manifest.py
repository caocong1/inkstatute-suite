"""Manifest builder for the concrete Codex backend adapter prototype."""

from __future__ import annotations

from platform_contract.agent_adapter import (
    AdapterCapabilitySet,
    AgentBackendManifest,
    AgentBackendMode,
)

from .config import CodexBackendConfig


def build_codex_manifest(
    config: CodexBackendConfig | None = None,
    *,
    stream_event_support: bool = False,
) -> AgentBackendManifest:
    """Build the Codex prototype backend manifest."""

    resolved = config or CodexBackendConfig()
    return AgentBackendManifest(
        adapter_name="codex-prototype-backend-adapter",
        adapter_version=resolved.adapter_version,
        mode=AgentBackendMode.CODEX,
        backend_version=resolved.backend_version,
        profile_name=None,
        bundle_id=None,
        capabilities=codex_prototype_capabilities(stream_event_support=stream_event_support),
        metadata={
            "default_lane": "oneshot",
            "production_ready": False,
            "no_channel_io_evidence": "Codex adapter returns platform objects only.",
            "ordinary_wecom_channel_owner": "inkstatute_wecom_service",
            "prototype": True,
        },
    )


def codex_prototype_capabilities(
    stream_event_support: bool = False,
) -> AdapterCapabilitySet:
    """Return the reduced Codex prototype capability set (14 fields)."""

    return AdapterCapabilitySet(
        hook_event_support=[],
        invocation_mode="sync",
        feedback_target_support="generated",
        session_read_support=False,
        artifact_return_support=False,
        trace_support=True,
        no_channel_io=True,
        run_invocation_modes=["oneshot"],
        stream_event_support=stream_event_support,
        cancel_support=False,
        approval_support=False,
        live_update_support=False,
        parallel_task_support=False,
        session_memory_support=False,
    )


__all__ = ["build_codex_manifest", "codex_prototype_capabilities"]
