"""Provider-neutral memory adapter contract and acceptance gates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
import re
from typing import Protocol, runtime_checkable

from platform_contract.events import JsonObject, MemoryRecord

from .memory import MemoryPrivacyError, MemoryQuery, MemorySearchResult, MemoryStorePolicy


class MemoryAdapterDecision:
    ACCEPTED_FOR_CURRENT_LEGAL_USE = "accepted_for_current_legal_use"
    ACCEPTED_FOR_SANITIZED_SPIKE = "accepted_for_sanitized_spike"
    DEFERRED_FOR_LEGAL_PRODUCTION = "deferred_for_legal_production"
    REJECTED_FOR_LEGAL_MEMORY = "rejected_for_legal_memory"


@dataclass(frozen=True, slots=True)
class MemoryStoreCapabilityManifest:
    adapter_id: str
    provider: str
    adapter_version: str
    deployment_model: str
    source_refs: tuple[str, ...] = ()
    supports_memory_records: bool = False
    supports_memory_candidates: bool = False
    supports_memory_uses: bool = False
    supports_ttl: bool = False
    supports_delete: bool = False
    supports_export: bool = False
    supports_tenant_isolation: bool = False
    supports_metadata_filters: bool = False
    supports_raw_payload_blocking: bool = False
    supports_human_review_gate: bool = False
    stores_raw_payloads_by_default: bool = False
    network_required: bool = False
    requires_secrets: bool = False
    sanitized_fixture_only: bool = True
    default_for_legal_memory: bool = False
    approved_for_live_legal_memory: bool = False
    data_residency: str = "unknown"
    deletion_model: str | None = None
    export_model: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryAdapterEvaluation:
    manifest: MemoryStoreCapabilityManifest
    decision: str
    reasons: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    required_gates: tuple[str, ...] = ()
    metadata: JsonObject = field(default_factory=dict)

    @property
    def is_live_legal_ready(self) -> bool:
        return self.decision == MemoryAdapterDecision.ACCEPTED_FOR_CURRENT_LEGAL_USE


@runtime_checkable
class MemoryStoreAdapter(Protocol):
    """Minimal adapter surface hosts may implement without changing RunRuntime."""

    def capability_manifest(self) -> MemoryStoreCapabilityManifest:
        ...

    def upsert(self, record: MemoryRecord) -> None:
        ...

    def search(
        self,
        query: MemoryQuery,
        *,
        policy: MemoryStorePolicy | None = None,
    ) -> tuple[MemorySearchResult, ...]:
        ...

    def mark_deleted(self, memory_id: str, *, reason: str = "") -> MemoryRecord:
        ...

    def export_records(self, query: MemoryQuery) -> tuple[MemoryRecord, ...]:
        ...


def evaluate_memory_adapter_manifest(
    manifest: MemoryStoreCapabilityManifest,
) -> MemoryAdapterEvaluation:
    """Classify a memory adapter without contacting the provider."""

    _validate_manifest_privacy(manifest)
    blockers: list[str] = []
    gates: list[str] = list(_LIVE_LEGAL_MEMORY_GATES)
    reasons: list[str] = []

    if manifest.stores_raw_payloads_by_default:
        blockers.append("stores_raw_payloads_by_default")
    if manifest.default_for_legal_memory and not manifest.approved_for_live_legal_memory:
        blockers.append("external_default_requires_explicit_live_legal_approval")
    if not manifest.supports_tenant_isolation:
        blockers.append("missing_tenant_isolation")
    if not manifest.supports_raw_payload_blocking:
        blockers.append("missing_raw_payload_blocking")
    if not manifest.supports_human_review_gate:
        blockers.append("missing_human_review_gate")

    if not manifest.supports_delete or not manifest.supports_export:
        gates.append("deletion_export_evidence")
    if manifest.network_required or manifest.requires_secrets:
        gates.append("security_secret_review")
    if manifest.data_residency in {"unknown", "requires_review"}:
        gates.append("data_residency_review")
    if manifest.sanitized_fixture_only:
        gates.append("live_legal_memory_gate")

    if blockers:
        decision = MemoryAdapterDecision.REJECTED_FOR_LEGAL_MEMORY
        reasons.append("hard privacy or approval blocker")
    elif manifest.default_for_legal_memory and manifest.approved_for_live_legal_memory and not manifest.sanitized_fixture_only:
        if _all_live_capabilities(manifest):
            decision = MemoryAdapterDecision.ACCEPTED_FOR_CURRENT_LEGAL_USE
            gates = ()
            reasons.append("all live legal memory gates represented by local manifest")
        else:
            decision = MemoryAdapterDecision.DEFERRED_FOR_LEGAL_PRODUCTION
            reasons.append("approved default still lacks one or more live legal memory capabilities")
    elif manifest.sanitized_fixture_only:
        decision = MemoryAdapterDecision.ACCEPTED_FOR_SANITIZED_SPIKE
        reasons.append("accepted for synthetic fixture evaluation only")
    else:
        decision = MemoryAdapterDecision.DEFERRED_FOR_LEGAL_PRODUCTION
        reasons.append("not a legal production default")

    return MemoryAdapterEvaluation(
        manifest=manifest,
        decision=decision,
        reasons=tuple(dict.fromkeys(reasons)),
        blockers=tuple(dict.fromkeys(blockers)),
        required_gates=tuple(dict.fromkeys(gates)),
        metadata={
            "privacy": "refs_hashes_lengths_statuses_only",
            "default_for_legal_memory": manifest.default_for_legal_memory,
            "sanitized_fixture_only": manifest.sanitized_fixture_only,
        },
    )


def _all_live_capabilities(manifest: MemoryStoreCapabilityManifest) -> bool:
    return all(
        (
            manifest.supports_memory_records,
            manifest.supports_ttl,
            manifest.supports_delete,
            manifest.supports_export,
            manifest.supports_tenant_isolation,
            manifest.supports_raw_payload_blocking,
            manifest.supports_human_review_gate,
            not manifest.stores_raw_payloads_by_default,
        )
    )


def _validate_manifest_privacy(manifest: MemoryStoreCapabilityManifest) -> None:
    for field_name in ("adapter_id", "provider", "adapter_version", "deployment_model"):
        value = getattr(manifest, field_name)
        if not isinstance(value, str) or not value.strip():
            raise MemoryPrivacyError(f"memory adapter manifest {field_name} must be non-empty")
        if _SECRET_VALUE_PATTERN.search(value):
            raise MemoryPrivacyError(f"memory adapter manifest {field_name} contains secret-like value")
    for ref in manifest.source_refs:
        if not isinstance(ref, str) or not ref.strip():
            raise MemoryPrivacyError("memory adapter manifest source_refs must be non-empty strings")
        if _SECRET_VALUE_PATTERN.search(ref):
            raise MemoryPrivacyError("memory adapter manifest source_refs contain secret-like value")
    _safe_metadata(manifest.metadata)


def _safe_metadata(value: object, path: str = "$") -> JsonObject:
    if not isinstance(value, Mapping):
        raise MemoryPrivacyError(f"memory adapter metadata must be an object at {path}")
    output: JsonObject = {}
    for key, child in value.items():
        key_text = str(key)
        child_path = f"{path}.{key_text}"
        if key_text in _FORBIDDEN_KEYS or _SECRET_KEY_PATTERN.search(key_text):
            raise MemoryPrivacyError(f"memory adapter metadata contains forbidden field at {child_path}")
        output[key_text] = _safe_value(child, child_path)
    return json.loads(json.dumps(output, ensure_ascii=False, sort_keys=True))


def _safe_value(value: object, path: str) -> object:
    if isinstance(value, Mapping):
        return _safe_metadata(value, path)
    if isinstance(value, list | tuple):
        return [_safe_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, str) and _SECRET_VALUE_PATTERN.search(value):
        raise MemoryPrivacyError(f"memory adapter metadata contains secret-like value at {path}")
    return value


_LIVE_LEGAL_MEMORY_GATES = (
    "privacy_review",
    "tenant_isolation_evidence",
    "deletion_export_evidence",
    "data_residency_review",
    "security_secret_review",
    "human_review_policy",
    "latency_relevance_eval",
)
_FORBIDDEN_KEYS = {
    "callback_body",
    "case_facts",
    "customer_document_text",
    "document_text",
    "feedback_message_text",
    "full_text",
    "message_text",
    "payload_text",
    "raw_payload",
    "raw_text",
}
_SECRET_KEY_PATTERN = re.compile(r"(api[_-]?key|token|secret|password|encoding[_-]?aes[_-]?key)", re.IGNORECASE)
_SECRET_VALUE_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN|password\s*[:=]|secret\s*[:=]|token\s*[:=])",
    re.IGNORECASE,
)


__all__ = [
    "MemoryAdapterDecision",
    "MemoryAdapterEvaluation",
    "MemoryStoreAdapter",
    "MemoryStoreCapabilityManifest",
    "evaluate_memory_adapter_manifest",
]
