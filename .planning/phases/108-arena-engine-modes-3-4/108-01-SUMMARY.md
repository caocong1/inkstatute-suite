---
phase: 108-arena-engine-modes-3-4
plan: 01
status: complete
requirements: [SAFE-06]
---

# Plan 01: Structured Review Output + Cross-Family Pairing Primitives - Summary

## What Was Built

- **`review.py`** — Structured review output primitives for Modes 3+4:
  - `ConfidenceLevel` enum with exactly 3 categorical members (Certain/Likely/Possible) — NO numeric percentages
  - `SeverityLevel` enum with exactly 3 members (High/Medium/Low)
  - `ReviewFinding` frozen slotted dataclass with description, confidence, severity, confirmed, source_slot, reviewed_slot, metadata
  - `_parse_review_findings()` regex parser extracting `[FINDING]...[/FINDING]` blocks from agent output with sensible defaults
  - Numeric confidence strings (e.g. "67%") rejected — fall back to `ConfidenceLevel.POSSIBLE`
  - `to_json()`/`from_json()` round-trip compatible with `ArenaReviewCompletedPayload.findings`

- **`families.py`** — Cross-family review enforcement (SAFE-06):
  - `DEFAULT_FAMILY_MAP` with known backend→family mappings (hermes→claude, codex→gpt, gemini-cli→gemini, inkstatute-agent→inkstatute)
  - `get_backend_family()` resolves known backends to families; unknown backends default to their own ID
  - `CrossFamilyPairingResult` frozen slotted dataclass with pairs, degraded, reason, metadata
  - `_pair_cross_family()` greedy cyclic pairing algorithm ensuring `families[reviewer] != families[reviewed]`
  - Explicit degradation (never silent) for same-family-only (`reason="same_family_only"`), single-agent (`reason="single_agent"`), and partial (`reason="partial_same_family"`) cases

- **`__init__.py`** — Updated to re-export all new primitives (`ReviewFinding`, `ConfidenceLevel`, `SeverityLevel`, `get_backend_family`, `CrossFamilyPairingResult`, `DEFAULT_FAMILY_MAP`) with updated `__all__` and module docstring

## Tasks Completed

- [x] Task 1: review.py — ReviewFinding, ConfidenceLevel, SeverityLevel, parsing
- [x] Task 2: families.py — backend_family mapping + cross-family pairing + degradation
- [x] Task 3: Re-export review + families from __init__.py

## Verification Results

- `test_review.py` — 9 tests, all pass (enum membership, frozen slotted shape, full block parse, empty content, missing-field defaults, numeric percentage rejection, to_json compatibility, from_json round-trip)
- `test_families.py` — 8 tests, all pass (known mappings, unknown default, 4-slot cross-pairing, same-family degradation, single-agent degradation, 3-slot mixed, frozen slotted shape, non-empty reason on degradation)
- `test_no_llm_imports.py` — 2 tests, all pass (ENGINE-05 AST gate covers new files automatically)
- `test_fresh_context.py` — 2 tests, all pass (ENGINE-06 AST gate covers new files automatically)
- Total: 21 tests, 0 failures

## Artifacts Produced

- `arena_engine.review.ConfidenceLevel` — categorical confidence enum (Certain/Likely/Possible)
- `arena_engine.review.SeverityLevel` — severity enum (High/Medium/Low)
- `arena_engine.review.ReviewFinding` — frozen slotted structured review finding dataclass
- `arena_engine.review._parse_review_findings` — regex parser for `[FINDING]` blocks
- `arena_engine.families.DEFAULT_FAMILY_MAP` — known backend_id → family mappings
- `arena_engine.families.get_backend_family` — backend family resolver
- `arena_engine.families.CrossFamilyPairingResult` — frozen slotted pairing result with degradation flag
- `arena_engine.families._pair_cross_family` — cross-family pairing algorithm with explicit degradation
- `tests/test_review.py` — ReviewFinding parsing and serialization test suite (9 tests)
- `tests/test_families.py` — cross-family enforcement and degradation test suite (8 tests)

## Notes

- Confidence levels are categorical (Certain/Likely/Possible), NOT numeric percentages — this is a binding research anti-pattern enforced in both the parser (rejects "67%") and the enum design.
- Cross-family degradation is always explicit: same-family-only and single-agent cases return `degraded=True` with a non-empty reason string, never silently proceeding.
- `ReviewFinding.to_json()` output is compatible with `ArenaReviewCompletedPayload.findings: list[JsonObject]` from `platform_contract.unified_events`.
- `get_backend_family()` will be called by Mode 3/4 (Plans 02/03) to build the `families` dict for `_pair_cross_family()`.
- `_pair_cross_family()` result drives cross-review pairing in Mode 3 and adversarial pairing in Mode 4.
- `ProvenanceChain.reviewer_slot` field (provenance.py line 38) will be populated by Mode 3/4 using pairing results.
- No LLM provider imports and no session/resume calls in any new file (AST-verified by existing gate tests).
