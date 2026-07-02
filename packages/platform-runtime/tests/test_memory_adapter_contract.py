from __future__ import annotations

from dataclasses import replace
import inspect
import unittest

from platform_contract.events import MemoryRecord
from platform_runtime import (
    InMemoryMemoryStore,
    MemoryAdapterDecision,
    MemoryPrivacyError,
    MemoryQuery,
    MemorySearchResult,
    MemoryStoreAdapter,
    MemoryStoreCapabilityManifest,
    MemoryStorePolicy,
    evaluate_memory_adapter_manifest,
)
from platform_runtime.runtime import DefaultRunRuntime


def manifest(**overrides: object) -> MemoryStoreCapabilityManifest:
    values = {
        "adapter_id": "platform-native",
        "provider": "platform_native",
        "adapter_version": "0.1.0",
        "deployment_model": "in_process",
        "source_refs": ("docs/architecture/memory/context-memory-contracts.md",),
        "supports_memory_records": True,
        "supports_memory_candidates": True,
        "supports_memory_uses": True,
        "supports_ttl": True,
        "supports_delete": True,
        "supports_export": True,
        "supports_tenant_isolation": True,
        "supports_metadata_filters": True,
        "supports_raw_payload_blocking": True,
        "supports_human_review_gate": True,
        "stores_raw_payloads_by_default": False,
        "network_required": False,
        "requires_secrets": False,
        "sanitized_fixture_only": False,
        "default_for_legal_memory": True,
        "approved_for_live_legal_memory": True,
        "data_residency": "repo-local",
        "deletion_model": "ttl_and_tombstone",
        "export_model": "memory_record_fixture",
        "metadata": {"privacy": "refs_hashes_lengths_statuses_only"},
    }
    values.update(overrides)
    return MemoryStoreCapabilityManifest(**values)


def mem0_style_manifest() -> MemoryStoreCapabilityManifest:
    return manifest(
        adapter_id="mem0-style-sanitized",
        provider="mem0",
        deployment_model="self_hosted_or_hosted_api",
        source_refs=(
            "https://docs.mem0.ai/api-reference",
            "https://docs.mem0.ai/open-source/features/rest-api",
            "https://docs.mem0.ai/api-reference/memory/delete-memories",
            "https://docs.mem0.ai/api-reference/memory/create-memory-export",
        ),
        supports_memory_candidates=False,
        supports_memory_uses=False,
        supports_ttl=False,
        supports_delete=True,
        supports_export=True,
        supports_tenant_isolation=True,
        supports_metadata_filters=True,
        supports_raw_payload_blocking=True,
        supports_human_review_gate=True,
        network_required=True,
        requires_secrets=True,
        sanitized_fixture_only=True,
        default_for_legal_memory=False,
        approved_for_live_legal_memory=False,
        data_residency="requires_review",
        deletion_model="filtered_delete",
        export_model="filtered_export_job",
        metadata={"privacy": "sanitized_fixture_only", "official_docs_checked": "2026-07-01"},
    )


def zep_style_manifest() -> MemoryStoreCapabilityManifest:
    return manifest(
        adapter_id="zep-style-sanitized",
        provider="zep",
        deployment_model="cloud_or_byoc",
        source_refs=(
            "https://help.getzep.com/quick-start-guide",
            "https://help.getzep.com/faq",
            "https://help.getzep.com/deleting-data-from-the-graph",
            "https://help.getzep.com/users-and-user-graphs",
        ),
        supports_memory_candidates=False,
        supports_memory_uses=False,
        supports_ttl=False,
        supports_delete=True,
        supports_export=False,
        supports_tenant_isolation=True,
        supports_metadata_filters=True,
        supports_raw_payload_blocking=True,
        supports_human_review_gate=True,
        network_required=True,
        requires_secrets=True,
        sanitized_fixture_only=True,
        default_for_legal_memory=False,
        approved_for_live_legal_memory=False,
        data_residency="requires_review",
        deletion_model="user_delete_and_graph_episode_delete_with_caveats",
        export_model="requires_review",
        metadata={"privacy": "sanitized_fixture_only", "official_docs_checked": "2026-07-01"},
    )


def hindsight_style_manifest() -> MemoryStoreCapabilityManifest:
    return manifest(
        adapter_id="hindsight-style-sanitized",
        provider="hindsight",
        deployment_model="self_hosted_or_cloud",
        source_refs=(
            "https://hindsight.vectorize.io",
            "https://github.com/vectorize-io/hindsight",
            "律师助理 Bot 的 Agent 记忆组件选型研究.md",
        ),
        supports_memory_candidates=False,
        supports_memory_uses=False,
        supports_ttl=False,
        supports_delete=True,
        supports_export=True,
        supports_tenant_isolation=True,
        supports_metadata_filters=True,
        supports_raw_payload_blocking=True,
        supports_human_review_gate=True,
        network_required=True,
        requires_secrets=True,
        sanitized_fixture_only=True,
        default_for_legal_memory=False,
        approved_for_live_legal_memory=False,
        data_residency="requires_review",
        deletion_model="provider_delete_plus_adapter_tombstone_required",
        export_model="provider_export_plus_contract_memory_export_required",
        metadata={
            "privacy": "sanitized_fixture_only",
            "candidate_role": "audit_focused_recall_retain_reflect_spike",
        },
    )


def openviking_style_manifest() -> MemoryStoreCapabilityManifest:
    return manifest(
        adapter_id="openviking-style-sanitized",
        provider="openviking",
        deployment_model="local_or_object_storage",
        source_refs=(
            "https://openviking.ai",
            "https://github.com/volcengine/OpenViking",
            "律师助理 Bot 的 Agent 记忆组件选型研究.md",
        ),
        supports_memory_candidates=False,
        supports_memory_uses=False,
        supports_ttl=False,
        supports_delete=False,
        supports_export=True,
        supports_tenant_isolation=True,
        supports_metadata_filters=True,
        supports_raw_payload_blocking=True,
        supports_human_review_gate=True,
        network_required=False,
        requires_secrets=False,
        sanitized_fixture_only=True,
        default_for_legal_memory=False,
        approved_for_live_legal_memory=False,
        data_residency="adapter_controlled",
        deletion_model="requires_fine_grained_delete_review",
        export_model="snapshot_or_pack_export_requires_contract_mapping",
        metadata={
            "privacy": "sanitized_fixture_only",
            "candidate_role": "local_file_context_spike",
            "license_gate": "required_before_commercial_distribution",
        },
    )


def reme_style_manifest() -> MemoryStoreCapabilityManifest:
    return manifest(
        adapter_id="reme-style-sanitized",
        provider="reme",
        deployment_model="local_files",
        source_refs=(
            "https://reme.agentscope.io",
            "https://github.com/agentscope-ai/ReMe",
            "律师助理 Bot 的 Agent 记忆组件选型研究.md",
        ),
        supports_memory_candidates=False,
        supports_memory_uses=False,
        supports_ttl=False,
        supports_delete=True,
        supports_export=True,
        supports_tenant_isolation=True,
        supports_metadata_filters=True,
        supports_raw_payload_blocking=True,
        supports_human_review_gate=True,
        network_required=False,
        requires_secrets=False,
        sanitized_fixture_only=True,
        default_for_legal_memory=False,
        approved_for_live_legal_memory=False,
        data_residency="adapter_controlled",
        deletion_model="file_delete_plus_adapter_tombstone_required",
        export_model="markdown_tree_export_requires_contract_mapping",
        metadata={
            "privacy": "sanitized_fixture_only",
            "candidate_role": "human_auditable_markdown_memory_spike",
            "concurrency_gate": "required_before_team_use",
        },
    )


def make_memory() -> MemoryRecord:
    return MemoryRecord(
        memory_id="memory-adapter-001",
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        scope="session",
        status="active",
        sensitivity="internal",
        created_at="2026-07-01T08:00:00Z",
        updated_at="2026-07-01T08:00:00Z",
        source_refs=["fixture://phase18/memory/source"],
        summary="adapter contract preference",
        subject="adapter",
        session_id="session-001",
        related_user_id="user-001",
        raw_payload_ref="fixture://phase18/memory/raw",
        confidence=0.9,
        metadata={"labels": ["adapter"]},
    )


class MemoryAdapterContractTests(unittest.TestCase):
    def test_platform_native_manifest_can_be_current_legal_default_after_approval(self) -> None:
        evaluation = evaluate_memory_adapter_manifest(manifest())

        self.assertEqual(evaluation.decision, MemoryAdapterDecision.ACCEPTED_FOR_CURRENT_LEGAL_USE)
        self.assertEqual(evaluation.blockers, ())
        self.assertTrue(evaluation.is_live_legal_ready)

    def test_mem0_and_zep_style_manifests_are_sanitized_spike_only(self) -> None:
        candidates = (
            mem0_style_manifest(),
            zep_style_manifest(),
            hindsight_style_manifest(),
            openviking_style_manifest(),
            reme_style_manifest(),
        )
        for candidate in candidates:
            with self.subTest(provider=candidate.provider):
                evaluation = evaluate_memory_adapter_manifest(candidate)

                self.assertEqual(evaluation.decision, MemoryAdapterDecision.ACCEPTED_FOR_SANITIZED_SPIKE)
                self.assertFalse(evaluation.is_live_legal_ready)
                self.assertIn("live_legal_memory_gate", evaluation.required_gates)
                self.assertFalse(candidate.default_for_legal_memory)

    def test_lawyer_memory_research_candidates_keep_provider_specific_gates(self) -> None:
        candidates = {
            "hindsight": hindsight_style_manifest(),
            "openviking": openviking_style_manifest(),
            "reme": reme_style_manifest(),
        }

        self.assertEqual(
            candidates["hindsight"].metadata["candidate_role"],
            "audit_focused_recall_retain_reflect_spike",
        )
        self.assertIn(
            "license_gate",
            candidates["openviking"].metadata,
        )
        self.assertIn(
            "concurrency_gate",
            candidates["reme"].metadata,
        )

    def test_external_default_for_legal_without_approval_is_rejected(self) -> None:
        candidate = replace(
            mem0_style_manifest(),
            default_for_legal_memory=True,
            approved_for_live_legal_memory=False,
            sanitized_fixture_only=False,
        )

        evaluation = evaluate_memory_adapter_manifest(candidate)

        self.assertEqual(evaluation.decision, MemoryAdapterDecision.REJECTED_FOR_LEGAL_MEMORY)
        self.assertIn("external_default_requires_explicit_live_legal_approval", evaluation.blockers)

    def test_raw_payload_default_storage_is_rejected(self) -> None:
        candidate = replace(mem0_style_manifest(), stores_raw_payloads_by_default=True)

        evaluation = evaluate_memory_adapter_manifest(candidate)

        self.assertEqual(evaluation.decision, MemoryAdapterDecision.REJECTED_FOR_LEGAL_MEMORY)
        self.assertIn("stores_raw_payloads_by_default", evaluation.blockers)

    def test_missing_delete_or_export_defers_legal_production(self) -> None:
        candidate = replace(
            manifest(default_for_legal_memory=False, approved_for_live_legal_memory=False),
            sanitized_fixture_only=False,
            supports_delete=False,
            supports_export=False,
        )

        evaluation = evaluate_memory_adapter_manifest(candidate)

        self.assertEqual(evaluation.decision, MemoryAdapterDecision.DEFERRED_FOR_LEGAL_PRODUCTION)
        self.assertIn("deletion_export_evidence", evaluation.required_gates)

    def test_secret_like_refs_and_metadata_are_rejected(self) -> None:
        with self.assertRaisesRegex(MemoryPrivacyError, "source_refs"):
            evaluate_memory_adapter_manifest(
                replace(mem0_style_manifest(), source_refs=("https://example.invalid?token=secret",))
            )

        with self.assertRaisesRegex(MemoryPrivacyError, "api_key"):
            evaluate_memory_adapter_manifest(replace(mem0_style_manifest(), metadata={"api_key": "unsafe"}))

    def test_protocol_can_be_implemented_by_phase17_store_wrapper(self) -> None:
        class AdapterWrapper:
            def __init__(self) -> None:
                self.store = InMemoryMemoryStore()

            def capability_manifest(self) -> MemoryStoreCapabilityManifest:
                return manifest()

            def upsert(self, record: MemoryRecord) -> None:
                self.store.upsert(record)

            def search(
                self,
                query: MemoryQuery,
                *,
                policy: MemoryStorePolicy | None = None,
            ) -> tuple[MemorySearchResult, ...]:
                return self.store.search(query, policy=policy)

            def mark_deleted(self, memory_id: str, *, reason: str = "") -> MemoryRecord:
                return self.store.mark_deleted(memory_id, reason=reason)

            def export_records(self, query: MemoryQuery) -> tuple[MemoryRecord, ...]:
                return self.store.list_for_query(query)

        adapter = AdapterWrapper()
        adapter.upsert(make_memory())
        results = adapter.search(
            MemoryQuery(
                tenant_id="tenant-001",
                workspace_id="workspace-001",
                session_id="session-001",
                user_id="user-001",
                text="adapter",
                now="2026-07-01T08:00:00Z",
            )
        )

        self.assertIsInstance(adapter, MemoryStoreAdapter)
        self.assertEqual([result.record.memory_id for result in results], ["memory-adapter-001"])

    def test_default_run_runtime_constructor_has_no_memory_adapter_parameter(self) -> None:
        signature = inspect.signature(DefaultRunRuntime.__init__)

        self.assertNotIn("memory_adapter", signature.parameters)
        self.assertNotIn("memory_store", signature.parameters)


if __name__ == "__main__":
    unittest.main()
