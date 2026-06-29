---
phase: 10
slug: embeddable-runruntime-fake-backend
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-28T23:49:30Z
updated: 2026-06-28T23:49:30Z
---

# Phase 10 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Runtime host -> `DefaultRunRuntime` | Embedding application injects backend, optional channels, feature flags, output boundary, clock, ID factory, and contract-log store. | Run requests, feature flags, IDs, refs, hashes, sanitized metadata |
| `DefaultRunRuntime` -> `BackendAdapter` | Runtime calls only the neutral backend protocol for fake run lifecycle behavior. | Run handles, run state, stream events, artifact refs |
| Backend stream -> ordinary-user visibility | Every yielded `RunEvent` passes through `AssistantOutputBoundary.apply` before stream exposure. | Visible deltas, non-text state events, sanitized output-boundary audit metadata |
| Runtime -> contract log store | Runtime writes append-only run/run_event records only when explicitly enabled and a store is injected. | Event IDs, statuses, `raw_payload_ref`, content hashes, sanitized metadata |
| Contract-test fixture -> evidence consumers | Static fake-runtime fixture proves embedded behavior without live service claims. | Synthetic non-legal fixture data, refs, hashes, zero-channel/no-server metadata |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-10-01-runtime-coupling | Tampering / Elevation of Privilege | `packages/platform-runtime/src` | mitigate | Runtime source imports protocol/support modules only and does not import concrete service, channel, or backend packages; protocol boundary tests pass. | closed |
| T-10-01-raw-payload-log | Information Disclosure | `InMemoryContractLogStore` | mitigate | Store validation rejects nested and top-level `raw_payload` plus full-text payload-like keys; runtime writes `raw_payload_ref` and hashes instead of request text. | closed |
| T-10-01-default-on-lane | Elevation of Privilege | `RuntimeFeatureFlags` | mitigate | All run, streaming, channel delivery, approval, and contract-log lanes default to `False`; tests prove disabled lanes fail closed. | closed |
| T-10-01-hidden-server | Spoofing / Tampering | runtime support package | mitigate | Phase 10 adds no HTTP framework, socket, database, queue, service process, or background worker; runtime constructs without a `server` attribute. | closed |
| T-10-02-backend-specific-runtime | Tampering | `DefaultRunRuntime` | mitigate | Runtime depends on the `BackendAdapter` Protocol and never branches on concrete backend names or private paths. | closed |
| T-10-02-channel-required | Denial of Service | `DefaultRunRuntime.__init__` | mitigate | `channels=()` is the default and zero-channel construction is covered by lifecycle tests. | closed |
| T-10-02-flag-bypass | Elevation of Privilege | runtime lifecycle methods | mitigate | `create_run`, `poll`, `stream`, `cancel`, and `approve` require enabled runtime flags before backend mutation or streaming. | closed |
| T-10-02-approval-unsafe | Elevation of Privilege | `approve` path | mitigate | `approve` requires `approval_lane_enabled` and records only sanitized approval state when contract logging is enabled. | closed |
| T-10-03-stream-leak | Information Disclosure | stream output boundary | mitigate | `_apply_output_boundary` now calls the injected boundary for every yielded event, including non-text state events; regression spot-check reports `events=4 boundary_calls=4`. | closed |
| T-10-03-legal-rewrite | Integrity | output boundary allow path | mitigate | Allow decisions preserve business/legal visible text byte-for-byte; tests assert legal conclusion equality. | closed |
| T-10-03-secret-audit | Information Disclosure | output-boundary audit metadata | mitigate | Audit metadata stores rule ID, hash prefix, length, and privacy marker; tests assert blocked/replaced originals are absent from yielded events and audit metadata. | closed |
| T-10-03-neutral-scan | Information Disclosure / Coupling | neutral runtime source | mitigate | Runtime source keeps generic rules; concrete leak samples stay in tests/fixtures and boundary allowlist/neutral source tests pass. | closed |
| T-10-04-fixture-sensitive-payload | Information Disclosure | Phase 10 contract fixture | mitigate | Fixture uses synthetic non-sensitive data, `raw_payload_ref`, refs, hashes, and sanitized policy summaries only; contract tests reject raw payload-like keys. | closed |
| T-10-04-false-live-claim | Spoofing | Phase 10 fixture and docs | mitigate | Fixture and README state fake backend, zero channels, no server, and not-live-acceptance markers. | closed |
| T-10-04-relationship-gap | Tampering / Repudiation | Phase 10 fixture relationships | mitigate | Contract tests verify relationship IDs and gap-free run event sequencing. | closed |
| T-10-04-test-runner-path | Tampering | contract test runner | mitigate | Runner imports `platform-runtime` only through explicit test path setup for Phase 10 validation; full contract-test-suite passes. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-28 | 16 | 16 | 0 | codex inline security auditor |

### Verification Evidence

| Check | Result |
|-------|--------|
| `PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/platform-runtime/tests/test_protocols.py packages/platform-runtime/tests/test_feature_flags.py packages/platform-runtime/tests/test_contract_log_store.py packages/platform-runtime/tests/test_run_runtime_lifecycle.py packages/platform-runtime/tests/test_output_boundary.py` | PASS, 40 tests |
| `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src:packages/platform-runtime/src python packages/contract-test-suite/scripts/run_contract_tests.py` | PASS, 107 tests |
| Boundary spot-check with counting output boundary | PASS, `events=4 boundary_calls=4` |
| Source scan for concrete services/backends/channels/server/database/queue dependencies in `packages/platform-runtime/src` | PASS, no forbidden imports or runtime construction found |
| Phase 10 verification report | PASS, 14/14 must-haves verified |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-28
