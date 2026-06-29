---
phase: 11-hermes-backendadapter-parity-spike
status: verified
created: 2026-06-29T00:29:00Z
updated: 2026-06-29T00:29:00Z
threats_open: 0
asvs_level: 1
---

# Phase 11 Security Review

## Scope

Phase 11 adds the concrete Hermes backend package, non-mutating capability probe, default-off `/v1/runs` client seam, approval safety guard, and parity fixtures/reporting.

## Threat Register

| ID | Threat | Severity | Mitigation | Status |
|---|---|---:|---|---|
| SEC-11-01 | Concrete Hermes code leaks into neutral runtime packages. | High | Code lives under `packages/backends/hermes`; neutral runtime import scan passes. | CLOSED |
| SEC-11-02 | Adapter performs ordinary-user channel I/O. | High | Manifest/capabilities enforce `no_channel_io=True`; adapter has no delivery methods. | CLOSED |
| SEC-11-03 | One-shot stores raw prompt/transcript in metadata. | High | Adapter stores `raw_payload_ref`, `request_content_sha256`, refs, and sanitized metadata only. | CLOSED |
| SEC-11-04 | One-shot overclaims streaming/cancel/approval/live/parallel support. | Medium | Reduced manifest tests lock unsupported capability booleans to false. | CLOSED |
| SEC-11-05 | Capability probe mutates or reads run-specific state. | High | `SAFE_PROBE_PATHS` is limited to `/health`, `/v1/capabilities`, `/v1/models`; tests assert exact paths. | CLOSED |
| SEC-11-06 | Probe dependency introduces live network behavior inside package. | Medium | Probe uses injected transport only; dependency scan rejects requests/httpx/aiohttp/socket/subprocess. | CLOSED |
| SEC-11-07 | Probe fallback leaks URL/token/private path exception text. | High | Fallback uses bounded reason codes; failing transport test includes URL/token/path and repr stays clean. | CLOSED |
| SEC-11-08 | `/v1/runs` becomes default before parity. | High | Config defaults disabled; env requires exact true-ish value; adapter still requires explicit `invocation_mode="runs_api"`. | CLOSED |
| SEC-11-09 | Disabled `/v1/runs` client touches transport. | High | `HermesRunsDisabledError` is raised before transport access; tests assert zero calls. | CLOSED |
| SEC-11-10 | API-run status drift emits invalid platform state. | Medium | Unknown statuses map to `AsyncTaskState.FAILED` with hash-only metadata. | CLOSED |
| SEC-11-11 | High-risk legal approval is auto-approved. | High | High-risk markers return human-review rejection with zero runner/transport calls. | CLOSED |
| SEC-11-12 | Non-high-risk API approval is forwarded without explicit support. | High | Fixed in `d09c317`; API approval requires explicit `api_approval_support=True`, otherwise unsupported and zero transport calls. | CLOSED |
| SEC-11-13 | Parity fixtures commit raw legal payloads, transcripts, secrets, runtime paths, or live claims. | High | Fixture uses refs/hashes only; privacy and forbidden-marker scans pass; `not_live_acceptance=true`. | CLOSED |
| SEC-11-14 | Failed parity is mistaken as permission to promote `/v1/runs`. | High | Intentional route mismatch yields `promote_api_runs=False` and `default_lane="oneshot"`. | CLOSED |
| SEC-11-15 | Contract-test-suite imports concrete backend from neutral runtime source. | Medium | Test-time path setup imports backend package directly; runtime source remains neutral. | CLOSED |

## Evidence

| Check | Result |
|---|---|
| Probe dependency scan | PASS - no `requests`, `httpx`, `aiohttp`, `urllib.request.urlopen`, `subprocess`, or socket construction in `probe.py`. |
| Fixture privacy scan | PASS - `assert_privacy_clean` on `parity_cases.json`. |
| Targeted safety tests | PASS - 21 tests OK across runs lane, capability probe, and parity report. |
| Backend suite | PASS - 30 tests OK. |
| Full contract runner | PASS - 110 tests OK. |
| Neutral runtime scan | PASS - no concrete Hermes imports in `packages/platform-runtime/src`. |
| Code review | PASS - `11-REVIEW.md` status clean. |
| Schema drift | PASS - `drift_detected=false`. |

## Security Decision

Phase 11 is security-verified for fixture-backed, default-off backend-adapter work. It does not approve live WeCom acceptance or `/v1/runs` live rollout. One-shot remains the safe default.

## Open Threats

None.

