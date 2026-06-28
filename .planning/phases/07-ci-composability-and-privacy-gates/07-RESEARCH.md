# Phase 7: CI, Composability, and Privacy Gates - Research

**Researched:** 2026-06-28
**Status:** Complete
**Mode:** Inline GSD research, no subagent spawn

## Research Question

What does Phase 7 need to know before planning repeatable V2 gates for CI, composability, coverage, privacy, and thin-layer boundaries?

## Findings

### Existing Gate Surface

- `packages/contract-test-suite/src/contract_test_suite/schema_validation.py` already validates the five platform event schemas and rejects forbidden top-level legal or sensitive fields such as `jurisdiction`, `phone`, `bank_account`, and `raw_payload`.
- `packages/contract-test-suite/src/contract_test_suite/fixture_replay.py` already replays full five-event JSON fixture bundles and computes relationship breakage with a configurable max breakage rate. Its default threshold is the PRD tolerance of 5%.
- `packages/contract-test-suite/src/contract_test_suite/event_stream_replay.py` already replays JSONL event streams, checks event ordering, required core event presence, turn/route/trace/result relationships, and also defaults integrity assertions to 5%.
- `packages/contract-test-suite/tests/test_composability.py` already proves non-legal finance/tax, engineering, and education fixtures validate without legal-only top-level fields.
- Service suites are dependency-light stdlib `unittest` suites with explicit `PYTHONPATH` setup. Existing package metadata across packages and services uses `requires-python >=3.11` and `dependencies = []`.

### Missing Phase 7 Capabilities

- There is no repo-root command that runs all package/service suites and contract gates as one local CI-equivalent command.
- There is no `.github` workflow. Phase 7 can introduce the first CI wrapper around the local command.
- Coverage evidence exists implicitly in JSONL streams but no helper reports paired `agent_turn` and `agent_result` coverage or distinguishes fixture evidence from missing live/runtime evidence.
- Privacy checks are duplicated in focused tests but there is no reusable repository scan for committed fixtures, docs, bundle manifests, runtime files, plaintext secret patterns, exact `raw_payload` data fields, or PII-like full values.
- Thin-layer checks are currently mostly documented. There is no automated import boundary check proving `platform-contract` does not depend on Hermes, WeCom, feedback, read-view, or service modules.

### Implementation Constraints

- Do not add tox, nox, pytest, or runtime dependencies. Use Python stdlib, `unittest`, `json`, `pathlib`, `subprocess`, `re`, and dataclasses.
- Do not rebuild Hermes core, session storage, router, skill registry, MCP registry, model gateway, or live WeCom behavior.
- CI must not upload raw logs, callback bodies, databases, customer documents, media, or raw legal payloads.
- Synthetic fixtures can prove calculations and safety behavior, but they must not be described as live lawyer-trial or real-task acceptance evidence.
- Legal-specific fixture details must stay under `industry_context`, metadata, profile extensions, or references. Platform schemas must remain industry-neutral.

## Proposed Gate Architecture

### Local Runner

Create `scripts/run_v2_gates.py` as the single repo-root command. It should:

- run all package/service unit suites with explicit `PYTHONPATH`;
- run the package-local contract runner or the contract-suite unittest discovery;
- run coverage, privacy, composability, and thin-layer checks;
- run `compileall` for package/service source directories;
- emit concise gate names and non-zero exit codes on failure;
- optionally emit a sanitized JSON summary, with no raw record data.

### Coverage Reporter

Add `contract_test_suite.coverage_report` to compute:

- stream count and record count;
- unique `turn_id` count from `agent_turn`;
- turns with paired `agent_result`;
- paired coverage rate;
- relationship check count, broken relationship count, and breakage rate from existing replay helpers;
- evidence kind: fixture/sanitized input/runtime input;
- runtime input missing as an explicit non-live status, not a pass claim.

### Privacy Scanner

Add `contract_test_suite.privacy_scan` with separate source and data scanning rules:

- strict data scan for `packages/*/fixtures`, service bundle manifests, docs/runbooks, and stable generated summaries;
- allow source files and tests to mention guard strings like `"raw_payload"` while still failing obvious committed secrets or runtime artifacts;
- preserve `raw_payload_ref`, `fixture://`, and other reference-first strings;
- fail on exact JSON/YAML key `raw_payload` in data artifacts, common plaintext secret patterns, complete phone/ID/bank/address-like values, runtime DB/log/media names, and callback body markers.

### Thin-Layer Checks

Add `contract_test_suite.boundary_checks` to prove:

- `packages/platform-contract/src` imports no Hermes, WeCom, feedback-service, conversation-read-view, or `services.*` modules;
- platform schema top-level required/properties stay free of forbidden legal-only fields;
- adapter manifests/output policy/hooks/read APIs/feedback normalization remain in their owning packages and services, not platform core or Hermes core paths;
- lawfirm bundle manifests remain sanitized and exclude runtime DBs, logs, customer documents, secrets, and raw legal payload paths.

## Validation Architecture

| Gate | Primary Proof | Command |
|------|---------------|---------|
| Unit suites | All package/service `unittest` discovery commands pass | `python scripts/run_v2_gates.py` |
| Coverage | Synthetic fixture/stream reporter has paired turn/result calculations and 5% breakage gate | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_coverage_report.py` |
| Privacy | Fixture/data scans fail on raw payloads/secrets and preserve references | `PYTHONPATH=packages/contract-test-suite/src python -m unittest packages/contract-test-suite/tests/test_privacy_gates.py` |
| Thin layer | Import/schema/bundle boundary tests pass | `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_thin_layer_boundaries.py` |
| CI wrapper | Workflow calls only local runner and uploads no unsafe artifacts | `python scripts/run_v2_gates.py` plus text tests if added |

## Risks

- A naive privacy scanner could false-positive source code guard strings. Use explicit data roots and a source allowlist mode.
- A coverage helper could make synthetic data sound like live acceptance. Report fixture and missing runtime inputs separately.
- A root runner can become hard to debug if it hides command output. Print each gate command and keep stdout/stderr visible for failing commands.
- CI YAML can drift from the local runner. Keep GitHub Actions thin and make the local runner authoritative.

## Research Complete

Phase 7 can be planned as three sequential slices:

1. Local runner and coverage reporter.
2. Privacy, composability, and thin-layer gate helpers.
3. GitHub Actions wrapper and documentation.

