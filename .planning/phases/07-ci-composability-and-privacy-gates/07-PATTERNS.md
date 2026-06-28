# Phase 7: CI, Composability, and Privacy Gates - Patterns

**Mapped:** 2026-06-28
**Status:** Complete

## Existing Patterns To Reuse

### Stdlib Test Runner

Closest analog: `packages/contract-test-suite/scripts/run_contract_tests.py`

- uses a repo/package-root calculation with `Path(__file__).resolve()`;
- inserts package `src` roots into `sys.path`;
- uses `unittest.defaultTestLoader.discover`;
- returns `0` only when the suite succeeds.

Phase 7 should extend this pattern at repo root with `subprocess.run` commands rather than introducing tox, nox, pytest, or shell-only orchestration.

### Relationship Integrity

Closest analogs:

- `contract_test_suite.fixture_replay.ReplayReport`
- `contract_test_suite.event_stream_replay.EventStreamReport`
- `assert_relationship_integrity(..., max_breakage_rate=0.05)`
- `assert_event_stream_integrity(..., max_breakage_rate=0.05)`

Phase 7 coverage helpers should call these existing APIs and should not build another schema or relationship validator.

### Composability

Closest analog: `packages/contract-test-suite/tests/test_composability.py`

- loads non-legal fixtures from platform and contract-suite fixture roots;
- validates each fixture with `validate_event_bundle`;
- checks relationship integrity with `assert_relationship_integrity`;
- recursively verifies required fields and top-level schema properties do not include forbidden lawfirm-only fields.

Phase 7 can either expand this test or add helper modules that reuse its same forbidden-field source of truth.

### Privacy Recursion

Closest analogs:

- `conversation_read_view.privacy.find_forbidden_raw_payload_path`
- `feedback_service.queue._find_exact_key`
- `wecom_service.protocol._find_forbidden_raw_payload_key`
- `hermes_contract_layer.wecom_validation._privacy_issues`

The established rule is exact-key matching: `raw_payload` is forbidden, `raw_payload_ref` is valid. Phase 7 should centralize repository scan behavior in `contract_test_suite.privacy_scan` without changing service-local helpers.

### Source Layout

All current packages and services use:

- Python `src/` layout;
- `requires-python = ">=3.11"`;
- `dependencies = []`;
- stdlib `unittest`;
- explicit `PYTHONPATH` in verification commands.

The root gate runner should keep that convention.

## Planned File Roles

| File | Role | Pattern Source |
|------|------|----------------|
| `scripts/run_v2_gates.py` | repo-root local CI-equivalent gate runner | `packages/contract-test-suite/scripts/run_contract_tests.py` |
| `packages/contract-test-suite/src/contract_test_suite/coverage_report.py` | paired turn/result coverage and breakage summaries | `event_stream_replay.py`, `fixture_replay.py` |
| `packages/contract-test-suite/src/contract_test_suite/privacy_scan.py` | committed data/source privacy scan helpers | service privacy recursion helpers |
| `packages/contract-test-suite/src/contract_test_suite/boundary_checks.py` | platform import/schema/thin-layer checks | `test_composability.py`, schema validation |
| `packages/contract-test-suite/tests/test_coverage_report.py` | unit tests for coverage and runtime-input semantics | existing contract-suite tests |
| `packages/contract-test-suite/tests/test_privacy_gates.py` | unit tests for privacy scanner false positives and failures | Phase 5/6 privacy tests |
| `packages/contract-test-suite/tests/test_thin_layer_boundaries.py` | unit tests for import and boundary checks | `test_composability.py` |
| `.github/workflows/v2-contract-gates.yml` | GitHub Actions wrapper around the local runner | no existing workflow |

## Constraints For Executors

- Read `AGENTS.md`, Phase 7 context, this patterns file, and the relevant existing helper before editing.
- Keep modules dependency-free.
- Prefer small dataclasses or plain dictionaries for report objects.
- Return sanitized summaries only. Do not include raw event objects in report JSON.
- Do not update Hermes core or create a runtime service/database/queue.

