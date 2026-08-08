---
phase: 107-arena-engine-modes-1-2
plan: 02
status: complete
requirements: [ENGINE-07, SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-07]
---

# Plan 02: ArtifactStore + GuardrailBoundary + ProvenanceLogger - Summary

## What Was Built

- **ArtifactStore** (`artifact_store.py`) — file-based persistence for arena round outputs. Every agent's structured output per round is written to disk as JSON at `{storage_dir}/{arena_id}/{agent_slot}/round_{round}.json`. The returned `RoundArtifact` carries `raw_payload_ref` as a file path reference (not the full content), honouring the reference-first logging rule.
- **GuardrailBoundary** (`guardrail_boundary.py`) — post-hoc guardrail enforcement at the arena-engine boundary for external ACP agents. `apply_post_hoc_guardrails` is the ONLY public entry point and always calls `enforce_citation_audit` + `de_ai_polish` when `is_external=True` (non-bypassable, verified by static AST analysis). Self-built agents skip post-hoc guardrails because v3.0 guardrails run in `turn_loop.py`.
- **ProvenanceLogger** (`provenance.py`) — per-claim agent → reviewer → source chain logging. Each claim is stored with `claim_ref` as a SHA-256 hash prefix (first 32 chars), NOT the full claim text. `reviewer_slot` is `None` for Phase 107 (cross-review is Phase 108).
- All three modules use frozen slotted dataclasses for their result types (`RoundArtifact`, `GuardrailResult`, `ProvenanceChain`).
- All three modules import and use existing v3.0 guardrail functions from `inkstatute_agent_core` AS-IS — no modifications to agent-core.

## Tasks Completed

- [x] Task 1: ArtifactStore with reference-first logging
- [x] Task 2: GuardrailBoundary — post-hoc citation audit + de-AI polish + high-risk review
- [x] Task 3: ProvenanceLogger — per-claim agent → reviewer → source chain

## Verification Results

All three task verify commands passed:

```
Task 1: python -m unittest discover -s packages/arena-engine/tests -p "test_artifact_store.py" -v
  → Ran 6 tests in 0.002s — OK

Task 2: python -m unittest discover -s packages/arena-engine/tests -p "test_guardrail_boundary.py" -v
  → Ran 8 tests in 0.009s — OK

Task 3: python -m unittest discover -s packages/arena-engine/tests -p "test_provenance.py" -v
  → Ran 7 tests in 0.002s — OK

Full suite: python -m unittest discover -s packages/arena-engine/tests -p "test_*.py" -v
  → Ran 37 tests in 0.094s — OK
```

## Artifacts Produced

- `arena_engine.artifact_store.RoundArtifact` — frozen slotted artifact dataclass with `raw_payload_ref` as file path
- `arena_engine.artifact_store.ArtifactStore` — file-based persistence with reference-first logging
- `arena_engine.guardrail_boundary.GuardrailResult` — frozen slotted guardrail result dataclass
- `arena_engine.guardrail_boundary.apply_post_hoc_guardrails` — post-hoc guardrail function for external agents (non-bypassable)
- `arena_engine.guardrail_boundary._is_high_risk_legal_conclusion` — high-risk keyword detection (SAFE-04)
- `arena_engine.guardrail_boundary._HIGH_RISK_KEYWORDS` — keyword set for SAFE-04 (违法, 无效, 撤销, etc.)
- `arena_engine.provenance.ProvenanceChain` — frozen slotted provenance record with hash `claim_ref`
- `arena_engine.provenance.ProvenanceLogger` — per-claim provenance logging with hash references
- `tests/test_artifact_store.py::ArtifactStoreTests` — 6 tests covering all ArtifactStore behaviours
- `tests/test_guardrail_boundary.py::GuardrailBoundaryTests` — 8 tests covering SAFE-01..04 (including non-bypassable AST verification)
- `tests/test_provenance.py::ProvenanceLoggerTests` — 7 tests covering all ProvenanceLogger behaviours

## Notes

- The `packages/arena-engine/` package scaffold (pyproject.toml, __init__.py) was created by Plan 01 in parallel. Plan 02 added the `__init__.py` re-exports for the three new modules without removing Plan 01's existing content (mock_acp, slot_runner).
- `apply_post_hoc_guardrails` is an `async` function because `enforce_citation_audit` from `inkstatute_agent_core.guardrails` is itself async (it delegates to the async `citations.audit()`).
- Test 8 (non-bypassable) uses `ast.parse()` + `inspect.getsource()` to statically verify that (a) `apply_post_hoc_guardrails` is the only public function, (b) it always calls `enforce_citation_audit` and `de_ai_polish`, and (c) the guardrail calls are NOT inside the `is_external=False` skip branch.
- All guardrail functions in `inkstatute_agent_core` were used AS-IS — no modifications to agent-core were made.
- No existing guardrail functions were modified. All imports use the existing v3.0 signatures.
