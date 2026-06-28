# Phase 7: CI, Composability, and Privacy Gates - Context

**Gathered:** 2026-06-28T07:58:00Z
**Status:** Ready for planning
**Source:** `$gsd-progress --next --auto` / `$gsd-discuss-phase 7 --auto`

<domain>
## Phase Boundary

Phase 7 turns the V2 contract, service, adapter, read-view, feedback, composability, and privacy checks into repeatable gates. It should make failures visible locally and in CI before lawyer trial acceptance: schema drift, missing required fields, broken relationships, coverage misses, legal-only top-level schema leaks, unsafe raw payload storage, plaintext secret patterns, Hermes/platform coupling, and accidental expansion beyond the thin contract/adaptor layer.

This phase may add CI workflow files, root or package-local gate runner scripts, contract-test-suite coverage/privacy helpers, composability tests, import-boundary checks, and documentation for running gates. It must not rebuild Hermes core, create a new service/database/queue, commit runtime logs or customer payloads, implement the lawyer trial, or claim live WeCom acceptance from synthetic fixtures.

</domain>

<decisions>
## Implementation Decisions

### CI Entry Point and Local Runner

- **D-01:** Add a single local Phase 7 gate command that developers and CI can run from the repo root. Prefer a stdlib Python script or thin shell/Python wrapper over tox/nox/pytest/new dependencies.
- **D-02:** Add `.github` CI only as a wrapper around local commands. The local command remains authoritative so failures are reproducible without GitHub Actions.
- **D-03:** CI should use Python versions compatible with package metadata (`requires-python >=3.11`) and install no runtime dependencies unless a plan proves a package needs one. Existing packages are dependency-free.
- **D-04:** Gate commands must include all existing package/service unit suites: platform-contract, contract-test-suite, hermes-contract-layer, wecom-service, feedback-service, and conversation-read-view.

### Contract Relationship and Coverage Gates

- **D-05:** Reuse `contract_test_suite.schema_validation`, `fixture_replay`, and `event_stream_replay`; do not create another schema validator.
- **D-06:** Relationship gates must fail when breakage exceeds the PRD tolerance of 5%. Existing fixture tests can keep zero-breakage expectations where they already do.
- **D-07:** Coverage reporting should calculate paired `AgentTurn`/`AgentResult` coverage and relationship breakage for provided contract streams. CI should prove the reporter on committed sanitized fixtures, but it must not pretend synthetic fixtures are live real-task evidence.
- **D-08:** If no real sanitized runtime contract log is supplied, the gate should report live/real-task coverage as not provided or fixture-only, not as live acceptance. Phase 8 owns real lawyer-trial metrics.

### Composability and Thin-Layer Enforcement

- **D-09:** Extend composability checks across legal and non-legal synthetic fixtures without adding lawfirm-only top-level schema fields. Legal-specific fields stay inside `industry_context` or metadata/profile extensions.
- **D-10:** Add boundary checks that fail if platform-contract imports Hermes, WeCom, feedback-service, conversation-read-view, or service runtime modules. Platform core must remain pure definitions and schema assets.
- **D-11:** Add checks that adapter manifests, output-boundary tests, hooks, read APIs, feedback normalization, and trial-support fixtures remain outside Hermes core rebuild scope. Phase 7 should detect thin-layer drift, not introduce new runtime behavior.

### Privacy and Secret Scanning

- **D-12:** Privacy gates must scan committed fixtures, docs, bundle manifests, and generated test outputs for exact `raw_payload` data fields, customer payload hints, complete ID/phone/bank/address-like values, plaintext secret patterns, WeCom keys/tokens/AES keys, model keys, runtime DB paths, logs, media files, and callback bodies.
- **D-13:** Source code may contain exact guard strings such as `"raw_payload"` in validators/tests. The scanner should use an explicit allowlist or mode split so guard code is allowed while fixture/data leakage still fails.
- **D-14:** Privacy scans must preserve `raw_payload_ref` and `fixture://` references as valid reference-first evidence.
- **D-15:** Route-mismatch and `skill_candidate` safety must remain human-reviewed. Gates should fail if fixtures or queue outputs imply automatic legal skill modification.

### Reports and Artifacts

- **D-16:** Gate reports should be machine-readable enough for CI (exit codes and concise JSON or text summaries) and human-readable enough for reviewers. Avoid committing generated reports unless a plan explicitly defines a stable static evidence artifact.
- **D-17:** CI artifacts must not upload runtime logs, callback bodies, customer documents, media, databases, or raw legal payloads. If artifacts are needed, upload only sanitized summaries.
- **D-18:** Documentation should clearly separate local fixture/composability gates, optional sanitized runtime-log coverage inputs, and Phase 8 live lawyer-trial acceptance.

### the agent's Discretion

- The planner may choose exact script names and workflow names. Prefer names like `scripts/run_v2_gates.py`, `contract_gates.py`, or `v2-contract-gates.yml` if they make the gate purpose obvious.
- The planner may split Phase 7 into separate plans for local gate runner/reporting, privacy/composability checks, and CI workflow/docs.
- The planner may add small helper dataclasses or report objects inside `packages/contract-test-suite` if they keep the suite dependency-free.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product and Scope

- `AGENTS.md` - V2 source-of-truth, GSD continuation protocol, privacy, Hermes boundary, no-secrets rules, and Phase 7 implementation priority.
- `docs/requirements/V2-PRD.md` - Active V2 PRD, especially CI, composability, privacy, thin-layer, coverage, and trial-readiness sections.
- `.planning/PROJECT.md` - Current project constraints, out-of-scope list, and key decisions.
- `.planning/REQUIREMENTS.md` - `REQ-composability-validation`, `REQ-security-privacy-baseline`, `REQ-v2-thin-contract-layer`, `REQ-contract-test-suite`, and `REQ-v2-development-order`.
- `.planning/ROADMAP.md` - Phase 7 goal, dependency, success criteria, and Phase 8 boundary.
- `.planning/STATE.md` - Current blockers, including live WeCom/Phase 8 human acceptance separation.

### Upstream Phase Evidence

- `.planning/phases/06-read-and-feedback-service-apis/06-CONTEXT.md` - Read/feedback API boundary, dependency-light handlers, privacy and no-authoritative-DB decisions.
- `.planning/phases/06-read-and-feedback-service-apis/06-VERIFICATION.md` - Phase 6 automated verification commands and privacy hardening fix.
- `.planning/phases/06-read-and-feedback-service-apis/06-REVIEW.md` - Clean code review and resolved raw-payload feedback API boundary.
- `.planning/phases/05.5-inkstatute-wecom-service-and-hermes-agent-adapter/05.5-CONTEXT.md` - WeCom service, adapter, no-channel-io, output boundary, and live acceptance gate.
- `.planning/phases/05.5-inkstatute-wecom-service-and-hermes-agent-adapter/05.5-VERIFICATION.md` - Phase 5.5 automated verification and live-blocked status.
- `.planning/phases/05.5-inkstatute-wecom-service-and-hermes-agent-adapter/05.5-WECOM-LIVE-ACCEPTANCE.md` - Live-vs-fixture evidence rules.
- `.planning/phases/05-wecom-shadow-loop-validation/05-VERIFICATION.md` - Fixture/live split and remaining human WeCom evidence gaps.

### Existing Code and Test Surface

- `packages/contract-test-suite/scripts/run_contract_tests.py` - Existing package-local contract test runner.
- `packages/contract-test-suite/README.md` - Current contract-suite coverage boundary and Phase 7 CI ownership statement.
- `packages/contract-test-suite/src/contract_test_suite/schema_validation.py` - Schema validation and forbidden top-level field enforcement.
- `packages/contract-test-suite/src/contract_test_suite/fixture_replay.py` - Bundle relationship checks.
- `packages/contract-test-suite/src/contract_test_suite/event_stream_replay.py` - JSONL event-stream replay and relationship checks.
- `packages/contract-test-suite/tests/test_composability.py` - Existing non-legal composability checks.
- `packages/contract-test-suite/tests/test_phase6_read_feedback_apis.py` - Phase 6 cross-service fixture/API privacy checks.
- `packages/platform-contract/src/platform_contract/schemas/` - JSON Schema source of truth.
- `packages/platform-contract/src/platform_contract/agent_adapter.py` - Adapter manifest validation.
- `services/wecom-service/src/wecom_service/output_policy.py` - Assistant output boundary behavior.
- `services/wecom-service/tests/test_output_policy.py` - Output policy allow/rewrite/block coverage.
- `services/hermes-contract-layer/bundles/lawfirm-profile-bundle.manifest.json` - Sanitized bundle manifest that privacy gates must protect.
- `services/hermes-contract-layer/docs/hermes_adapter_compatibility.md` - Hermes version/capability matrix.
- `services/feedback-service/src/feedback_service/queue.py` - Feedback dedupe/queue/human-review behavior.
- `services/conversation-read-view/src/conversation_read_view/api.py` - Pure read API handlers and privacy scrubber use.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `packages/contract-test-suite/scripts/run_contract_tests.py` already provides a stdlib runner for contract-test-suite and platform-contract paths.
- `test_composability.py` already checks non-legal finance/tax, engineering, and education fixtures for schema validity, relationship integrity, and lawfirm-only top-level field leaks.
- `schema_validation.py` already carries forbidden top-level field logic that Phase 7 can broaden or expose through a gate report.
- `event_stream_replay.py` already computes relationship check and breakage counts for JSONL streams.
- Every current package/service has `dependencies = []` in `pyproject.toml`, making a dependency-free CI command feasible.
- There is no `.github` workflow yet, so Phase 7 can introduce the first CI wrapper without conflicting with existing CI.

### Established Patterns

- Tests use stdlib `unittest`, explicit `PYTHONPATH`, synthetic fixtures, and reference-first data.
- Prior phases use fixture-specific tests plus broader contract-suite tests rather than heavyweight test frameworks.
- Live/runtime evidence is always separated from committed fixtures; synthetic replay cannot count as live WeCom or lawyer-trial acceptance.
- Generated bytecode and runtime data are not committed.

### Integration Points

- Root gate runner can invoke all package/service `unittest` commands and the contract-suite runner.
- GitHub Actions can call the same root gate runner.
- Privacy scanner can live under `packages/contract-test-suite/src/contract_test_suite/` or `scripts/` and be tested by `packages/contract-test-suite/tests/`.
- Coverage/report helper can consume committed `phase4_*_event_stream.jsonl`, `phase5_wecom_contract_stream.jsonl`, and optional external sanitized JSONL paths.
- Thin-layer checks can inspect imports and schema files without importing runtime services.

</code_context>

<specifics>
## Specific Ideas

- Prefer a root command that prints each gate name before running it: platform contracts, contract suite, service suites, composability, privacy, coverage, compile.
- Prefer a privacy scanner with two modes: strict fixture/data scan and source-code allowlist scan.
- Prefer a coverage report that distinguishes `fixture_coverage` from `runtime_coverage_input_missing`.
- Prefer CI workflow names that make the V2 boundary explicit, such as `v2-contract-gates.yml`.
- Prefer failing closed for schema, relationship, privacy, and thin-layer import violations; live runtime input absence should be explicit but not mislabeled as pass.

</specifics>

<deferred>
## Deferred Ideas

- Phase 8 owns real lawyer-trial execution, live five-workday metrics, and real-task acceptance reports.
- Production deployment topology, live WeCom callback evidence, and real customer document handling remain runtime/operator concerns outside committed CI fixtures.
- Full security platform features such as RBAC, encryption-at-rest, WORM audit logs, tenancy, key rotation, and retention/destruction workflows remain beyond V2.

</deferred>

---

*Phase: 7-CI, Composability, and Privacy Gates*
*Context gathered: 2026-06-28T07:58:00Z*

