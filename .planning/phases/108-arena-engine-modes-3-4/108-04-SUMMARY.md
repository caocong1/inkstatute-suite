---
phase: 108-arena-engine-modes-3-4
plan: 04
status: complete
requirements: [ENGINE-03, ENGINE-04, SAFE-06]
---

# Plan 04: Engine Dispatch + BackendAdapter Protocol + Mock ACP + Re-exports - Summary

## Objective

Wire Modes 3 and 4 into the `ArenaEngine` dispatch, add `backend_family()` to the `BackendAdapter` Protocol and `MockACPBackendAdapter`, update `__init__.py` re-exports, and add engine-level integration tests that verify the full dispatch path from `ArenaEngine.run()` through Mode 3 and Mode 4 execution.

## Tasks Completed

### Task 1: Add backend_family() to BackendAdapter Protocol + MockACPBackendAdapter

**Files modified:**
- `packages/platform-runtime/src/platform_runtime/protocols.py` — Added `def backend_family(self) -> str: ...` to the `BackendAdapter` Protocol (after `backend_id()`).
- `packages/arena-engine/src/arena_engine/mock_acp.py` — Added `backend_family: str | None = None` parameter to `MockACPBackendAdapter.__init__()`. Added `backend_family()` method that returns the explicit family when provided, or auto-derives via `get_backend_family(self._backend_id)` from `families.py`. Imported `get_backend_family` from `.families`.
- `packages/arena-engine/tests/test_mock_acp.py` — Added `MockACPBackendFamilyTests` class with 4 tests covering explicit family, auto-derive from known backend_id, auto-derive for unknown backend (defaults to own ID), and backward compatibility of `backend_id()`.

**Verification:** 10 tests pass (6 existing + 4 new), zero regressions.

### Task 2: ArenaEngine dispatch for Mode 3 + Mode 4 + guardrail/provenance wiring

**Files modified:**
- `packages/arena-engine/src/arena_engine/engine.py`:
  - Added imports for `run_mode3_arena_review`, `Mode3Result` from `.mode3` and `run_mode4_adversarial`, `Mode4Result` from `.mode4`.
  - Updated `_results` type hint to include `Mode3Result | Mode4Result`.
  - Added `self._synthesis_adapters` and `self._adversarial_adapters` dicts to `__init__`.
  - Added `register_synthesis_adapter(arena_id, adapter)` and `register_adversarial_adapter(arena_id, adapter)` methods.
  - Added Mode 3 dispatch branch (`"mode3_arena_review"`): builds `backend_families` dict via `_build_backend_families()`, calls `run_mode3_arena_review()`, stores result, applies guardrails to synthesis output.
  - Added Mode 4 dispatch branch (`"mode4_adversarial"`): builds `backend_families` dict, calls `run_mode4_adversarial()` with synthesis + adversarial adapters, stores result, applies guardrails to final synthesis output.
  - Added `_build_backend_families()` static method that calls `adapter.backend_family()` for each slot adapter.
  - Updated docstrings to mention Modes 3+4.
- `packages/arena-engine/tests/test_engine.py` — Added `Mode3Mode4DispatchTests` class with 9 tests covering Mode 3 dispatch, Mode 4 dispatch, distinct synthesis/adversarial adapters, guardrail application to synthesis outputs, backend_family usage for cross-family enforcement, unknown mode ValueError, and Mode 1/2 no-regression.

**Verification:** 22 tests pass (13 existing + 9 new), zero regressions.

### Task 3: Update __init__.py re-exports + run full gate suite

**Files modified:**
- `packages/arena-engine/src/arena_engine/__init__.py`:
  - Added imports from `.mode3` (`Mode3Result`, `run_mode3_arena_review`) and `.mode4` (`Mode4Result`, `SynthesisRound`, `run_mode4_adversarial`).
  - Added all 5 new names to `__all__`.
  - Updated module docstring to mention Modes 3+4 (Arena Review + Adversarial).

**Verification:** Full arena-engine test suite passes — 128 tests, zero failures. AST gate tests (ENGINE-05: no LLM imports, ENGINE-06: no session/resume) pass with mode3.py and mode4.py included.

## Commits

1. `feat(108-04): add backend_family() to BackendAdapter Protocol + MockACPBackendAdapter` (378426a)
2. `feat(108-04): ArenaEngine dispatch for Mode 3 + Mode 4 + guardrail/provenance wiring` (a01a37c)
3. `feat(108-04): update __init__.py re-exports for Mode 3/4 + full gate suite passes` (d2a0069)

## Key Design Decisions

- **BackendAdapter Protocol** — `backend_family()` is a signature-only Protocol method (not `@runtime_checkable`), so existing implementations that don't have it won't break at runtime. The engine's `_build_backend_families()` has a fallback to `backend_id()` if `backend_family()` raises.
- **MockACPBackendAdapter** — `backend_family` parameter is optional with `None` default, ensuring full backward compatibility. Auto-derivation via `get_backend_family()` uses `DEFAULT_FAMILY_MAP` for known backends and defaults to the backend's own ID for unknown ones.
- **ArenaEngine dispatch** — Mode 3 and Mode 4 use separate `register_synthesis_adapter()` and `register_adversarial_adapter()` methods rather than overloading `register_adapters()`, keeping the slot adapter map clean and making the "orchestrator never produces content" invariant explicit.
- **Guardrail application** — Post-hoc guardrails are applied to the synthesis output (Mode 3) and final synthesis output (Mode 4) using the same `_apply_guardrails_and_provenance()` method, with the synthesis adapter's `backend_id` determining the `is_external` flag.

## Test Coverage

| Test Suite | Tests | Status |
|---|---|---|
| test_mock_acp | 10 | PASS |
| test_engine | 22 | PASS |
| test_mode3 | 21 | PASS |
| test_mode4 | 18 | PASS |
| test_no_llm_imports | 2 | PASS |
| test_fresh_context | 2 | PASS |
| All other arena-engine tests | 53 | PASS |
| **Total** | **128** | **ALL PASS** |
