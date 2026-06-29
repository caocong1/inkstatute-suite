"""Manifest builders for the concrete Hermes backend adapter."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

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
        capabilities=hermes_oneshot_capabilities(),
        metadata={
            "default_lane": "oneshot",
            "ordinary_wecom_channel_owner": "inkstatute_wecom_service",
            "profile_materialization": "external_secret_or_sanitized_bundle_ref",
            "no_channel_io_evidence": (
                "Hermes adapter returns platform objects only; ordinary-user delivery is owned by InkStatute."
            ),
        },
    )


def hermes_oneshot_capabilities() -> AdapterCapabilitySet:
    """Return the reduced default Hermes one-shot capability set."""

    return AdapterCapabilitySet(
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
    )


def build_probe_manifest(config: HermesBackendConfig | None, report: Any) -> AgentBackendManifest:
    """Build a manifest from a probe report, falling back to one-shot safely."""

    resolved = config or HermesBackendConfig()
    capabilities = getattr(report, "capabilities", hermes_oneshot_capabilities())
    modes = list(getattr(capabilities, "run_invocation_modes", []))
    if getattr(report, "ok", False) and "runs_api" in modes:
        return AgentBackendManifest(
            adapter_name="hermes-lawfirm-backend-adapter",
            adapter_version=resolved.adapter_version,
            mode=AgentBackendMode.HERMES,
            backend_version=resolved.backend_version,
            profile_name=resolved.profile_name,
            bundle_id=f"{resolved.profile_name}-profile-bundle",
            capabilities=replace(capabilities, no_channel_io=True),
            metadata={
                "default_lane": "oneshot",
                "opt_in_lane": "runs_api",
                "probe_status": "ok",
                "ordinary_wecom_channel_owner": "inkstatute_wecom_service",
                "runs_api_default_enabled": False,
            },
        )

    manifest = build_hermes_oneshot_manifest(resolved)
    return replace(
        manifest,
        metadata={
            **manifest.metadata,
            "fallback_reason": _sanitize_fallback_reason(
                getattr(report, "fallback_reason", None) or "runs_api_not_advertised"
            ),
        },
    )


def _sanitize_fallback_reason(value: object) -> str:
    text = str(value or "probe_fallback").lower().strip()
    safe = []
    for char in text:
        if char.isalnum() or char == "_":
            safe.append(char)
        elif char in {"-", " "}:
            safe.append("_")
    reason = "".join(safe).strip("_")
    return reason[:80] or "probe_fallback"


__all__ = ["build_hermes_oneshot_manifest", "build_probe_manifest", "hermes_oneshot_capabilities"]
