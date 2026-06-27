# InkStatute Contract Test Suite

This package provides the Phase 2 local contract harness for InkStatute V2. It consumes the sibling `platform-contract` schemas and fixtures, validates contract event shape, replays fixture bundles, checks relationship continuity, and proves local synthetic composability across non-legal finance/tax, engineering, and education examples.

## Local Command

Run the suite from the repository with:

```bash
cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py
```

The runner is package-local and stdlib-only. It inserts `src` and `../platform-contract/src` into `sys.path`, performs `unittest` discovery against `packages/contract-test-suite/tests`, and exits non-zero on failure.

## Coverage Boundary

This suite validates:

- schema validation for the five platform contract event types
- Phase 1 platform-contract fixtures
- fixture replay and relationship integrity across turn, route, trace, result, artifacts, and feedback
- synthetic composability for non-legal finance/tax, engineering, and education tasks
- rejection of legal-only or sensitive top-level fields in platform events

This package does not implement Hermes hooks, real Hermes adapters, WeCom loop validation, feedback-service processing, conversation read-view APIs, or `.github` CI workflows.

Phase 7 owns CI enforcement for this command, including any `.github` workflow wiring and broader composability/privacy gates. Phase 3 and Phase 4 own real Hermes output replay and hook/adaptor work.
