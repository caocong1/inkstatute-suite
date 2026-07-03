# Phase 33: V2 Requirement Audit & Traceability Infrastructure - Research

**Researched:** 2026-07-03
**Status:** Complete

## Research Questions

### RQ-1: What proven audit script pattern exists in the repo?

**Finding:** `scripts/check_v1_3_verification_artifacts.py` (171 lines) is the canonical pattern. It uses:
- `argparse` with `--mode` sub-commands (artifacts, traceability, audit)
- `pathlib.Path` for all path resolution (`REPO_ROOT = Path(__file__).resolve().parents[1]`)
- `re.findall` for parsing traceability tables from markdown
- Dataclass-free, function-based checks returning `list[str]` failures
- Exit codes: 0 pass, 1 artifact/traceability failure, 2 audit-statement failure
- `_read(path)` helper for UTF-8 file reading

This pattern is stdlib-only and deterministic. The Phase 33 audit script should follow the same structure but extend it with three-level verification and JSON output.

### RQ-2: How does the V2 gate runner work and how to add a 9th gate?

**Finding:** `scripts/run_v2_gates.py` (136 lines) defines a frozen `Gate` dataclass with `name`, `command` (tuple), and `pythonpath` (tuple). The `_gates()` function returns a tuple of 8 `Gate` entries. Adding a 9th gate requires:
1. Add one new `Gate(...)` entry to the tuple returned by `_gates()`
2. The gate command runs `scripts/audit_v2_requirements.py --check-gaps`
3. PYTHONPATH is not needed (the audit script is stdlib-only and resolves paths itself)
4. The gate name should be `v2-acceptance-traceability`
5. The `compileall` gate's path list should include `scripts/audit_v2_requirements.py`

The gate runner already handles `--json-summary` and `--list` modes. No changes to the runner logic are needed — only the gate tuple.

### RQ-3: What evidence producers exist in contract-test-suite?

**Finding:** `packages/contract-test-suite/src/contract_test_suite/` contains 7 evidence producers:

| Module | Purpose | Key API |
|--------|---------|---------|
| `schema_validation.py` | JSON Schema subset validation | `validate_event()`, `validate_fixture()`, `EVENT_SCHEMA_BY_KEY` |
| `fixture_replay.py` | Golden fixture replay + relationship checks | `replay_fixtures()`, `load_fixture_paths()` |
| `event_stream_replay.py` | JSONL event stream replay | `load_event_stream()`, `replay_event_streams()` |
| `coverage_report.py` | Coverage summaries | `CoverageReport`, `CoverageSourceReport` |
| `boundary_checks.py` | Thin-layer + composability boundary | `BoundaryIssue`, scan functions |
| `privacy_scan.py` | Secret/PII scanning | `PrivacyIssue`, scan functions |
| `trial_acceptance.py` | Lawyer trial threshold checks | Trial readiness functions |

The audit script should **invoke** these producers (import and call) rather than re-implement checks. This ensures the audit uses the same evidence the gates use.

### RQ-4: What are the 10 unchecked V2 Active requirements?

**Finding:** `.planning/PROJECT.md` lines 43-52 contain 10 unchecked `[ ]` Active requirements:

1. Build InkStatute-owned WeCom service (receive/send, ACK, normalization, delivery, feedback callbacks, idempotency, retry, output policy)
2. Define and implement agent backend adapter contract and runtime selector (Hermes first, Codex/provider-model future)
3. Build reproducible Hermes agent adapter bootstrap path (sanitized lawfirm profile, version matrix, secrets/env, health checks)
4. Add assistant output boundary (block/rewrite Hermes gateway/update/command/meta notices)
5. Preserve and validate WeCom task-to-agent-to-reply-to-card-to-feedback loop
6. Normalize Hermes feedback into FeedbackEvent (dedupe, classification, human-reviewed skill candidates)
7. Build read-only conversation/task/feedback APIs from contract logs
8. Enforce observability, replay, privacy, and legal safety baselines
9. Enforce composability and industry-neutral contract behavior in CI
10. Complete the five-workday lawyer trial acceptance criteria

Requirement #10 is a human gate (Phase 8) — the audit should classify it as `human_gate`, not `gap`.

### RQ-5: What three-level verification prevents the MEM-07/MEM-16 false-positive?

**Finding:** The v1.4 milestone audit (`.planning/milestones/v1.4-MILESTONE-AUDIT.md`) documented the false-positive pattern:
- **MEM-07**: `HindsightMemory` class exists (library surface) and schema exists, but `ingress_runtime.py` never passes `memory` to `WeComSessionRuntime` (production wiring missing). Gate tests passed because tests inject the memory directly.
- **MEM-16**: `MemoryOperationEvent` and `MemoryObserver` are defined (library surface), `RetryableMemory` emits events, but no production observer is wired. Events only captured in tests.

The three-level verification pattern prevents this:
1. **Level 1 — Schema definition**: Does the JSON Schema / dataclass / interface exist? (e.g., `feedback_event.schema.json` exists)
2. **Level 2 — Library surface**: Does the implementation module exist with the right functions/classes? (e.g., `feedback_service/wecom_normalizer.py` has `normalize_feedback()`)
3. **Level 3 — Production wiring**: Is the module actually imported and called in the production entrypoint? (e.g., `wecom_service/ingress_runtime.py` imports and calls the normalizer)

A requirement is `satisfied` only if all three levels pass. `partial` if levels 1-2 pass but level 3 fails. `gap` if level 1 or 2 fails. `human_gate` if the requirement inherently requires live human evidence (lawyer trial, live WeCom UAT).

### RQ-6: What PRD §10 acceptance criteria exist?

**Finding:** `docs/requirements/V2-PRD.md` §10 defines four acceptance sections:

- **§10.1 仓库与文档验收**: README, PRD coverage, .gitignore, git repo
- **§10.2 契约 CI 验收**: contract-test-suite passing, WeCom contract test coverage, schema validation, fixture replay, relationship integrity, coverage ≥95%, output boundary fixtures
- **§10.3 可组合性合成任务验收**: 8 synthetic task types (simple QA, contract review, legal retrieval, route mismatch, WeCom feedback, long task failure, non-legal tasks), all schema-valid + relationship-complete
- **§10.4 律师试运行验收**: 15 real tasks, 5 workdays, success rates, feedback rates, route_mismatch limits, output boundary, bootstrap evidence

The criterion-to-test mapping must map each §10.1-10.4 bullet to specific test functions and fixture files.

### RQ-7: What fixtures exist for evidence bundles?

**Finding:** `packages/contract-test-suite/fixtures/` contains 30+ fixture files covering:
- Phase 3-5 WeCom contract streams (`.jsonl`)
- Phase 10-25 runtime/memory fixtures (`.json`)
- Phase 55 non-Hermes adapter + output policy cases
- Non-legal domain fixtures (finance, engineering, education)
- Platform foundation fixtures

`packages/platform-contract/fixtures/` contains 5 additional fixtures including legal/non-legal runs.

### RQ-8: What test modules exist per service?

**Finding:**

| Service | Test modules | Count |
|---------|-------------|-------|
| wecom-service | test_active_task_router, test_agent_backend, test_delivery_guard, test_ingress_memory_runtime, test_ingress_memory_wiring, test_ingress_runtime, test_normalization, test_output_policy, test_protocol | 9 |
| hermes-contract-layer | test_adapter_bootstrap, test_hook, test_mapper, test_wecom_validation, test_writer | 5 |
| feedback-service | test_feedback_queue, test_memory_wiring, test_wecom_normalizer | 3 |
| conversation-read-view | test_api, test_read_model | 2 |
| contract-test-suite | 21 test modules | 21 |

Total: 40 test modules across services + contract-test-suite.

### RQ-9: Is JSON or YAML better for the traceability manifest?

**Finding:** JSON is the correct choice. `json` is Python stdlib (always available). PyYAML is NOT installed in the repo (confirmed: no `yaml` import anywhere in scripts/). The existing `run_v2_gates.py` already uses `json.dumps` for `--json-summary`. The traceability sidecar should be `acceptance/v2-traceability.json`.

### RQ-10: What is the existing `acceptance/` directory state?

**Finding:** The `acceptance/` directory does not exist yet. It needs to be created. The traceability sidecar path `acceptance/v2-traceability.json` is specified in AUDIT-05. The directory should also hold per-requirement evidence bundles if we choose to write them as separate files (though the plan recommends embedding bundles in the single JSON sidecar for determinism).

## Architecture Decision: Audit Script Design

The audit script `scripts/audit_v2_requirements.py` will be a single stdlib-only Python file following the `check_v1_3_verification_artifacts.py` pattern, extended with:

1. **Requirement registry**: A dataclass `RequirementSpec` with `req_id`, `description`, `evidence_probes` (list of three-level verification probes), `prd_section`, `human_gate` flag.
2. **Three-level verification**: Each probe checks schema → library surface → production wiring using `pathlib`, `ast`, and `re`.
3. **Evidence collection**: For each requirement, collect file paths, test modules, gate names, schema IDs, and fixture paths by scanning the repo structure.
4. **Classification engine**: `satisfied` (all 3 levels + evidence), `partial` (levels 1-2 only), `gap` (level 1 or 2 missing), `human_gate` (inherently human).
5. **PRD §10 mapping**: A static mapping from §10.1-10.4 criteria to test functions and fixtures.
6. **JSON output**: `--json` flag writes `acceptance/v2-traceability.json`; default prints human-readable matrix.
7. **Gap-check mode**: `--check-gaps` exits non-zero if any requirement is `gap` or evidence is missing (used by the 9th gate).

The script will NOT re-run tests or gates. It reads the codebase structure and existing evidence. Running gates is the job of `run_v2_gates.py`. The audit script verifies that evidence *exists and is wired*, not that it *passes* (the gates already prove passing).
