---
phase: 58-v1-8-pre-implementation-safety
reviewed: 2026-07-07T16:10:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - .planning/phases/08-lawyer-trial-acceptance/08-TRIAL-EVIDENCE-TEMPLATE.json
  - packages/channels/qqbot/tests/test_v1_8_safety_baseline.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 58: Code Review Report

**Reviewed:** 2026-07-07T16:10:00Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Phase 58 is a safety-verification phase: it restores a deleted data file (`08-TRIAL-EVIDENCE-TEMPLATE.json`) from git history and adds a consolidated v1.8 safety-baseline test (`test_v1_8_safety_baseline.py`). No user-facing functionality, auth, crypto, or runtime behavior was changed.

Both files were read in full and cross-referenced against the live `platform_contract.enums`, `platform_runtime.protocols`, `platform_runtime.feature_flags`, and the qqbot `pyproject.toml`. The restored JSON is valid, contains only placeholder references (no secrets, no real legal payloads), and correctly carries `readiness_gates.local_v2_gates_passed = false`. The new test file was executed locally — all 6 tests pass on Python 3.14.

No Critical issues were found. Two Warnings concern robustness of the test assertions themselves (not product bugs): the `dir()`-based Protocol method count depends on an undocumented invariant of `typing.Protocol`, and the `dependencies = []` check uses a raw substring match instead of TOML parsing. One Info notes a redundant assertion.

## Warnings

### WR-01: `dir()`-based Protocol method count relies on undocumented `typing.Protocol` surface

**File:** `packages/channels/qqbot/tests/test_v1_8_safety_baseline.py:36-41`
**Issue:** The tests `test_channel_adapter_has_exactly_6_methods` and `test_backend_adapter_has_exactly_9_methods` compute method counts via `[m for m in dir(ChannelAdapter) if not m.startswith("_")]`. This works only because CPython's `typing.Protocol` happens to expose no non-underscore-prefixed attributes. That invariant is an implementation detail, not a documented contract — a future Python release adding a public attribute to `Protocol` (or a `runtime_checkable` decorator change) would flip the count to 7/10 and produce a confusing `AssertionError` that looks like a contract regression rather than a test-harness drift. The module docstring acknowledges the tests are "complementary, not duplicative" to the SHA-256/AST baselines, which is good, but the failure mode is still non-obvious.
**Fix:** Pin the introspection to the protocol's own `__dict__` (or `__protocol_attrs__`) so inherited `Protocol`/`object` members can never perturb the count:

```python
def _protocol_methods(cls: type) -> list[str]:
    return sorted(m for m in cls.__dict__ if not m.startswith("_"))

def test_channel_adapter_has_exactly_6_methods(self) -> None:
    self.assertEqual(len(_protocol_methods(ChannelAdapter)), 6)

def test_backend_adapter_has_exactly_9_methods(self) -> None:
    self.assertEqual(len(_protocol_methods(BackendAdapter)), 9)
```

### WR-02: `dependencies = []` check uses raw substring match instead of TOML parsing

**File:** `packages/channels/qqbot/tests/test_v1_8_safety_baseline.py:58-61`
**Issue:** `test_qqbot_pyproject_has_empty_dependencies` reads `pyproject.toml` as text and asserts `"dependencies = []"` appears anywhere in the file. This verifies the literal string is present but not that it is the `[project]` table's dependency list. A future edit that moves the real dependencies into `[project]` and leaves a stale `dependencies = []` line in a comment or in an unrelated `[tool.*]` table would still pass the test while violating the SC-5 invariant (the qqbot package must have zero runtime dependencies). The semantic invariant is weaker than the assertion implies.
**Fix:** Parse the TOML and assert on the structured field. Python 3.11+ (the project's minimum) ships `tomllib` in the stdlib:

```python
import tomllib

def test_qqbot_pyproject_has_empty_dependencies(self) -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)
    self.assertEqual(data["project"]["dependencies"], [])
```

## Info

### IN-01: Redundant length assertion in `test_feedback_source_has_exactly_4_values`

**File:** `packages/channels/qqbot/tests/test_v1_8_safety_baseline.py:49-52`
**Issue:** `len(values) == 4` is asserted immediately before `set(values) == expected` where `expected` has exactly 4 elements. The set-equality check already implies the count (given unique enum values), making the length assertion redundant. Not a bug — the redundancy is harmless and arguably documents intent — but it is dead logic.
**Fix:** Drop the length assertion, or keep only the length check and replace the set comparison with a sorted-list comparison if order independence is not required.

---

_Reviewed: 2026-07-07T16:10:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
