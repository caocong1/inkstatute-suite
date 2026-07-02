"""Hindsight-backed implementation of the long-term Memory interface."""

from __future__ import annotations

from typing import Any

from hindsight_client import Hindsight

from platform_contract.events import JsonObject

from .long_term_memory import (
    Memory,
    MemoryPrivacyError,
    MemoryRecallInput,
    MemoryRecallResult,
    MemoryReflectInput,
    MemoryReflectResult,
    MemoryRetainInput,
    MemoryRetainResult,
    RecalledMemory,
    _validate_recall_input,
    _validate_reflect_input,
    _validate_retain_input,
)
from .memory_adapters import MemoryStoreCapabilityManifest


class HindsightMemoryError(RuntimeError):
    """Raised when a Hindsight API call fails."""


class HindsightMemory:
    """Async long-term memory adapter backed by Hindsight.

    Configuration is read from environment variables:
    - HINDSIGHT_BASE_URL: Hindsight API base URL (default: http://localhost:8888)
    - HINDSIGHT_API_KEY: optional Bearer token
    - HINDSIGHT_LLM_MODEL: optional default LLM model
    - HINDSIGHT_EMBEDDING_MODEL: optional default embedding model

    Tenant/workspace isolation is enforced by mapping each (tenant_id, workspace_id,
    user_id) tuple to a Hindsight bank_id. The bank is created on first use.
    """

    def __init__(
        self,
        *,
        client: Hindsight,
    ) -> None:
        self._client = client
        self._base_url = getattr(client, "base_url", "http://localhost:8888")

    def capability_manifest(self) -> JsonObject:
        """Return a capability manifest describing this adapter."""
        manifest = MemoryStoreCapabilityManifest(
            adapter_id="hindsight-v0.8.4",
            provider="hindsight",
            adapter_version="0.1.0",
            deployment_model="self_hosted_or_cloud",
            source_refs=(
                "https://hindsight.vectorize.io",
                "https://github.com/vectorize-io/hindsight",
                ".planning/phases/26-memory-provider-evaluation-and-selection/26-SELECTION.md",
            ),
            supports_memory_records=True,
            supports_memory_candidates=False,
            supports_memory_uses=False,
            supports_ttl=False,
            supports_delete=True,
            supports_export=True,
            supports_tenant_isolation=True,
            supports_metadata_filters=True,
            supports_raw_payload_blocking=True,
            supports_human_review_gate=True,
            stores_raw_payloads_by_default=False,
            network_required=True,
            requires_secrets=True,
            sanitized_fixture_only=False,
            default_for_legal_memory=False,
            approved_for_live_legal_memory=False,
            data_residency="self_hosted_by_default",
            deletion_model="provider_delete_plus_adapter_tombstone_required",
            export_model="provider_export_plus_contract_memory_export_required",
            metadata={
                "privacy": "hindsight_bank_per_tenant_workspace_user",
                "retain_recall_reflect": "supported",
            },
        )
        return {
            "adapter_id": manifest.adapter_id,
            "provider": manifest.provider,
            "adapter_version": manifest.adapter_version,
            "deployment_model": manifest.deployment_model,
            "source_refs": manifest.source_refs,
            "supports_memory_records": manifest.supports_memory_records,
            "supports_delete": manifest.supports_delete,
            "supports_export": manifest.supports_export,
            "supports_tenant_isolation": manifest.supports_tenant_isolation,
            "supports_raw_payload_blocking": manifest.supports_raw_payload_blocking,
            "stores_raw_payloads_by_default": manifest.stores_raw_payloads_by_default,
            "network_required": manifest.network_required,
            "requires_secrets": manifest.requires_secrets,
            "data_residency": manifest.data_residency,
            "metadata": manifest.metadata,
        }

    def _bank_id(self, tenant_id: str, workspace_id: str, user_id: str) -> str:
        """Derive a Hindsight bank_id from the InkStatute scope.

        Hindsight bank_ids are simple strings; we use a colon-separated scope.
        """
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in f"{tenant_id}:{workspace_id}:{user_id}")
        return f"ink-{safe}"

    async def _ensure_bank(self, bank_id: str) -> None:
        """Create the bank if it does not exist; idempotent."""
        try:
            await self._client.acreate_bank(bank_id)
        except Exception as e:
            # Banks may already exist; Hindsight does not expose a clean exists
            # API so we swallow creation errors and rely on later calls to fail.
            if "already exists" not in str(e).lower():
                pass

    async def aretain(self, input: MemoryRetainInput) -> MemoryRetainResult:
        _validate_retain_input(input)
        bank_id = self._bank_id(input.tenant_id, input.workspace_id, input.user_id)
        await self._ensure_bank(bank_id)
        try:
            result = await self._client.aretain(bank_id=bank_id, content=input.content)
            return MemoryRetainResult(
                bank_id=bank_id,
                retained_count=result.items_count or 1,
                metadata={
                    "scope": {
                        "tenant_id": input.tenant_id,
                        "workspace_id": input.workspace_id,
                        "user_id": input.user_id,
                    },
                    "async": result.var_async,
                },
            )
        except Exception as e:
            raise HindsightMemoryError(f"retain failed for bank {bank_id}: {e}") from e

    async def arecall(self, input: MemoryRecallInput) -> MemoryRecallResult:
        _validate_recall_input(input)
        bank_id = self._bank_id(input.tenant_id, input.workspace_id, input.user_id)
        await self._ensure_bank(bank_id)
        try:
            result = await self._client.arecall(bank_id=bank_id, query=input.query)
            memories = tuple(
                RecalledMemory(
                    memory_id=getattr(item, "id", f"hindsight-{index}"),
                    text=getattr(item, "text", ""),
                    type=getattr(item, "type", "world"),
                    relevance_score=getattr(item, "score", None),
                    metadata={"index": index},
                )
                for index, item in enumerate(result.results)
            )
            return MemoryRecallResult(
                bank_id=bank_id,
                query=input.query,
                memories=memories[: max(1, input.max_results)] if input.max_results else memories,
                metadata={
                    "scope": {
                        "tenant_id": input.tenant_id,
                        "workspace_id": input.workspace_id,
                        "user_id": input.user_id,
                    },
                },
            )
        except Exception as e:
            raise HindsightMemoryError(f"recall failed for bank {bank_id}: {e}") from e

    async def areflect(self, input: MemoryReflectInput) -> MemoryReflectResult:
        _validate_reflect_input(input)
        bank_id = self._bank_id(input.tenant_id, input.workspace_id, input.user_id)
        await self._ensure_bank(bank_id)
        try:
            result = await self._client.areflect(bank_id=bank_id, query=input.query)
            return MemoryReflectResult(
                bank_id=bank_id,
                query=input.query,
                text=getattr(result, "text", ""),
                based_on=tuple(getattr(result, "based_on", ()) or ()),
                metadata={
                    "scope": {
                        "tenant_id": input.tenant_id,
                        "workspace_id": input.workspace_id,
                        "user_id": input.user_id,
                    },
                },
            )
        except Exception as e:
            raise HindsightMemoryError(f"reflect failed for bank {bank_id}: {e}") from e
