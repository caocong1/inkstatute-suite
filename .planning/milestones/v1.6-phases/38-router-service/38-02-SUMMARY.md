# Plan 38-02 Summary — SKILL Strategy, Mapper Injection, and None Fallback

## Plan ID
- **Phase:** 38 (Router Service)
- **Plan:** 02
- **Title:** SKILL strategy with Skill Registry integration, mapper injection, and None fallback
- **Wave:** 2
- **Requirements:** ROUTER-02, ROUTER-01

## Tasks Completed

### Task 01 — Complete SKILL strategy with full Skill Registry search integration
- **Commit:** `caa6996`
- **Description:** Expanded the `_decide_skill()` stub in `RouterService` to implement the full SKILL strategy with three paths:
  1. **Direct skill_id lookup** via `get_skill()` — returns `matched` (confidence 1.0) with `skill_lookup_method="get_skill"` metadata, or `zero_match` with `skill_not_found=True` if not found
  2. **Intent-based search** via `classify_intent()` + `search(category=<intent>)` with `search(name_substring=<first word>)` fallback — single match returns `matched` (confidence 0.7), multiple matches return `simple_qa` (confidence 0.5) with `supporting_skills` and `ambiguous_matches` count, zero matches return `zero_match`
  3. **No registry configured** — returns `zero_match` with `registry_not_configured=True`
  - Added `_search_by_message()` helper for de-duplicated intent + substring search
  - Added `supporting_skills` override parameter to `_build_decision()`
  - Created `test_skill_strategy.py` with 8 test cases

### Task 02 — Inject RouterPort into mapper.py with None default and exception fallback
- **Commit:** `895f53a`
- **Description:** Modified `map_agent_end_context()` in `mapper.py` to accept an optional `router: RouterPort | None = None` keyword-only parameter:
  - Added `TYPE_CHECKING` guard for `RouterPort` import (no runtime dependency on `router-service`)
  - Extracted inline route_decision construction into `_inline_route_decision()` helper (pure refactor — same JSONL shape)
  - Added `_route_decision_to_dict()` helper that converts frozen `RouteDecision` dataclass to dict matching inline JSONL shape (overrides `route_decision_id`, `turn_id`, `created_at` with mapper-computed values; preserves router metadata; handles None `reason` and `matched_rule`)
  - Added router delegation logic: when `router is not None`, calls `router.decide(context)` and converts output; on exception, falls back to inline inference
  - When `router=None` (default), uses inline inference exactly as before (zero regression)
  - Added 5 new test cases to `test_mapper.py`

## Test Results

### Task 01 — Router Service Tests

| Test File | Tests | Pass | Fail |
|-----------|-------|------|------|
| `test_skill_strategy.py` | 8 | 8 | 0 |
| `test_port.py` | 3 | 3 | 0 |
| `test_service.py` | 7 | 7 | 0 |
| `test_strategies.py` | 15 | 15 | 0 |
| **Total** | **33** | **33** | **0** |

**Verification commands run:**
- `PYTHONPATH=packages/router-service/src:packages/platform-contract/src:packages/skill-registry/src python -m unittest discover -s packages/router-service/tests -p "test_skill_strategy.py"` — exit 0
- `PYTHONPATH=packages/router-service/src:packages/platform-contract/src:packages/skill-registry/src python -m unittest discover -s packages/router-service/tests` — exit 0 (all 33 tests)
- `python -m compileall packages/router-service/src` — exit 0

### Task 02 — Hermes Contract Layer Tests

| Test File | Tests | Pass | Fail |
|-----------|-------|------|------|
| `test_mapper.py` (existing) | 5 | 5 | 0 |
| `test_mapper.py` (new router injection) | 5 | 5 | 0 |
| `test_hook.py` | 9 | 9 | 0 |
| `test_writer.py` | 3 | 3 | 0 |
| `test_adapter_bootstrap.py` | 6 | 6 | 0 |
| `test_wecom_validation.py` | 6 | 6 | 0 |
| **Total** | **35** | **35** | **0** |

**Verification commands run:**
- `PYTHONPATH=services/hermes-contract-layer/src:packages/platform-contract/src:packages/contract-test-suite/src:packages/router-service/src:packages/skill-registry/src python -m unittest discover -s services/hermes-contract-layer/tests` — exit 0 (all 35 tests)
- `python -m compileall packages/router-service/src services/hermes-contract-layer/src` — exit 0

## Files Modified

| File | Change |
|------|--------|
| `packages/router-service/src/inkstatute_router_service/service.py` | Expanded `_decide_skill()` with full SKILL strategy; added `_search_by_message()` helper; added `supporting_skills` parameter to `_build_decision()` |

## Files Created

| File | Purpose |
|------|---------|
| `packages/router-service/tests/test_skill_strategy.py` | SKILL strategy unit tests (8 test cases) |

## Files Modified (Task 02)

| File | Change |
|------|--------|
| `services/hermes-contract-layer/src/hermes_contract_layer/mapper.py` | Added `router: RouterPort \| None = None` parameter; added `_inline_route_decision()` and `_route_decision_to_dict()` helpers; added router delegation with exception fallback; added `dataclasses` import and `TYPE_CHECKING` guard |
| `services/hermes-contract-layer/tests/test_mapper.py` | Added `RouterInjectionTests` class with 5 new test cases; added `RouteDecision` import |

## Deviations

1. **None reason handling in `_route_decision_to_dict()`:** The `RouteDecision` dataclass allows `reason: str | None`, but the JSONL schema requires `reason` to be a string. When the router's `RouteDecision.reason` is `None`, the helper substitutes a default string `"Route decision produced by injected router."` to satisfy schema validation. This is a minimal, well-scoped deviation that ensures JSONL shape compatibility without modifying the frozen `RouteDecision` dataclass or the platform-contract schemas.

## Contract Freeze Safety

- No files in `packages/platform-contract/` were modified (SAFETY-06 preserved).
- `mapper.py` uses `TYPE_CHECKING` guard for `RouterPort` import — no runtime dependency on `router-service` when router is not injected.
- The `router=None` default preserves inline inference exactly as before (zero regression on all existing mapper tests).
- All `RouteDecision` objects produced by the SKILL strategy use frozen `RouteMode` values only (`matched`, `simple_qa`, `skipped`, `zero_match`).
- The dependency graph is one-directional: `hermes-contract-layer → router-service → {platform-contract, skill-registry}`.

## EXECUTION COMPLETE
