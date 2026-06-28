"""Hermes adapter manifest helpers."""

from __future__ import annotations

from typing import Any


def build_hermes_adapter_manifest(
    *,
    backend_version: str,
    profile_name: str,
    adapter_version: str = "0.1.0",
    no_channel_io: bool = True,
) -> dict[str, Any]:
    """Build a backend-neutral manifest for the Hermes lawfirm adapter."""

    return {
        "adapter_name": "hermes-lawfirm-agent-adapter",
        "adapter_version": adapter_version,
        "mode": "hermes",
        "backend_version": backend_version,
        "profile_name": profile_name,
        "bundle_id": "lawfirm-profile-bundle",
        "capabilities": {
            "hook_event_support": [
                "agent:end",
                "gateway:startup",
                "response_filter_contract_result_recorder",
            ],
            "invocation_mode": "sync",
            "feedback_target_support": "message_id",
            "session_read_support": True,
            "artifact_return_support": True,
            "trace_support": True,
            "no_channel_io": no_channel_io,
        },
        "metadata": {
            "after_filter_recorder_dir": "response_filter_contract_result_recorder",
            "manifest_hook_name": "contract_result_recorder",
            "repo_hook_artifacts": [
                "hooks/response_filter_contract_result_recorder",
                "response_filter_contract_result_recorder",
            ],
            "ordinary_wecom_channel_owner": "inkstatute_wecom_service",
            "no_channel_io_evidence": "Hermes adapter returns platform events/results; WeCom send is owned by InkStatute service.",
            "source_status": "repo_fixture_manifest",
            "production_ready": True,
        },
    }


__all__ = ["build_hermes_adapter_manifest"]
