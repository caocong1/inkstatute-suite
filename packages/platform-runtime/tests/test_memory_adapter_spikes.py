"""Tests for Phase 25: external memory adapter spikes and final recommendation."""

from __future__ import annotations

import unittest

from platform_runtime import (
    AdapterComparisonResult,
    ExternalAdapterSpikeRunner,
    ExternalAdapterSpikeSpec,
    MemoryAdapterRecommendation,
    MemoryEvalRunner,
    canonical_spike_specs,
)

FIXED_NOW = "2026-07-02T18:00:00+00:00"


def make_runner() -> ExternalAdapterSpikeRunner:
    return ExternalAdapterSpikeRunner(clock=lambda: FIXED_NOW)


def make_eval_runner() -> MemoryEvalRunner:
    return MemoryEvalRunner(clock=lambda: FIXED_NOW)


class CanonicalSpikeSpecsTests(unittest.TestCase):
    def test_canonical_specs_returns_three_candidates(self) -> None:
        """XMEM-01/02/03: canonical_spike_specs() returns 3 specs."""
        specs = canonical_spike_specs()
        self.assertEqual(len(specs), 3)

    def test_canonical_spec_ids(self) -> None:
        """Each spec has a unique candidate_id."""
        specs = canonical_spike_specs()
        ids = {s.candidate_id for s in specs}
        self.assertIn("zep_style_graph", ids)
        self.assertIn("reme_style_file_auditable", ids)
        self.assertIn("mem0_style_quick_poc", ids)

    def test_zep_style_spec_documents_raw_payload_risk(self) -> None:
        """XMEM-01: Zep-style spec must mark raw_payload_blocked=False."""
        spec = next(s for s in canonical_spike_specs() if s.candidate_id == "zep_style_graph")
        self.assertFalse(spec.raw_payload_blocked)

    def test_reme_style_spec_passes_hard_gates(self) -> None:
        """XMEM-02: ReMe-style spec must pass all hard gate requirements."""
        spec = next(s for s in canonical_spike_specs() if s.candidate_id == "reme_style_file_auditable")
        self.assertTrue(spec.raw_payload_blocked)
        self.assertTrue(spec.delete_export_support)
        self.assertTrue(spec.human_review_support)
        self.assertTrue(spec.source_refs_support)
        self.assertNotEqual(spec.tenant_isolation, "no_built_in")

    def test_mem0_style_spec_is_poc_only_no_tenant_isolation(self) -> None:
        """XMEM-03: Mem0-style spec must not have tenant isolation (PoC-only)."""
        spec = next(s for s in canonical_spike_specs() if s.candidate_id == "mem0_style_quick_poc")
        self.assertEqual(spec.tenant_isolation, "no_built_in")
        self.assertFalse(spec.raw_payload_blocked)

    def test_all_specs_have_capability_manifests(self) -> None:
        """XMEM-04: all specs must provide a MemoryStoreCapabilityManifest."""
        for spec in canonical_spike_specs():
            with self.subTest(candidate=spec.candidate_id):
                self.assertIsNotNone(spec.capability_manifest)
                self.assertEqual(spec.capability_manifest.adapter_id, spec.candidate_id)

    def test_capability_manifest_documents_required_xmem04_fields(self) -> None:
        """XMEM-04: manifest must record raw_payload_blocking, tenant_isolation, delete, data_residency."""
        for spec in canonical_spike_specs():
            m = spec.capability_manifest
            with self.subTest(candidate=spec.candidate_id):
                # XMEM-04: deployment model
                self.assertNotEqual(m.deployment_model, "")
                # XMEM-04: data residency
                self.assertNotEqual(m.data_residency, "unknown")
                # XMEM-04: secrets
                self.assertIsInstance(m.requires_secrets, bool)
                # XMEM-04: raw payload
                self.assertIsInstance(m.supports_raw_payload_blocking, bool)
                # XMEM-04: tenant isolation
                self.assertIsInstance(m.supports_tenant_isolation, bool)
                # XMEM-04: delete
                self.assertIsInstance(m.supports_delete, bool)


class AdapterComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.native_report = make_eval_runner().run()
        self.spike_runner = make_runner()
        self.specs = canonical_spike_specs()
        self.comparisons = self.spike_runner.compare(self.specs, native_report=self.native_report)

    def test_compare_returns_one_result_per_spec(self) -> None:
        self.assertEqual(len(self.comparisons), len(self.specs))

    def test_zep_style_kept_native_due_to_raw_payload_gate(self) -> None:
        """Zep-style fails raw_payload_blocked hard gate → keep_native."""
        zep = next(c for c in self.comparisons if c.spec.candidate_id == "zep_style_graph")
        self.assertEqual(zep.recommended_action, "keep_native")

    def test_mem0_style_kept_native_due_to_tenant_isolation_gate(self) -> None:
        """Mem0-style fails tenant isolation hard gate → keep_native."""
        mem0 = next(c for c in self.comparisons if c.spec.candidate_id == "mem0_style_quick_poc")
        self.assertEqual(mem0.recommended_action, "keep_native")

    def test_reme_style_gets_defer_or_gate_action(self) -> None:
        """XMEM-02: ReMe passes hard gates; action is defer_external or add_behind_gate."""
        reme = next(c for c in self.comparisons if c.spec.candidate_id == "reme_style_file_auditable")
        self.assertIn(reme.recommended_action, ("defer_external", "add_behind_gate"))

    def test_delta_is_computed_correctly(self) -> None:
        """delta = spike_baseline - native_baseline."""
        native = self.native_report.baseline_score
        for c in self.comparisons:
            expected_delta = round(c.spec.spike_baseline_score - native, 4)
            self.assertAlmostEqual(c.delta, expected_delta, places=4)

    def test_all_comparison_results_have_rationale(self) -> None:
        for c in self.comparisons:
            with self.subTest(candidate=c.spec.candidate_id):
                self.assertGreater(len(c.rationale), 0)


class MemoryAdapterRecommendationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.native_report = make_eval_runner().run()
        self.spike_runner = make_runner()
        self.comparisons = self.spike_runner.compare(canonical_spike_specs(), native_report=self.native_report)
        self.recommendation = self.spike_runner.recommend(
            self.comparisons, native_report=self.native_report
        )

    def test_recommendation_has_recommended_default(self) -> None:
        """XMEM-05: recommendation has a non-empty recommended_default."""
        self.assertGreater(len(self.recommendation.recommended_default), 0)

    def test_recommendation_default_is_native_or_deferred(self) -> None:
        """XMEM-05: recommendation is either native, gated, or deferred (no open-ended options)."""
        valid_prefixes = ("platform_native_only", "defer_all_external", "add_")
        self.assertTrue(
            any(self.recommendation.recommended_default.startswith(p) for p in valid_prefixes),
            f"Unexpected recommendation: {self.recommendation.recommended_default!r}",
        )

    def test_recommendation_has_rationale(self) -> None:
        """XMEM-05: recommendation includes a human-readable rationale."""
        self.assertGreater(len(self.recommendation.rationale), 20)

    def test_recommendation_has_evidence_refs(self) -> None:
        """XMEM-05: recommendation includes evidence_refs for auditability."""
        self.assertEqual(len(self.recommendation.evidence_refs), len(self.comparisons))
        for ref in self.recommendation.evidence_refs:
            self.assertIn("://", ref)

    def test_all_candidates_compared_in_recommendation(self) -> None:
        """XMEM-01/02/03: recommendation comparisons cover all three spike candidates."""
        candidate_ids = {c.spec.candidate_id for c in self.recommendation.comparisons}
        self.assertIn("zep_style_graph", candidate_ids)
        self.assertIn("reme_style_file_auditable", candidate_ids)
        self.assertIn("mem0_style_quick_poc", candidate_ids)

    def test_mem0_not_recommended_as_production_default(self) -> None:
        """XMEM-03: Mem0-style must never be the recommended legal production default."""
        self.assertNotEqual(self.recommendation.recommended_default, "add_mem0_style_quick_poc_behind_gate")


if __name__ == "__main__":
    unittest.main()
