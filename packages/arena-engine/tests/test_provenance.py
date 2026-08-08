"""Tests for ProvenanceLogger — per-claim agent → reviewer → source chain (SAFE-07)."""

from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from inkstatute_agent_core.citations import CitationAudit, CitationAuditItem
from inkstatute_agent_core.citations.extract import CitationKind

from arena_engine.provenance import ProvenanceChain, ProvenanceLogger


def _make_audit_with_items() -> CitationAudit:
    """Build a CitationAudit with one item for Test 3."""
    return CitationAudit(
        items=[
            CitationAuditItem(
                kind=CitationKind.LAW,
                source="民法典",
                reference="第143条",
                status="verified",
                tier="L1-法规（本地库）",
            )
        ],
        total=1,
        verified=1,
        retrieved=0,
        unverified=0,
    )


def _make_audit_empty() -> CitationAudit:
    """Build a CitationAudit with zero items for Test 4."""
    return CitationAudit(
        items=[],
        total=0,
        verified=0,
        retrieved=0,
        unverified=0,
    )


class ProvenanceLoggerTests(unittest.TestCase):
    """Cover all 7 ProvenanceLogger behaviours from Plan 107-02 Task 3."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.storage_dir = self._tmp.name
        self.logger = ProvenanceLogger(storage_dir=self.storage_dir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # Test 1 — log_claim stores a record; get_chain returns it
    def test_log_claim_and_get_chain(self) -> None:
        claim = "根据《民法典》第143条"
        chain = self.logger.log_claim(
            arena_id="a-1",
            claim=claim,
            agent_slot="slot-0",
            citation_audit=_make_audit_with_items(),
            reviewer_slot=None,
        )
        self.assertIsInstance(chain, ProvenanceChain)
        results = self.logger.get_chain(arena_id="a-1", claim=claim)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].agent_slot, "slot-0")

    # Test 2 — ProvenanceChain is frozen slotted dataclass with correct fields
    def test_provenance_chain_is_frozen_slotted(self) -> None:
        self.assertTrue(dataclasses.is_dataclass(ProvenanceChain))
        chain = ProvenanceChain(
            claim_ref="abc123",
            agent_slot="slot-0",
            reviewer_slot=None,
            source="",
            tier=None,
            timestamp="2026-01-01T00:00:00+00:00",
        )
        with self.assertRaises((AttributeError, dataclasses.FrozenInstanceError)):
            chain.agent_slot = "mutated"  # type: ignore[misc]
        field_names = {f.name for f in dataclasses.fields(ProvenanceChain)}
        self.assertEqual(
            field_names,
            {"claim_ref", "agent_slot", "reviewer_slot", "source", "tier", "timestamp"},
        )
        # reviewer_slot is None for Phase 107
        self.assertIsNone(chain.reviewer_slot)

    # Test 3 — source and tier populated from first citation item
    def test_source_and_tier_from_citation_items(self) -> None:
        claim = "根据《民法典》第143条"
        chain = self.logger.log_claim(
            arena_id="a-1",
            claim=claim,
            agent_slot="slot-0",
            citation_audit=_make_audit_with_items(),
        )
        self.assertEqual(chain.source, "民法典")
        self.assertEqual(chain.tier, "L1-法规（本地库）")

    # Test 4 — empty citation_audit → source="" and tier=None
    def test_empty_citation_audit_source_and_tier(self) -> None:
        claim = "some claim"
        chain = self.logger.log_claim(
            arena_id="a-1",
            claim=claim,
            agent_slot="slot-0",
            citation_audit=_make_audit_empty(),
        )
        self.assertEqual(chain.source, "")
        self.assertIsNone(chain.tier)

    # Test 5 — get_all_chains returns all entries for an arena
    def test_get_all_chains(self) -> None:
        self.logger.log_claim(
            arena_id="a-1",
            claim="claim one",
            agent_slot="slot-0",
            citation_audit=_make_audit_with_items(),
        )
        self.logger.log_claim(
            arena_id="a-1",
            claim="claim two",
            agent_slot="slot-1",
            citation_audit=_make_audit_empty(),
        )
        all_chains = self.logger.get_all_chains(arena_id="a-1")
        self.assertEqual(len(all_chains), 2)

    # Test 6 — stored JSON does NOT contain full claim text, only claim_ref
    def test_reference_first_logging_no_full_claim_text(self) -> None:
        claim = "根据《民法典》第143条，这是一个很长的声明文本"
        self.logger.log_claim(
            arena_id="a-1",
            claim=claim,
            agent_slot="slot-0",
            citation_audit=_make_audit_with_items(),
        )
        file_path = Path(self.storage_dir) / "a-1" / "provenance.json"
        self.assertTrue(file_path.exists())
        raw = file_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        entry = data[0]
        # claim_ref is a hash, not the full claim
        self.assertIn("claim_ref", entry)
        self.assertNotEqual(entry["claim_ref"], claim)
        # The full claim text must NOT appear in the stored JSON
        self.assertNotIn(claim, raw)

    # Test 7 — multiple log_claim for same claim from different agents
    def test_multiple_agents_same_claim(self) -> None:
        claim = "根据《民法典》第143条"
        self.logger.log_claim(
            arena_id="a-1",
            claim=claim,
            agent_slot="slot-0",
            citation_audit=_make_audit_with_items(),
        )
        self.logger.log_claim(
            arena_id="a-1",
            claim=claim,
            agent_slot="slot-1",
            citation_audit=_make_audit_empty(),
        )
        results = self.logger.get_chain(arena_id="a-1", claim=claim)
        self.assertEqual(len(results), 2)
        # Insertion order preserved
        self.assertEqual(results[0].agent_slot, "slot-0")
        self.assertEqual(results[1].agent_slot, "slot-1")


if __name__ == "__main__":
    unittest.main()
