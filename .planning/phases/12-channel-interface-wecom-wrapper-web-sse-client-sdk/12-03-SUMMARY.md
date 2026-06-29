---
phase: "12-channel-interface-wecom-wrapper-web-sse-client-sdk"
plan: "12-03"
subsystem: client-embedding-surface
tags: [platform-api, openapi, typescript-sdk, default-off, remote-thin]
requires:
  - phase: "12-02-web-api-sse-fixture-channel"
    provides: "ChannelAdapter contract, default-off channel config pattern, and SSE frame encoding shape"
  - phase: "11-hermes-backendadapter-parity-spike"
    provides: "RunRuntime Protocol and FakeBackendAdapter for end-to-end handler smoke"
  - phase: "10-embeddable-runruntime-fake-backend"
    provides: "DefaultRunRuntime, RuntimeFeatureFlags, ContractLogStore injection"
provides:
  - "Default-off PlatformApiConfig with secret refs only and INKSTATUTE_PLATFORM_API_ENABLED gate"
  - "PlatformApiApp pure handler host with dispatch + stream surfaces (no ASGI/WSGI dependency)"
  - "Deterministic OpenAPI 3.1 document for run lifecycle and SSE stream endpoints"
  - "Deterministic TypeScript SDK generator that emits a remote/thin PlatformApiClient"
  - "25 platform_api tests + 9 platform-sdk-ts tests covering config gates, handler validation, lifecycle, OpenAPI shape, and SDK determinism"
affects: [phase-12, phase-13, client-embedding-surface, sdk-generation]
tech-stack:
  added: []
  patterns: [default-off-platform-api, pure-handler-host, deterministic-openapi, deterministic-sdk-generation, remote-thin-sdk]
key-files:
  created:
    - apps/platform_api/pyproject.toml
    - apps/platform_api/README.md
    - apps/platform_api/src/platform_api/__init__.py
    - apps/platform_api/src/platform_api/config.py
    - apps/platform_api/src/platform_api/app.py
    - apps/platform_api/src/platform_api/openapi.py
    - apps/platform_api/openapi/platform-api.json
    - apps/platform_api/tests/test_platform_api.py
    - packages/platform-sdk-ts/package.json
    - packages/platform-sdk-ts/README.md
    - packages/platform-sdk-ts/scripts/generate_sdk.py
    - packages/platform-sdk-ts/src/index.ts
    - packages/platform-sdk-ts/tests/test_sdk_generation.py
  modified: []
key-decisions:
  - "The platform API host is a pure handler host: it accepts plain dicts and returns plain dicts, so any ASGI/WSGI/starlette/fastapi adapter can wrap it without taking on a production web-server dependency."
  - "OpenAPI is rendered with sort_keys=True, ASCII-only JSON, and 2-space indent so the on-disk document is byte-stable for SDK generation and contract tests."
  - "The TypeScript SDK generator is a pure function over the OpenAPI document; it never depends on a third-party OpenAPI generator or a TypeScript toolchain."
  - "The SDK ships its own minimal SSE frame parser (parseSseFrame) and exposes a remote/thin client; it never embeds DefaultRunRuntime, BackendAdapter, or RunRequest."
  - "All five run lifecycle operations are exposed: createRun, pollRun, cancelRun, submitApproval, streamRun; streamRun is implemented as an async generator that yields sanitized SSE frames."
patterns-established:
  - "Default-off config + secret refs only for cross-runtime hosts (extends the pattern from Phase 12-01 / 12-02)."
  - "OpenAPI is the source of truth; the SDK is generated rather than hand-edited, and a committed-file-matches-builder test enforces the discipline."
  - "Generator inputs are sorted, so two consecutive runs on the same input produce byte-identical output; a determinism test pins the behavior."
requirements-completed:
  - REQ-client-embedding-surface
duration: 25 min
completed: 2026-06-29
---

# Phase 12 Plan 03: Platform API OpenAPI And TypeScript SDK Summary

**Default-off platform API host + deterministic OpenAPI + remote/thin TypeScript SDK.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-06-29T04:00:00Z
- **Completed:** 2026-06-29T04:25:00Z
- **Tasks:** 4
- **Files modified:** 13 (created)

## Accomplishments

- Added `inkstatute-platform-api` package with `PlatformApiConfig` (default-off via `INKSTATUTE_PLATFORM_API_ENABLED`, secret refs only) and a pure-handler `PlatformApiApp` that delegates to an injected `RunRuntime`.
- Implemented `handle_create_run`, `handle_poll_run`, `handle_cancel_run`, `handle_submit_approval`, and `handle_stream_run`; the host never starts a production HTTP server, never embeds a local runtime, and never imports a concrete backend or channel adapter.
- Added a deterministic OpenAPI 3.1 document (24 KB JSON, sorted/ASCII) covering the five run lifecycle operations and the SSE stream endpoint, with sanitized examples that use refs and placeholder ids only.
- Added a deterministic Python generator that emits a remote/thin TypeScript SDK (`createRun`/`pollRun`/`cancelRun`/`submitApproval`/`streamRun` + a `parseSseFrame` helper); the SDK is the committed `packages/platform-sdk-ts/src/index.ts`.
- Added 25 platform API tests (config gates, handler validation, disabled-gate behavior, full lifecycle through fakes, OpenAPI shape, and SDK determinism) plus 9 SDK tests (CLI determinism, content checks, OpenAPI source-of-truth) — 34 tests in total.

## Task Commits (suggested; host git is read-only in this sandbox)

1. **Task 12-03-01: platform_api package + PlatformApiConfig** - `feat(12-03): add platform_api package and default-off config`
2. **Task 12-03-02: handlers + dispatch/stream** - `feat(12-03): implement pure handler host over injected RunRuntime`
3. **Task 12-03-03: OpenAPI + SDK generator** - `feat(12-03): add deterministic openapi document and typescript sdk generator`
4. **Task 12-03-04: API + SDK tests** - `test(12-03): cover platform api handlers, openapi, and sdk determinism`

**Plan metadata:** this SUMMARY file

## Files Created/Modified

- `apps/platform_api/pyproject.toml` - package metadata for the platform API host.
- `apps/platform_api/README.md` - boundary, operations, configuration, OpenAPI, SDK, tests, and not-live-acceptance notes.
- `apps/platform_api/src/platform_api/__init__.py` - public package exports (config + handlers + app).
- `apps/platform_api/src/platform_api/config.py` - default-off `PlatformApiConfig` with secret-ref-only settings.
- `apps/platform_api/src/platform_api/app.py` - pure handler functions and `PlatformApiApp` (dispatch + stream).
- `apps/platform_api/src/platform_api/openapi.py` - deterministic OpenAPI 3.1 builder for run lifecycle and SSE stream.
- `apps/platform_api/openapi/platform-api.json` - committed OpenAPI document (24 024 bytes).
- `apps/platform_api/tests/test_platform_api.py` - 25 tests across config, dispatch, lifecycle, OpenAPI, and SDK determinism.
- `packages/platform-sdk-ts/package.json` - SDK package metadata with a `generate` script.
- `packages/platform-sdk-ts/README.md` - generation, usage, and not-live-acceptance notes.
- `packages/platform-sdk-ts/scripts/generate_sdk.py` - deterministic TypeScript SDK generator.
- `packages/platform-sdk-ts/src/index.ts` - generated TypeScript SDK (4 880 bytes; deterministic; remote/thin).
- `packages/platform-sdk-ts/tests/test_sdk_generation.py` - 9 tests for the generator and committed SDK.

## Decisions Made

- The host is implemented as **plain async/sync functions** that take and return Python dicts. This keeps the package dependency-free at runtime, makes the surface trivially testable, and lets any ASGI/WSGI adapter wrap the handlers externally when a real HTTP host is finally wired.
- OpenAPI is the **source of truth**: the on-disk `platform-api.json` is rendered by `build_openapi_document` and `render_openapi_json`; a test asserts the committed file equals the builder output.
- The SDK generator is a **pure function** over the OpenAPI mapping; it sorts paths, methods, and path params, so the same input always produces byte-identical output. A test exercises the determinism by running the CLI twice and comparing the output.
- The SDK ships its own minimal SSE frame parser instead of depending on an external package, keeping the package zero-dependency and remote/thin.
- The host is **default-OFF** and ref/secret-ref-first; `PlatformApiDisabledError` is raised for every operation when the env flag is missing.

## Deviations from Plan

### Auto-fixed Issues

- Initial generator used `value.split("_")` for camelCase, which collapsed `createRun` into `createrun`. Switched to a manual camelCase splitter so `pollRun`, `createRun`, etc. round-trip correctly.
- The body-line indentation in the generated SDK was 2 spaces; corrected to 4 spaces so the output reads as a normal TypeScript class body.
- Test helper originally used `asyncio.get_event_loop()`; on Python 3.14 the main thread has no default event loop, so the helper now uses `asyncio.new_event_loop()` (one-off, per test, then closed).
- The privacy pre-check in `test_contract_log_records_run_and_events` initially assumed `raw_payload_ref` was always `None`; tightened to drop the metadata in the test payload so the assertion is meaningful (and a separate test exercises the pass-through path with a ref).

### Sandbox Note

- The user's `.git` directory in this sandbox is mounted read-only, so commits could not be created from the agent process. The work is staged and the suggested commits are listed above for the host git to apply.

**Total deviations:** 4 test/quality refinements + 1 sandbox note.
**Impact on plan:** Plan scope preserved; tests are stronger; commit timing is the user's responsibility.

## Issues Encountered

- None significant. Generator and host landed on the first run after the camelCase and indentation fixes; 34 tests passed end-to-end.

## Verification

- `python -m compileall apps/platform_api/src apps/platform_api/tests` - passed.
- `PYTHONPATH=apps/platform_api/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest apps.platform_api.tests.test_platform_api` - **25 tests passed**.
- `python packages/platform-sdk-ts/tests/test_sdk_generation.py` - **9 tests passed**.
- `PYTHONPATH=apps/platform_api/src:packages/platform-contract/src python3 -c "from contract_test_suite.privacy_scan import scan_privacy_targets; ..."` - **0 source privacy issues** across all new files.
- Two consecutive `generate_sdk.py` runs produced byte-identical output (md5 match).
- The committed `apps/platform_api/openapi/platform-api.json` matches `build_openapi_document()` exactly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`apps/platform_api` is a default-off thin host for `RunRuntime`, the OpenAPI document is committed, and the TypeScript SDK is generated deterministically and committed. Phase 12-04 (Embeddable Web Chat + Contract Evidence) can consume the SDK/API shapes, the SSE frame format, and the not-live-acceptance discipline to ship a small embeddable chat renderer.

---
*Phase: 12-channel-interface-wecom-wrapper-web-sse-client-sdk*
*Completed: 2026-06-29*
