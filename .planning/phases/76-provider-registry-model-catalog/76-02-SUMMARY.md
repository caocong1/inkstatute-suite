---
phase: 76-provider-registry-model-catalog
plan: 02
subsystem: testing
tags: [csrf, ssrf, ssr, provider-registry, model-catalog, unittest, pytest, hmac]

# Dependency graph
requires:
  - phase: 74-admin-config-api-rbac
    provides: /config/providers + /config/catalog GET/PUT sections, RBAC matrix, operator_config_enabled flag gate
  - phase: 75-channel-config-apply
    provides: admin-web-ui SSR form pattern (channels.py), fake API proxy + CSRF field convention
provides:
  - "Wave 0 API RED contracts for /config/providers (canonical built-ins, custom allowlist, forged URL/allowlist rejection, duplicate ID, probe_targets metadata)"
  - "Wave 0 API RED contracts for /config/catalog (registry-instance to vendor/allowlist binding, catalog metadata with supports_vision)"
  - "Wave 0 API RED contracts for POST /config/providers/probe (target=main|vision resolution, SSRF matrix, auth dialects, no-body/no-save, flag+RBAC gates)"
  - "Wave 0 UI RED contracts for signed CSRF (HMAC-SHA256, role/tenant/route binding, compare_digest)"
  - "Wave 0 UI RED contracts for /config/providers SSR (metadata-driven profiles, read-only built-in URLs, conditional vision probe form, CSRF-before-proxy)"
  - "Wave 0 UI RED contracts for /config/catalog SSR (metadata-driven catalog rows, supports_vision badges, CSRF-before-proxy)"
affects: [76-03, 76-04, 77-vision-routing-runtime, 78-console-ssr-docs-gate-honesty]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Resolver/opener injection seams for SSRF-safe probe testing (fake socket.getaddrinfo + recording urlopen)"
    - "Route-bound CSRF token contract (HMAC-SHA256 + nonce + role/tenant/route binding)"
    - "Fake API proxy pattern (injected handle_admin_get/handle_admin_put) for SSR POST tests"
    - "Status-only _FakeResponse that fails on read() to prove no-body-logging"

key-files:
  created:
    - "services/admin-console-api/tests/test_config_providers.py"
    - "services/admin-console-api/tests/test_config_catalog.py"
    - "services/admin-console-api/tests/test_config_probe.py"
    - "services/admin-web-ui/tests/test_csrf.py"
    - "services/admin-web-ui/tests/test_providers_form.py"
    - "services/admin-web-ui/tests/test_catalog_form.py"
  modified: []

key-decisions:
  - "Probe RED contracts define resolver and opener injection seams (handle_config_probe with resolver=, opener= kwargs) for Plan 76-03 to implement"
  - "CSRF RED contracts define issue_csrf_token/validate_csrf_token with identity+route+signing_key binding for Plan 76-04 to implement"
  - "Probe tests post only {'target': 'main'} or {'target': 'vision'} — no arbitrary provider_id/URL/ref/header/model override accepted"
  - "Absent and both partial vision pairs return identical generic not_configured with zero resolver/opener/save side effects"
  - "Catalog tests use operator-chosen provider IDs (primary-openai) distinct from vendor kinds (openai) to prove kind-based validation"
  - "All scaffold tests use fake stores, injected DNS/openers, and planted values — no live network, DNS, or provider calls"

patterns-established:
  - "Pattern: _FakeResponse fails on read() to enforce no-body-logging invariant"
  - "Pattern: _RecordingOpener records URL/headers/timeout and refuses redirect behavior"
  - "Pattern: _resolver_returning(addrinfo) provides deterministic socket.getaddrinfo-shaped results for SSRF matrix"
  - "Pattern: _try_import_csrf() / _try_import_probe() gracefully fail with self.fail() when modules don't exist yet (RED scaffold discovery)"

requirements-completed:
  - PROV-01
  - PROV-02
  - PROV-03
  - PROV-04

# Metrics
duration: 8min
completed: 2026-07-10
---

# Phase 76 Plan 02: Wave 0 API + UI Test Contracts Summary

**Six RED test-only modules specifying canonical built-ins, custom allowlists, catalog binding, SSRF-safe probing, signed CSRF, and SSR provider/catalog flows before either service implementation changes**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-10T17:52:00Z
- **Completed:** 2026-07-10T17:59:50Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created three admin-console-api Wave 0 test modules covering provider canonical persistence, catalog vendor/allowlist binding, and SSRF-safe non-destructive probing with resolver/opener injection
- Created three admin-web-ui Wave 0 test modules covering signed CSRF (HMAC-SHA256, role/tenant/route binding), provider/probe SSR forms, and catalog SSR forms
- Probe RED contracts accept only target=main|vision, resolve stored main/vision provider/model pairs, and prove absent/partial vision returns generic not_configured with zero side effects
- SSRF matrix covers scheme, userinfo, redirects, and every unsafe IP class (loopback, private 10/172/192, link-local, multicast, reserved, unspecified)
- All scaffold tests use fake stores, injected DNS/openers, and planted values — no live provider, WeCom, QQ, or lawyer-trial acceptance

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold provider, catalog, and safe-probe API contracts** - `3a31a6b` (test)
2. **Task 2: Scaffold signed-CSRF and provider/catalog SSR contracts** - `0ecb93c` (test)

_Note: TDD RED contracts — tests are intentionally failing until Plans 76-01, 76-03, and 76-04 implement production code._

## Files Created/Modified
- `services/admin-console-api/tests/test_config_providers.py` - Provider API RED contract: canonical built-in persistence, custom allowlist round-trip, planted-secret rejection, duplicate ID rejection, forged built-in URL rejection, non-empty built-in allowlist rejection, probe_targets metadata, RBAC/flag gates
- `services/admin-console-api/tests/test_config_catalog.py` - Catalog API RED contract: valid built-in kind match, built-in vendor mismatch, missing provider, valid custom allowlist selection, custom model-not-allowed rejection, catalog metadata (vendor_id/model_id/supports_vision, gpt-5/claude-opus-4-8)
- `services/admin-console-api/tests/test_config_probe.py` - Probe API RED contract: target=main|vision resolution, unknown/extra-field rejection, absent/partial vision not_configured, configured-vision parity, SSRF matrix (scheme/userinfo/redirect/IP classes), auth dialects (Bearer/x-api-key+anthropic-version), no-body/no-save, flag+RBAC gates
- `services/admin-web-ui/tests/test_csrf.py` - Signed CSRF RED contract: HMAC-SHA256, random nonce, role/tenant/route binding, compare_digest, missing/malformed/tampered/cross-role/cross-tenant/cross-route rejection
- `services/admin-web-ui/tests/test_providers_form.py` - Provider SSR RED contract: metadata-driven built-in profiles, read-only canonical URLs, editable custom URL/allowlist, refs-only rendering, blank-card drop, conditional vision probe form, CSRF-before-proxy for save and probe
- `services/admin-web-ui/tests/test_catalog_form.py` - Catalog SSR RED contract: metadata-driven vendor_id/model_id/supports_vision rows, provider-instance selection, exact copy, HTML escaping, CSRF-before-proxy

## Decisions Made
- Probe handler signature defined as `handle_config_probe(path, body, headers, flags, env, *, config_store, rbac_secret, resolver, opener)` — resolver/opener are injection seams for testability
- CSRF module signature defined as `issue_csrf_token(identity, route, signing_key)` / `validate_csrf_token(token, identity, route, signing_key)` — binds role+tenant+route into the signed payload
- Vision target resolution uses `vision.vision_provider_id` / `vision.vision_model_id` (additive field Plan 76-01 will add to VisionPolicyDoc)
- Catalog metadata exposed via `catalog_entries` list with `vendor_id`, `model_id`, `supports_vision` bool per entry

## Deviations from Plan

None - plan executed exactly as written

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Wave 0 API and UI test contracts are complete and compile-verified
- Plans 76-03 (API production: probe handler + provider/catalog metadata) and 76-04 (UI production: CSRF + SSR modules) can now turn these RED contracts green
- Plan 76-01 (operator-config: model_allowlist, built-in catalog, vendor profiles, duplicate validation, vision_provider_id) must supply the shared contracts first
- No file overlap with Wave 1 Plan 76-01 — this plan modifies tests only

---
*Phase: 76-provider-registry-model-catalog*
*Completed: 2026-07-10*
