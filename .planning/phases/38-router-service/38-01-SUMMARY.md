# Plan 38-01 Summary — Router-Service Package, RouterPort Protocol, RouterService, and RULE Strategy

## Plan ID
- **Phase:** 38 (Router Service)
- **Plan:** 01
- **Title:** Router-service package structure, RouterPort Protocol, RouterService, and RULE strategy
- **Wave:** 1
- **Requirements:** ROUTER-01, ROUTER-02

## Tasks Completed

### Task 01 — Package structure, RouterPort Protocol, RouterStrategy enum, and RouterService with RULE strategy
- **Commit:** `d0405e9`
- **Description:** Created the `packages/router-service/` library package with `pyproject.toml`, `README.md`, `src/inkstatute_router_service/` module, and `tests/` directory. Implemented:
  - `RouterPort` Protocol (`port.py`) with a single `decide(context) -> RouteDecision` method
  - `RouterStrategy` StrEnum (`strategies.py`) with `RULE = "rule"` and `SKILL = "skill"` — separate from frozen `RouteMode`
  - `classify_intent()` function (`classifier.py`) with `INTENT_KEYWORDS` for 4 intent categories
  - `RouterService` class (`service.py`) implementing `RouterPort` via structural subtyping, with RULE strategy (keyword/regex intent classification) and SKILL strategy stub
  - `__init__.py` re-exporting `RouterPort`, `RouterService`, `RouterStrategy`, `classify_intent`
  - `test_port.py` (3 tests) — Protocol conformance verification
  - `test_service.py` (7 tests) — RULE strategy decide() behavior tests

### Task 02 — RouterStrategy and classifier tests proving RULE strategy RouteMode mapping
- **Commit:** `21ef323`
- **Description:** Created `test_strategies.py` with 15 test cases covering:
  - RouterStrategy enum value verification (5 tests)
  - classify_intent function tests (8 tests) including case-insensitive English matching
  - RULE strategy RouteMode mapping integration tests (2 tests) verifying strategy maps to frozen RouteMode values, not strategy names
- **Deviation:** The classifier was updated to use word boundaries (`\b`) for ASCII/English keywords to prevent false substring matches (e.g., "is" matching inside "this"). Chinese keywords continue to use substring matching. This deviation was necessary to satisfy the `test_classify_intent_case_insensitive` acceptance criterion.

## Test Results

| Test File | Tests | Pass | Fail |
|-----------|-------|------|------|
| `test_port.py` | 3 | 3 | 0 |
| `test_service.py` | 7 | 7 | 0 |
| `test_strategies.py` | 15 | 15 | 0 |
| **Total** | **25** | **25** | **0** |

**Verification commands run:**
- `PYTHONPATH=packages/router-service/src:packages/platform-contract/src:packages/skill-registry/src python -m unittest discover -s packages/router-service/tests -p "test_port.py"` — exit 0
- `PYTHONPATH=packages/router-service/src:packages/platform-contract/src:packages/skill-registry/src python -m unittest discover -s packages/router-service/tests -p "test_service.py"` — exit 0
- `PYTHONPATH=packages/router-service/src:packages/platform-contract/src:packages/skill-registry/src python -m unittest discover -s packages/router-service/tests -p "test_strategies.py"` — exit 0
- `PYTHONPATH=packages/router-service/src:packages/platform-contract/src:packages/skill-registry/src python -m unittest discover -s packages/router-service/tests` — exit 0 (all 25 tests)
- `python -m compileall packages/router-service/src` — exit 0

## Files Created

| File | Purpose |
|------|---------|
| `packages/router-service/pyproject.toml` | Package definition with `[tool.inkstatute]` section |
| `packages/router-service/README.md` | Package documentation |
| `packages/router-service/src/inkstatute_router_service/__init__.py` | Package init with re-exports |
| `packages/router-service/src/inkstatute_router_service/port.py` | `RouterPort` Protocol |
| `packages/router-service/src/inkstatute_router_service/strategies.py` | `RouterStrategy` StrEnum (RULE, SKILL) |
| `packages/router-service/src/inkstatute_router_service/classifier.py` | `classify_intent()`, `INTENT_KEYWORDS` |
| `packages/router-service/src/inkstatute_router_service/service.py` | `RouterService` class, `ROUTER_SERVICE_VERSION` |
| `packages/router-service/tests/test_port.py` | Protocol conformance tests (3 cases) |
| `packages/router-service/tests/test_service.py` | RouterService.decide() tests (7 cases) |
| `packages/router-service/tests/test_strategies.py` | RouterStrategy + classifier + mapping tests (15 cases) |

## Deviations

1. **Classifier word boundary for English keywords:** The plan specified `re.search(re.escape(keyword), message, re.IGNORECASE)` for all keywords. However, the acceptance criterion `test_classify_intent_case_insensitive` expects `classify_intent("Please REVIEW this")` to return `"review"`, but the keyword `"is"` (in `factual_qa`) would match as a substring inside `"this"`. The classifier was updated to use `\b` word boundaries for ASCII keywords while preserving substring matching for Chinese keywords. This is a minimal, well-scoped deviation that makes the classifier more accurate for English text.

## Contract Freeze Safety

- No files in `packages/platform-contract/` were modified (SAFETY-06 preserved).
- `RouterStrategy` (RULE, SKILL) is a new enum in `router-service`, NOT added to the frozen `RouteMode` enum.
- All `RouteDecision` objects produced by `RouterService.decide()` use frozen `RouteMode` values only (`matched`, `simple_qa`, `skipped`, `zero_match`).
- The strategy is recorded in `metadata["router_strategy"]`, not in `mode`.

## EXECUTION COMPLETE
