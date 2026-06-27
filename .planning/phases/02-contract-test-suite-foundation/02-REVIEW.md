---
phase: 02-contract-test-suite-foundation
reviewed: 2026-06-27T17:35:26Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - packages/contract-test-suite/README.md
  - packages/contract-test-suite/fixtures/non_legal_education_task.json
  - packages/contract-test-suite/fixtures/non_legal_finance_tax_task.json
  - packages/contract-test-suite/pyproject.toml
  - packages/contract-test-suite/scripts/run_contract_tests.py
  - packages/contract-test-suite/src/contract_test_suite/__init__.py
  - packages/contract-test-suite/src/contract_test_suite/fixture_replay.py
  - packages/contract-test-suite/src/contract_test_suite/paths.py
  - packages/contract-test-suite/src/contract_test_suite/schema_validation.py
  - packages/contract-test-suite/tests/test_composability.py
  - packages/contract-test-suite/tests/test_fixture_replay.py
  - packages/contract-test-suite/tests/test_schema_validation.py
findings:
  critical: 1
  warning: 0
  info: 0
  total: 1
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-06-27T17:35:26Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Re-reviewed the Phase 2 contract-test-suite implementation after `.planning/phases/02-contract-test-suite-foundation/02-REVIEW-FIX.md`. CR-02 is resolved: unknown keys under fixture `events` are rejected and covered by regression tests. CR-03 is resolved: artifact relationship integrity is checked from `agent_result.artifacts` to `execution_trace.artifacts_written` and in the reverse direction, with regression coverage.

CR-01 is only partially fixed. The suite now rejects obviously invalid timestamp strings such as `not-a-date`, but the `format: date-time` validator is still too permissive and accepts strings that are not JSON Schema `date-time` values.

Verification run:

```text
cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py
Ran 21 tests in 0.013s
OK
```

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: BLOCKER - `date-time` validation accepts non-RFC3339 timestamps

**File:** `packages/contract-test-suite/src/contract_test_suite/schema_validation.py:228`

**Issue:** `_validate_date_time` uses `datetime.fromisoformat(value.replace("Z", "+00:00"))` as the only `format: date-time` check. Python's parser accepts values that JSON Schema `date-time` should reject, including date-only strings (`2026-06-27`), timestamps without a timezone (`2026-06-27T13:00:00`), and timestamps using a space instead of `T` (`2026-06-27 13:00:00`). I verified these values are currently accepted by `validate_event("agent_turn", ...)`. As a result, contract fixtures and replay can still pass with invalid platform event timestamps.

**Fix:**
```python
import re
from datetime import datetime

_RFC3339_DATE_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T"
    r"\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"(?:Z|[+-]\d{2}:\d{2})$"
)


def _validate_date_time(value: Any, path: tuple[str, ...]) -> None:
    if not isinstance(value, str):
        return
    if not _RFC3339_DATE_TIME.fullmatch(value):
        raise ContractValidationError(f"{_path(path)}: invalid date-time format")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractValidationError(f"{_path(path)}: invalid date-time format") from exc
```

Add regression cases for `2026-06-27`, `2026-06-27T13:00:00`, and `2026-06-27 13:00:00Z` in `test_invalid_date_time_format_errors_cover_contract_timestamps`, alongside the existing `not-a-date` case.

---

_Reviewed: 2026-06-27T17:35:26Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
