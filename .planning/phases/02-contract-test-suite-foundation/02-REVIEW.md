---
phase: 02-contract-test-suite-foundation
reviewed: 2026-06-27T17:26:18Z
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
  critical: 3
  warning: 0
  info: 0
  total: 3
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-06-27T17:26:18Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Reviewed the Phase 2 contract-test-suite implementation, fixtures, tests, runner, and README. Existing unittest discovery passes, but the harness currently accepts invalid contract data in cases Phase 2 is supposed to catch: invalid schema date-time values, unvalidated extra event payloads, and incomplete artifact relationship continuity.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: BLOCKER - `format: date-time` constraints are never enforced

**File:** `packages/contract-test-suite/src/contract_test_suite/schema_validation.py:118`

**Issue:** `_validate_schema` enforces `type`, `enum`, and numeric range, but ignores JSON Schema `format`. The platform schemas define required event timestamps through `common.schema.json#/$defs/datetime` using `format: date-time`, so a fixture with `received_at: "not-a-date"` or invalid `created_at`/`occurred_at` values still passes `validate_event_bundle`. That makes the contract suite report schema-valid events that are not valid platform contract events.

**Fix:**
```python
from datetime import datetime


def _validate_schema(...):
    ...
    if resolved.get("format") == "date-time":
        _validate_date_time(value, path)


def _validate_date_time(value: Any, path: tuple[str, ...]) -> None:
    if not isinstance(value, str):
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractValidationError(f"{_path(path)}: invalid date-time format") from exc
```
Add negative tests that mutate `agent_turn.received_at`, `route_decision.created_at`, `execution_trace.occurred_at`, and `feedback_event.created_at`.

### CR-02: BLOCKER - Unknown event objects inside a fixture bundle are silently accepted

**File:** `packages/contract-test-suite/src/contract_test_suite/schema_validation.py:98`

**Issue:** `validate_event_bundle` only checks that the five expected event keys exist, then validates those five keys. It never rejects extra keys under `events`. A bundle can include an additional unvalidated event such as `raw_legal_payload` containing sensitive full text and still pass schema validation and replay. This violates the five-event contract boundary and undermines the privacy rule that contract logs should keep raw payloads by reference.

**Fix:**
```python
def validate_event_bundle(
    fixture: Mapping[str, Any],
    schemas: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    loaded_schemas = schemas if schemas is not None else load_schemas()
    fixture_id = _fixture_id(fixture)
    events = fixture.get("events")
    if not isinstance(events, dict):
        raise ContractValidationError(f"{fixture_id}: events must be object")

    extra_events = sorted(set(events) - set(EVENT_SCHEMA_BY_KEY))
    if extra_events:
        raise ContractValidationError(f"{fixture_id}.{extra_events[0]}: unknown event key")

    for event_key in EVENT_SCHEMA_BY_KEY:
        if event_key not in events:
            raise ContractValidationError(f"{fixture_id}.{event_key}: missing event")
        validate_event(event_key, events[event_key], loaded_schemas, fixture_id=fixture_id)
```
Add a regression test that inserts an extra event containing a forbidden raw payload field and expects `ContractValidationError`.

### CR-03: BLOCKER - Artifact relationship integrity only checks one direction

**File:** `packages/contract-test-suite/src/contract_test_suite/fixture_replay.py:190`

**Issue:** The replay relationship check verifies each `agent_result.artifacts[*].artifact_id` appears in `execution_trace.artifacts_written`, but it does not verify the reverse direction. If `execution_trace.artifacts_written` includes an artifact id that is never present in `agent_result.artifacts`, replay still returns zero broken relationships. This creates a false-positive relationship report and loses trace-to-result continuity for produced artifacts.

**Fix:**
```python
artifacts_written = set(execution_trace.get("artifacts_written", []))
result_artifact_ids = {
    artifact.get("artifact_id")
    for artifact in agent_result.get("artifacts", [])
    if isinstance(artifact, dict)
}

for artifact_id in result_artifact_ids:
    checks.append(("artifact_id", "agent_result.artifacts.artifact_id", artifact_id, artifacts_written))

for artifact_id in artifacts_written:
    checks.append(("artifact_written", "execution_trace.artifacts_written", artifact_id, result_artifact_ids))
```
Add a regression test that appends an unreferenced id to `execution_trace.artifacts_written` and expects a relationship issue.

---

_Reviewed: 2026-06-27T17:26:18Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
