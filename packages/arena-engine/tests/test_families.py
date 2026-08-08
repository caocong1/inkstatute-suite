"""Tests for families.py — cross-family enforcement and degradation (SAFE-06).

Covers: backend family mapping, cross-family pairing algorithm, explicit
degradation for same-family-only and single-agent cases, frozen slotted
dataclass shape.
"""

from __future__ import annotations

import dataclasses
import unittest

from arena_engine.families import (
    CrossFamilyPairingResult,
    DEFAULT_FAMILY_MAP,
    _pair_cross_family,
    get_backend_family,
)


class CrossFamilyEnforcementTests(unittest.TestCase):
    """Cover all 8 behaviors from Plan 108-01 Task 2."""

    # ------------------------------------------------------------------
    # Test 1: known backend → family mappings
    # ------------------------------------------------------------------

    def test_known_backend_family_mappings(self) -> None:
        self.assertEqual(get_backend_family("hermes"), "claude")
        self.assertEqual(get_backend_family("codex"), "gpt")
        self.assertEqual(get_backend_family("gemini-cli"), "gemini")
        self.assertEqual(get_backend_family("inkstatute-agent"), "inkstatute")

    # ------------------------------------------------------------------
    # Test 2: unknown backend defaults to its own ID
    # ------------------------------------------------------------------

    def test_unknown_backend_defaults_to_own_id(self) -> None:
        self.assertEqual(get_backend_family("unknown-backend"), "unknown-backend")

    # ------------------------------------------------------------------
    # Test 3: 4 slots, 2 families — all cross-paired
    # ------------------------------------------------------------------

    def test_four_slots_two_families_all_cross_paired(self) -> None:
        slots = ["slot-0", "slot-1", "slot-2", "slot-3"]
        families = {
            "slot-0": "claude",
            "slot-1": "claude",
            "slot-2": "gpt",
            "slot-3": "gpt",
        }
        result = _pair_cross_family(slots, families)
        self.assertFalse(result.degraded)
        self.assertEqual(result.reason, "")
        # Every pair satisfies cross-family constraint.
        for reviewer, reviewed in result.pairs.items():
            self.assertNotEqual(
                families[reviewer],
                families[reviewed],
                f"{reviewer} ({families[reviewer]}) reviewed "
                f"{reviewed} ({families[reviewed]}) — same family!",
            )
        # All slots are paired.
        self.assertEqual(set(result.pairs.keys()), set(slots))
        self.assertEqual(set(result.pairs.values()), set(slots))

    # ------------------------------------------------------------------
    # Test 4: all same family → explicit degradation
    # ------------------------------------------------------------------

    def test_all_same_family_degrades_explicitly(self) -> None:
        slots = ["slot-0", "slot-1"]
        families = {"slot-0": "claude", "slot-1": "claude"}
        result = _pair_cross_family(slots, families)
        self.assertTrue(result.degraded)
        self.assertEqual(result.reason, "same_family_only")
        self.assertEqual(result.pairs, {})

    # ------------------------------------------------------------------
    # Test 5: single slot → explicit degradation
    # ------------------------------------------------------------------

    def test_single_slot_degrades_explicitly(self) -> None:
        result = _pair_cross_family(["slot-0"], {"slot-0": "claude"})
        self.assertTrue(result.degraded)
        self.assertEqual(result.reason, "single_agent")
        self.assertEqual(result.pairs, {})

    # ------------------------------------------------------------------
    # Test 6: 3 slots, 2 same family + 1 different — all cross-paired
    # ------------------------------------------------------------------

    def test_three_slots_mixed_families(self) -> None:
        slots = ["slot-0", "slot-1", "slot-2"]
        families = {
            "slot-0": "claude",
            "slot-1": "claude",
            "slot-2": "gpt",
        }
        result = _pair_cross_family(slots, families)
        # All pairs must satisfy cross-family constraint.
        for reviewer, reviewed in result.pairs.items():
            self.assertNotEqual(families[reviewer], families[reviewed])

    # ------------------------------------------------------------------
    # Test 7: CrossFamilyPairingResult is frozen slotted dataclass
    # ------------------------------------------------------------------

    def test_pairing_result_is_frozen_slotted_dataclass(self) -> None:
        # frozen
        result = CrossFamilyPairingResult(
            pairs={"a": "b"},
            degraded=False,
            reason="",
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.degraded = True  # type: ignore[misc]

        # slots
        self.assertTrue(hasattr(CrossFamilyPairingResult, "__slots__"))
        self.assertNotIn("__dict__", dir(CrossFamilyPairingResult))

        # fields
        field_names = {f.name for f in dataclasses.fields(CrossFamilyPairingResult)}
        self.assertEqual(field_names, {"pairs", "degraded", "reason", "metadata"})

    # ------------------------------------------------------------------
    # Test 8: degraded=True always has non-empty reason
    # ------------------------------------------------------------------

    def test_degraded_has_non_empty_reason(self) -> None:
        single = _pair_cross_family(["slot-0"], {"slot-0": "claude"})
        self.assertTrue(single.degraded)
        self.assertIn(single.reason, {"same_family_only", "single_agent"})
        self.assertNotEqual(single.reason, "")

        same = _pair_cross_family(
            ["slot-0", "slot-1"],
            {"slot-0": "claude", "slot-1": "claude"},
        )
        self.assertTrue(same.degraded)
        self.assertIn(same.reason, {"same_family_only", "single_agent"})
        self.assertNotEqual(same.reason, "")


if __name__ == "__main__":
    unittest.main()
