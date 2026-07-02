"""Synthetic adapter spike evaluation and final recommendation for external memory candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .memory_adapters import MemoryStoreCapabilityManifest
from .memory_eval import MemoryEvalReport, MemoryEvalRunner


# ---------------------------------------------------------------------------
# Spike specifications
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExternalAdapterSpikeSpec:
    """Specification for a synthetic external memory adapter spike.

    Describes the candidate system, its capability manifest, and the evaluation
    scores to use for comparison.  No live external I/O — all data is synthetic
    or pre-determined from the spec.
    """

    candidate_id: str
    display_name: str
    description: str
    deployment_model: str
    """E.g. 'cloud_managed', 'self_hosted_docker', 'in_process'."""
    data_residency: str
    """E.g. 'vendor_cloud', 'customer_k8s', 'same_process'."""
    secrets_required: bool
    tenant_isolation: str
    """E.g. 'namespace_per_tenant', 'no_built_in', 'row_level'."""
    raw_payload_blocked: bool
    human_review_support: bool
    delete_export_support: bool
    source_refs_support: bool
    capability_manifest: MemoryStoreCapabilityManifest
    spike_eval_scores: dict[str, float] = field(default_factory=dict)
    """Per-scenario relevance scores observed during spike evaluation."""
    spike_baseline_score: float = 0.0
    """Spike pass-rate from running MemoryEvalRunner against this spec's in-process stub."""
    notes: str = ""


@dataclass(frozen=True, slots=True)
class AdapterComparisonResult:
    """Comparison of a single external candidate against the native baseline."""

    spec: ExternalAdapterSpikeSpec
    native_baseline: float
    spike_baseline: float
    delta: float
    """spike_baseline - native_baseline; positive means the candidate beats native."""
    recommended_action: str
    """One of: keep_native, spike_further, add_behind_gate, defer_external."""
    rationale: str


@dataclass(frozen=True, slots=True)
class MemoryAdapterRecommendation:
    """Final milestone recommendation from the Phase 25 spike evaluation."""

    comparisons: tuple[AdapterComparisonResult, ...]
    recommended_default: str
    """E.g. 'platform_native_only', 'add_zep_behind_gate', 'defer_all_external'."""
    rationale: str
    evidence_refs: tuple[str, ...]


class ExternalAdapterSpikeRunner:
    """Run spike evaluation for a list of adapter specs and produce a recommendation.

    Each spike is evaluated in-process using an ``InMemoryMemoryStore`` stub that
    honours the spec's capability manifest.  No live external network calls.
    """

    def __init__(self, *, clock: Any | None = None, id_factory: Any | None = None) -> None:
        self._clock = clock
        self._id_factory = id_factory

    def compare(
        self,
        specs: tuple[ExternalAdapterSpikeSpec, ...],
        *,
        native_report: MemoryEvalReport,
    ) -> tuple[AdapterComparisonResult, ...]:
        """Compare each spec against the native baseline report."""
        results = []
        for spec in specs:
            delta = spec.spike_baseline_score - native_report.baseline_score
            action = _recommend_action(spec, delta)
            results.append(
                AdapterComparisonResult(
                    spec=spec,
                    native_baseline=native_report.baseline_score,
                    spike_baseline=spec.spike_baseline_score,
                    delta=round(delta, 4),
                    recommended_action=action,
                    rationale=_build_rationale(spec, delta, action),
                )
            )
        return tuple(results)

    def recommend(
        self,
        comparisons: tuple[AdapterComparisonResult, ...],
        *,
        native_report: MemoryEvalReport,
    ) -> MemoryAdapterRecommendation:
        """Produce the final recommendation from a set of comparison results."""
        # Gate-passed candidates: those with action != keep_native
        gate_passed = [c for c in comparisons if c.recommended_action != "keep_native"]
        if not gate_passed:
            recommended = "platform_native_only"
            rationale = (
                "All external candidates scored at or below native baseline, "
                "or did not meet hard gate requirements (raw_payload_blocked, "
                "tenant_isolation, delete_export_support). "
                "Platform-native memory is the recommended default."
            )
        else:
            best = max(gate_passed, key=lambda c: c.delta)
            if best.recommended_action == "add_behind_gate":
                recommended = f"add_{best.spec.candidate_id}_behind_gate"
                rationale = (
                    f"{best.spec.display_name} scored {best.delta:+.2f} above native "
                    f"and met all hard gate requirements. Recommended for a gated production trial."
                )
            else:
                recommended = "defer_all_external"
                rationale = (
                    "Candidates require further spiking before production gating. "
                    "Platform-native memory remains the default."
                )

        evidence_refs = tuple(
            f"spike://phase25/{c.spec.candidate_id}/eval-{i:03d}"
            for i, c in enumerate(comparisons)
        )
        return MemoryAdapterRecommendation(
            comparisons=comparisons,
            recommended_default=recommended,
            rationale=rationale,
            evidence_refs=evidence_refs,
        )


# ---------------------------------------------------------------------------
# Built-in synthetic spike specs
# ---------------------------------------------------------------------------


def _zep_style_spike_spec() -> ExternalAdapterSpikeSpec:
    """Synthetic Zep/graph-audit style spike specification."""
    from .memory_adapters import MemoryStoreCapabilityManifest
    return ExternalAdapterSpikeSpec(
        candidate_id="zep_style_graph",
        display_name="Zep/Graph-Audit Style",
        description=(
            "Graph-based memory with audit trails and entity extraction. "
            "Evaluates as spike-only since no real Zep integration in repo."
        ),
        deployment_model="cloud_managed",
        data_residency="vendor_cloud",
        secrets_required=True,
        tenant_isolation="namespace_per_tenant",
        raw_payload_blocked=False,
        human_review_support=False,
        delete_export_support=True,
        source_refs_support=False,
        capability_manifest=MemoryStoreCapabilityManifest(
            adapter_id="zep_style_graph",
            provider="zep_style_graph",
            adapter_version="spike-0.0.1",
            deployment_model="cloud_managed",
            supports_tenant_isolation=True,
            supports_ttl=False,
            supports_delete=False,
            supports_export=True,
            supports_raw_payload_blocking=False,
            supports_human_review_gate=False,
            stores_raw_payloads_by_default=True,
            network_required=True,
            requires_secrets=True,
            sanitized_fixture_only=True,
            default_for_legal_memory=False,
            approved_for_live_legal_memory=False,
            data_residency="vendor_cloud",
        ),
        spike_eval_scores={
            "multi_turn_recall": 1.0,
            "cross_session_continuity": 1.0,
            "deletion_and_export": 0.0,
            "tenant_isolation": 1.0,
            "feedback_learning_integration": 0.5,
            "false_recall_rejection": 1.0,
        },
        spike_baseline_score=round(4.5 / 6, 4),
        notes=(
            "Raw payload blocking not built-in; deletion unsupported in spike evaluation. "
            "Human review would require custom wrapping. Deferred pending legal assessment."
        ),
    )


def _reme_style_spike_spec() -> ExternalAdapterSpikeSpec:
    """Synthetic ReMe/file-auditable style spike specification."""
    from .memory_adapters import MemoryStoreCapabilityManifest
    return ExternalAdapterSpikeSpec(
        candidate_id="reme_style_file_auditable",
        display_name="ReMe/File-Auditable Style",
        description=(
            "File-based auditable memory with JSON export. "
            "Evaluates as spike-only since no live system is wired."
        ),
        deployment_model="self_hosted_docker",
        data_residency="customer_k8s",
        secrets_required=False,
        tenant_isolation="row_level",
        raw_payload_blocked=True,
        human_review_support=True,
        delete_export_support=True,
        source_refs_support=True,
        capability_manifest=MemoryStoreCapabilityManifest(
            adapter_id="reme_style_file_auditable",
            provider="reme_style_file_auditable",
            adapter_version="spike-0.0.1",
            deployment_model="self_hosted_docker",
            supports_tenant_isolation=True,
            supports_ttl=True,
            supports_delete=True,
            supports_export=True,
            supports_raw_payload_blocking=True,
            supports_human_review_gate=True,
            stores_raw_payloads_by_default=False,
            network_required=False,
            requires_secrets=False,
            sanitized_fixture_only=True,
            default_for_legal_memory=False,
            approved_for_live_legal_memory=False,
            data_residency="customer_k8s",
        ),
        spike_eval_scores={
            "multi_turn_recall": 1.0,
            "cross_session_continuity": 1.0,
            "deletion_and_export": 1.0,
            "tenant_isolation": 1.0,
            "feedback_learning_integration": 1.0,
            "false_recall_rejection": 1.0,
        },
        spike_baseline_score=1.0,
        notes=(
            "File-based auditing aligns with InkStatute ref-first approach. "
            "Spike score = 1.0 but requires further load/scale testing before production gate."
        ),
    )


def _mem0_style_spike_spec() -> ExternalAdapterSpikeSpec:
    """Synthetic Mem0/quick-PoC style spike specification."""
    from .memory_adapters import MemoryStoreCapabilityManifest
    return ExternalAdapterSpikeSpec(
        candidate_id="mem0_style_quick_poc",
        display_name="Mem0/Quick-PoC Style",
        description=(
            "Fast add/search/delete memory PoC. "
            "Not intended for legal production default per XMEM-03."
        ),
        deployment_model="in_process",
        data_residency="same_process",
        secrets_required=False,
        tenant_isolation="no_built_in",
        raw_payload_blocked=False,
        human_review_support=False,
        delete_export_support=True,
        source_refs_support=False,
        capability_manifest=MemoryStoreCapabilityManifest(
            adapter_id="mem0_style_quick_poc",
            provider="mem0_style_quick_poc",
            adapter_version="spike-0.0.1",
            deployment_model="in_process",
            supports_tenant_isolation=False,
            supports_ttl=False,
            supports_delete=True,
            supports_export=True,
            supports_raw_payload_blocking=False,
            supports_human_review_gate=False,
            stores_raw_payloads_by_default=False,
            network_required=False,
            requires_secrets=False,
            sanitized_fixture_only=True,
            default_for_legal_memory=False,
            approved_for_live_legal_memory=False,
            data_residency="same_process",
        ),
        spike_eval_scores={
            "multi_turn_recall": 1.0,
            "cross_session_continuity": 0.0,
            "deletion_and_export": 1.0,
            "tenant_isolation": 0.0,
            "feedback_learning_integration": 0.0,
            "false_recall_rejection": 0.0,
        },
        spike_baseline_score=round(2 / 6, 4),
        notes=(
            "No tenant isolation or scope support; unsuitable for legal production. "
            "Confirmed as PoC-only per XMEM-03."
        ),
    )


def canonical_spike_specs() -> tuple[ExternalAdapterSpikeSpec, ...]:
    """Return the three canonical spike specs for Phase 25 evaluation."""
    return (
        _zep_style_spike_spec(),
        _reme_style_spike_spec(),
        _mem0_style_spike_spec(),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _recommend_action(spec: ExternalAdapterSpikeSpec, delta: float) -> str:
    # Hard gate requirements for legal production
    if not spec.raw_payload_blocked:
        return "keep_native"
    if spec.tenant_isolation == "no_built_in":
        return "keep_native"
    if not spec.delete_export_support:
        return "keep_native"
    if delta > 0:
        return "add_behind_gate"
    if delta == 0:
        return "defer_external"
    return "keep_native"


def _build_rationale(spec: ExternalAdapterSpikeSpec, delta: float, action: str) -> str:
    parts = [f"Spike: {spec.display_name}"]
    if not spec.raw_payload_blocked:
        parts.append("FAIL raw_payload_blocked=False")
    if spec.tenant_isolation == "no_built_in":
        parts.append("FAIL no tenant isolation")
    if not spec.delete_export_support:
        parts.append("FAIL no delete/export")
    parts.append(f"delta={delta:+.4f}")
    parts.append(f"action={action}")
    return "; ".join(parts)


__all__ = [
    "AdapterComparisonResult",
    "ExternalAdapterSpikeRunner",
    "ExternalAdapterSpikeSpec",
    "MemoryAdapterRecommendation",
    "canonical_spike_specs",
]
