---
phase: 76
slug: provider-registry-model-catalog
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-11
updated: 2026-07-11
---

# Phase 76 — Validation Strategy

> Per-phase validation contract for provider/catalog consistency, safe probing, and CSRF-protected SSR execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` suites collected by `pytest` |
| **Config file** | Existing per-package `tests/` layouts; no new framework config |
| **Wave 1 package command** | `PYTHONPATH=packages/operator-config/src:packages/platform-runtime/src python -m pytest packages/operator-config/tests/test_schemas.py packages/operator-config/tests/test_validate_document.py packages/operator-config/tests/test_catalog.py -q` |
| **Wave 2 API command** | `PYTHONPATH=services/admin-console-api/src:packages/rbac/src:packages/platform-runtime/src:packages/platform-contract/src:packages/operator-config/src:services/conversation-read-view/src:services/feedback-service/src python -m pytest services/admin-console-api/tests/test_config_providers.py services/admin-console-api/tests/test_config_catalog.py services/admin-console-api/tests/test_config_probe.py -q` |
| **Wave 3 UI command** | `PYTHONPATH=services/admin-web-ui/src:services/admin-console-api/src:packages/rbac/src:packages/platform-runtime/src:packages/platform-contract/src:packages/operator-config/src:services/conversation-read-view/src:services/feedback-service/src python -m pytest services/admin-web-ui/tests/test_csrf.py services/admin-web-ui/tests/test_providers_form.py services/admin-web-ui/tests/test_catalog_form.py -q` |
| **Full suite command** | `python scripts/run_v2_gates.py` |
| **Feedback target** | Each targeted command completes in under 60 seconds |

---

## Sampling Rate

- **After every task commit:** Run that task's `<verify><automated>` command.
- **After Wave 1:** Run the operator-config package command and compile all six Wave 0 test files.
- **After Wave 2:** Run all three API test modules together; no live DNS/network is permitted.
- **After Wave 3:** Run all three UI test modules together, then `python scripts/run_v2_gates.py`.
- **Before `$gsd-verify-work`:** The full gate must be green; mocked probe success is not live acceptance.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirements | Threat Ref | Secure behavior | Automated proof | Status |
|---------|------|------|--------------|------------|-----------------|-----------------|--------|
| 76-01-01 | 01 | 1 | PROV-01, PROV-02, PROV-03 | T-76-02..06 | Source-grounded vendor/model contracts, required supports_vision, strict allowlist parsing, no env/Hermes/network | `pytest test_schemas.py test_catalog.py -q` with operator-config PYTHONPATH | ⬜ pending |
| 76-01-02 | 01 | 1 | PROV-01, PROV-02, PROV-03 | T-76-01..05 | Canonical built-ins and registry-instance catalog binding enforced with no value echo | `pytest test_validate_document.py test_schemas.py test_catalog.py -q` with operator-config PYTHONPATH | ⬜ pending |
| 76-02-01 | 02 | 1 | PROV-01..04 | T-76-07, T-76-09..12 | API RED contracts include forged built-ins, selection mismatch, SSRF classes, headers, gates, no body/save | Compile the three API scaffold modules | ⬜ pending |
| 76-02-02 | 02 | 1 | PROV-01..04 | T-76-08..12 | UI RED contracts include signed CSRF mismatch and 403-before-proxy for all three POST routes | Compile the three UI scaffold modules | ⬜ pending |
| 76-03-01 | 03 | 2 | PROV-04 | T-76-15, T-76-17..19 | Public HTTPS only, unsafe-address rejection, no redirects, exact auth dialects, no response read/log | `pytest services/admin-console-api/tests/test_config_probe.py -q` with API PYTHONPATH | ⬜ pending |
| 76-03-02 | 03 | 2 | PROV-01..04 | T-76-13..19 | Metadata, canonical persistence, provider-instance selection, stored-provider-only gated probe | Run all three API test modules | ⬜ pending |
| 76-04-01 | 04 | 3 | PROV-01..04 | T-76-20..21 | Nonce+HMAC-SHA256 binds role, tenant, route; compare_digest rejects tampering | `pytest services/admin-web-ui/tests/test_csrf.py -q` with UI/RBAC PYTHONPATH | ⬜ pending |
| 76-04-02 | 04 | 3 | PROV-01, PROV-02, PROV-03 | T-76-23..26 | API-metadata rendering, refs-only escaped fields, valid non-nested forms, no JavaScript/live claims | Import/render smoke from Plan 76-04 Task 2 | ⬜ pending |
| 76-04-03 | 04 | 3 | PROV-01..04 | T-76-20..27 | Every new POST validates CSRF before proxy; save/probe/catalog flows stay generic and refs-only | Run all three UI test modules | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/admin-console-api/tests/test_config_providers.py` — canonical built-ins, forged URL/allowlist rejection, custom round-trip, refs-only/RBAC/flag coverage.
- [ ] `services/admin-console-api/tests/test_config_catalog.py` — operator provider_id versus vendor_id binding, built-in mismatch, custom allowlist positive/negative coverage.
- [ ] `services/admin-console-api/tests/test_config_probe.py` — resolver/opener-injected SSRF matrix, disabled redirects, auth dialects, no body/save, gates.
- [ ] `services/admin-web-ui/tests/test_csrf.py` — process-local signed token, role/tenant/route binding, compare_digest coverage.
- [ ] `services/admin-web-ui/tests/test_providers_form.py` — metadata-driven provider/probe SSR, CSRF-before-proxy, escaping, form ownership, no-live claims.
- [ ] `services/admin-web-ui/tests/test_catalog_form.py` — metadata-driven catalog/vision badges, selection POST, CSRF-before-proxy, no-live claims.

Plan 76-02 owns these test files only. Plans 76-03 and 76-04 turn them green after Plan 76-01 supplies the operator-config contracts.

---

## Required Negative Matrices

### Provider/catalog

- Built-in provider with forged `api_base_url`.
- Built-in provider with non-empty `model_allowlist`.
- Duplicate provider registry IDs.
- Catalog provider missing or half-filled.
- Built-in model selected through the wrong provider kind.
- Custom model absent from the selected provider instance's allowlist.
- Planted secret marker absent from every error body.

### Probe destination

- Non-HTTPS custom URL and URL with userinfo.
- Loopback, private, link-local, multicast, reserved, and unspecified resolver results.
- Redirect response with zero credential forwarding.
- Missing/unsupported key ref, unknown provider, flag OFF, and LAWYER/VIEWER role.
- Response fake whose `read()` fails the test if called.

### CSRF

- Missing, malformed, tampered, cross-role, cross-tenant, and cross-route token.
- Provider save, catalog save, and provider probe each return 403 before all API proxy calls.

---

## Manual-Only Verifications

All phase behavior has automated verification. Probe success is represented by injected resolver/opener fixtures only. Phase 76 must not claim live provider reachability, Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ `--live` acceptance.

---

## Validation Sign-Off

- [x] Every task has `<verify><automated>`.
- [x] Wave 0 test ownership is isolated in Plan 76-02.
- [x] API and UI green plans depend on their Wave 0 scaffolds.
- [x] Resolver/opener injection avoids live network and controls feedback latency.
- [x] CSRF valid/missing/mismatch behavior is automated for all three new POST routes.
- [x] No watch-mode command or external package install is required.
- [x] `nyquist_compliant: true` remains set.

**Approval:** revised and approved 2026-07-11
