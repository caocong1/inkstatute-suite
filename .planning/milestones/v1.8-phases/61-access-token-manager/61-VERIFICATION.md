---
phase: 61-access-token-manager
verified: 2026-07-09T09:06:09Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 61: Access Token Manager Verification Report

**Phase Goal:** QQ Bot access token is acquired via `appId + clientSecret → POST /getAppAccessToken`, cached with 7200s TTL, auto-refreshed 60s before expiry, and single-flight under concurrent refresh via `asyncio.Lock`.
**Verified:** 2026-07-09T09:06:09Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `token_manager.py` acquires access token via `POST /getAppAccessToken` using appId + clientSecret | ✓ VERIFIED | `UrllibTokenTransport._blocking_fetch` POSTs JSON `{"appId","clientSecret"}` to `https://bots.qq.com/app/getAppAccessToken`; `TokenManager.get_token` awaits `self._transport.fetch_token(self._app_id, self._client_secret)` |
| 2 | Token cached with 7200s TTL and auto-refreshed 60s before expiry | ✓ VERIFIED | Cache TTL from response `expires_in` (not hardcoded); default `refresh_margin=60.0`; `_is_near_expiry` triggers when `clock() >= expires_at - refresh_margin`. Lifecycle tests cover 7200s path and non-hardcoded `expires_in=100` |
| 3 | Concurrent refresh is single-flight via `asyncio.Lock` | ✓ VERIFIED | `self._lock = asyncio.Lock()` with lock re-check before fetch; `test_concurrent_refresh_is_single_flight` — 10× `asyncio.gather` → `call_count == 2`, all results `"token-002"` |
| 4 | Tests cover lifecycle, concurrent refresh, and error handling | ✓ VERIFIED | 13 tests green: 5 lifecycle + 1 concurrent + 6 error + 1 import-safety; wecom AST coverage for `token_manager.py` also green |

**Score:** 4/4 truths verified

### Plan Must-Haves (merged, non-roadmap detail)

All Plan 01/02 frontmatter truths verified against codebase:

| Plan truth | Status | Evidence |
| --- | --- | --- |
| Injected `app_id` / `client_secret` (no env/file reads) | ✓ VERIFIED | Keyword-only constructor stores strings; no `os.environ` / file I/O in module |
| No top-level urllib/httpx/aiohttp; `dependencies = []` | ✓ VERIFIED | Lazy import inside `_blocking_fetch`; `grep -c 'dependencies = \[\]' pyproject.toml` → 1; import-safety test green |
| TokenError propagates; missing/invalid fields raise; no credential leak | ✓ VERIFIED | `TokenManagerErrorTests` (6 cases) all pass |
| `test_no_wecom_import` covers `token_manager.py` | ✓ VERIFIED | `test_token_manager_does_not_import_wecom_service` present and green |

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py` | TokenManager + transports + TokenError | ✓ VERIFIED | Exists, substantive (~180 lines), exports `__all__` as planned; `asyncio.Lock` + lock re-check wired |
| `packages/channels/qqbot/tests/test_token_manager.py` | Lifecycle + concurrent + error + import-safety | ✓ VERIFIED | Classes `TokenManagerLifecycleTests`, `TokenManagerConcurrentRefreshTests`, `TokenManagerErrorTests`, `TokenManagerImportSafetyTests` |
| `packages/channels/qqbot/tests/test_no_wecom_import.py` | AST isolation for token_manager | ✓ VERIFIED | `test_token_manager_does_not_import_wecom_service` reads `PACKAGE_SRC / "token_manager.py"` |

`gsd-tools query verify.artifacts` for both plans: `all_passed: true` (4/4 artifacts).

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `token_manager.py` | `TokenTransport.fetch_token` | `get_token` slow path | ✓ WIRED | Lines 143–145: `await self._transport.fetch_token(self._app_id, self._client_secret)` after lock re-check |
| `test_token_manager.py` | `token_manager.py` | import + FakeTokenTransport | ✓ WIRED | `from inkstatute_channels_qqbot.token_manager import FakeTokenTransport, TokenError, TokenManager` |
| `test_token_manager.py` | concurrent single-flight | `asyncio.gather` | ✓ WIRED | Line 177: `asyncio.gather(*[manager.get_token() for _ in range(10)])` + `call_count == 2` |
| `test_no_wecom_import.py` | `token_manager.py` | AST `_imported_modules` | ✓ WIRED | Lines 85–92 scan `token_manager.py` |

Note: `gsd-tools query verify.key-links` reported false negatives due to double-escaped regex patterns in PLAN frontmatter (`fetch_token\\\\(` etc.). Manual source inspection confirms all links are wired.

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `TokenManager.get_token` | `_token` / `_expires_at` | `transport.fetch_token` → `_extract_token` / `_extract_expiry` | Yes — response fields populate cache; FakeTokenTransport supplies fixture payloads in tests | ✓ FLOWING |
| `UrllibTokenTransport` | JSON body / response | POST getAppAccessToken | Production path present; CI uses FakeTokenTransport (by design — no live QQ credentials) | ✓ FLOWING (prod path) / Fake in tests |

`TokenManager` is intentionally not exported from `__init__.py` and not yet consumed by the egress sender — Phase 62 owns that wiring. Not a Phase 61 gap.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Token manager unit suite | `PYTHONPATH=packages/channels/qqbot/src python3 -m unittest packages.channels.qqbot.tests.test_token_manager -v` | 13 tests OK, exit 0 | ✓ PASS |
| WeCom import isolation | `PYTHONPATH=packages/channels/qqbot/src python3 -m unittest packages.channels.qqbot.tests.test_no_wecom_import -v` | 9 tests OK (incl. token_manager), exit 0 | ✓ PASS |
| Structural: URL + Lock + margin | Python asserts on source | `structural_ok` | ✓ PASS |
| `dependencies = []` | `grep -c 'dependencies = \[\]' packages/channels/qqbot/pyproject.toml` | `1` | ✓ PASS |

### Probe Execution

| Probe | Command | Result | Status |
| --- | --- | --- | --- |
| — | — | No phase-declared or conventional `scripts/*/tests/probe-*.sh` for this phase | SKIPPED |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| EGRESS-01 | 61-01, 61-02 | QQ Bot access token via getAppAccessToken, cache TTL, 60s refresh, asyncio.Lock single-flight | ✓ SATISFIED | All 4 roadmap SCs verified; implementation + 13 unit tests |

REQUIREMENTS.md maps EGRESS-01 → Phase 61 only. No orphaned phase-61 requirements. EGRESS-02/03/04 map to Phase 62 (out of scope).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| — | — | No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` in phase-modified files | — | None |

`FakeTokenTransport` is intentional test infrastructure, not a production stub. `UrllibTokenTransport` is production-ready.

### Human Verification Required

None. No `<human-check>` blocks in PLAN files. Phase deliverable is a library module with FakeTokenTransport-backed unit coverage; live QQ Bot credential acquisition is explicitly out of scope for CI.

### Gaps Summary

No gaps. Phase goal achieved in codebase: acquire → cache (`expires_in`, typically 7200s) → 60s pre-expiry refresh → single-flight `asyncio.Lock`, with lifecycle/concurrent/error tests green.

**Confirmation-bias notes (non-blocking):**
1. Roadmap wording "7200s TTL" is satisfied via response `expires_in` (QQ returns 7200); plan correctly forbids hardcoding 7200 as cache TTL — verified by `test_uses_response_expires_in_not_hardcoded_7200`.
2. Production `HTTPError`/`URLError` mapping in `UrllibTokenTransport` is not exercised against real urllib in unit tests; equivalent `TokenError` propagation is covered via FakeTokenTransport injection — acceptable for this phase.
3. `TokenManager` consumer wiring deferred to Phase 62 by plan — not a Phase 61 gap.

---

_Verified: 2026-07-09T09:06:09Z_
_Verifier: Claude (gsd-verifier)_
